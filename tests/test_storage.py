"""StateStore 테스트."""

import sqlite3

import pytest

from cmux_agent.domain.models import (
    Agent,
    AgentRole,
    Artifact,
    Message,
    MessageType,
    Part,
    Run,
    RunStatus,
    Task,
    TaskState,
)
from cmux_agent.infrastructure.storage import StateStore


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    s = StateStore(db_path)
    yield s
    s.close()


class TestRunCRUD:
    def test_save_and_get(self, store):
        run = Run(run_id="run-1")
        store.save_run(run)
        result = store.get_run("run-1")
        assert result is not None
        assert result.run_id == "run-1"
        assert result.status == RunStatus.CREATED

    def test_get_latest(self, store):
        store.save_run(Run(run_id="run-1"))
        store.save_run(Run(run_id="run-2"))
        latest = store.get_latest_run()
        assert latest is not None
        assert latest.run_id == "run-2"

    def test_get_active(self, store):
        store.save_run(Run(run_id="run-1", status=RunStatus.COMPLETED))
        store.save_run(Run(run_id="run-2", status=RunStatus.RUNNING))
        active = store.get_active_run()
        assert active is not None
        assert active.run_id == "run-2"

    def test_update_status(self, store):
        store.save_run(Run(run_id="run-1"))
        store.update_run_status("run-1", RunStatus.RUNNING)
        run = store.get_run("run-1")
        assert run.status == RunStatus.RUNNING

    def test_get_nonexistent(self, store):
        assert store.get_run("nonexistent") is None


class TestAgentCRUD:
    def test_save_and_list(self, store):
        store.save_run(Run(run_id="run-1"))
        store.save_agent(Agent(run_id="run-1", role=AgentRole.ORCHESTRATOR, name="orch"))
        store.save_agent(Agent(run_id="run-1", role=AgentRole.WORKER, name="w1"))

        agents = store.get_agents("run-1")
        assert len(agents) == 2
        assert agents[0].name == "orch"
        assert agents[1].name == "w1"

    def test_get_by_name(self, store):
        store.save_run(Run(run_id="run-1"))
        store.save_agent(Agent(run_id="run-1", role=AgentRole.WORKER, name="w1"))

        agent = store.get_agent_by_name("run-1", "w1")
        assert agent is not None
        assert agent.role == AgentRole.WORKER

    def test_get_by_name_not_found(self, store):
        store.save_run(Run(run_id="run-1"))
        assert store.get_agent_by_name("run-1", "nope") is None


class TestMessageCRUD:
    def test_save_and_list(self, store):
        store.save_run(Run(run_id="run-1"))
        msg = Message(
            run_id="run-1", sender="orch", recipient="w1",
            type=MessageType.DISPATCH, payload='{"test": true}',
        )
        store.save_message(msg)

        messages = store.get_messages("run-1")
        assert len(messages) == 1
        assert messages[0].sender == "orch"

    def test_pending_messages(self, store):
        store.save_run(Run(run_id="run-1"))
        msg = Message(
            run_id="run-1", sender="orch", recipient="w1",
            type=MessageType.DISPATCH, payload="{}",
        )
        store.save_message(msg)

        pending = store.get_pending_messages("run-1", "w1")
        assert len(pending) == 1

    def test_count_messages(self, store):
        store.save_run(Run(run_id="run-1"))
        m1 = Message(run_id="run-1", sender="a", recipient="b", payload="{}")
        m2 = Message(run_id="run-1", sender="b", recipient="a", payload="{}")
        m2.mark_delivered()
        store.save_message(m1)
        store.save_message(m2)

        counts = store.count_messages("run-1")
        assert counts.get("PENDING") == 1
        assert counts.get("DELIVERED") == 1

    def test_message_with_task_correlation(self, store):
        store.save_run(Run(run_id="run-1"))
        msg = Message(
            run_id="run-1", sender="orch", recipient="w1",
            type=MessageType.DISPATCH, payload="{}",
            task_id="task-1", context_id="ctx-1",
        )
        store.save_message(msg)

        loaded = store.get_messages("run-1")
        assert len(loaded) == 1
        assert loaded[0].task_id == "task-1"
        assert loaded[0].context_id == "ctx-1"

    def test_message_without_task_correlation(self, store):
        store.save_run(Run(run_id="run-1"))
        msg = Message(
            run_id="run-1", sender="orch", recipient="w1",
            type=MessageType.DISPATCH, payload="{}",
        )
        store.save_message(msg)

        loaded = store.get_messages("run-1")
        assert loaded[0].task_id is None
        assert loaded[0].context_id is None

    def test_save_message_after_legacy_schema_migration(self, tmp_path):
        db_path = tmp_path / "legacy.sqlite3"
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'CREATED',
                workspace_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE agents (
                agent_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                role TEXT NOT NULL,
                name TEXT NOT NULL,
                surface_id TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE messages (
                message_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                payload TEXT NOT NULL,
                artifact_path TEXT,
                created_at TEXT NOT NULL,
                delivered_at TEXT
            );
            """
        )
        conn.commit()
        conn.close()

        store = StateStore(db_path)
        try:
            store.save_run(Run(run_id="run-1"))
            store.save_message(
                Message(
                    run_id="run-1",
                    sender="orch",
                    recipient="w1",
                    type=MessageType.DISPATCH,
                    payload="{}",
                    task_id="task-1",
                    context_id="ctx-1",
                )
            )

            loaded = store.get_messages("run-1")
            assert loaded[0].task_id == "task-1"
            assert loaded[0].context_id == "ctx-1"
        finally:
            store.close()


class TestTaskCRUD:
    def test_save_and_get(self, store):
        store.save_run(Run(run_id="run-1"))
        task = Task(task_id="task-1", context_id="ctx-1", run_id="run-1")
        store.save_task(task)

        loaded = store.get_task("task-1")
        assert loaded is not None
        assert loaded.task_id == "task-1"
        assert loaded.context_id == "ctx-1"
        assert loaded.state == TaskState.SUBMITTED

    def test_get_nonexistent(self, store):
        assert store.get_task("nonexistent") is None

    def test_get_tasks(self, store):
        store.save_run(Run(run_id="run-1"))
        store.save_task(Task(task_id="t1", context_id="c1", run_id="run-1"))
        store.save_task(Task(task_id="t2", context_id="c2", run_id="run-1"))

        tasks = store.get_tasks("run-1")
        assert len(tasks) == 2

    def test_get_active_task(self, store):
        store.save_run(Run(run_id="run-1"))
        t1 = Task(task_id="t1", context_id="ctx-1", run_id="run-1", state=TaskState.COMPLETED)
        t2 = Task(task_id="t2", context_id="ctx-1", run_id="run-1", state=TaskState.WORKING)
        store.save_task(t1)
        store.save_task(t2)

        active = store.get_active_task("run-1", "ctx-1")
        assert active is not None
        assert active.task_id == "t2"

    def test_save_with_history(self, store):
        store.save_run(Run(run_id="run-1"))
        task = Task(task_id="t1", context_id="c1", run_id="run-1")
        task.add_message("msg-1")
        task.add_message("msg-2")
        store.save_task(task)

        loaded = store.get_task("t1")
        assert loaded.history_message_ids == ["msg-1", "msg-2"]

    def test_update_state(self, store):
        store.save_run(Run(run_id="run-1"))
        task = Task(task_id="t1", context_id="c1", run_id="run-1")
        store.save_task(task)

        task.transition_to(TaskState.WORKING)
        store.save_task(task)

        loaded = store.get_task("t1")
        assert loaded.state == TaskState.WORKING

    def test_history_preserved_after_state_update(self, store):
        store.save_run(Run(run_id="run-1"))
        task = Task(task_id="t1", context_id="c1", run_id="run-1")
        task.add_message("msg-1")
        task.add_message("msg-2")
        store.save_task(task)

        task.transition_to(TaskState.WORKING)
        store.save_task(task)

        loaded = store.get_task("t1")
        assert loaded.state == TaskState.WORKING
        assert loaded.history_message_ids == ["msg-1", "msg-2"]


class TestLegacySchemaMigration:
    def test_existing_messages_table_is_upgraded_for_correlation_fields(self, tmp_path):
        db_path = tmp_path / "legacy.sqlite3"
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'CREATED',
                workspace_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE agents (
                agent_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                role TEXT NOT NULL,
                name TEXT NOT NULL,
                surface_id TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE messages (
                message_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                payload TEXT NOT NULL,
                artifact_path TEXT,
                created_at TEXT NOT NULL,
                delivered_at TEXT
            );
            """
        )
        conn.commit()
        conn.close()

        store = StateStore(db_path)
        try:
            store.save_run(Run(run_id="run-1"))
            store.save_message(
                Message(
                    run_id="run-1",
                    sender="orch",
                    recipient="w1",
                    type=MessageType.DISPATCH,
                    payload="{}",
                    task_id="task-1",
                    context_id="ctx-1",
                )
            )
            loaded = store.get_messages("run-1")
            assert loaded[0].task_id == "task-1"
            assert loaded[0].context_id == "ctx-1"
        finally:
            store.close()


class TestArtifactCRUD:
    def test_save_and_get(self, store):
        store.save_run(Run(run_id="run-1"))
        store.save_task(Task(task_id="t1", context_id="c1", run_id="run-1"))

        art = Artifact(
            artifact_id="art-1", task_id="t1",
            parts=[Part(kind="text", text="result data")],
        )
        store.save_artifact(art)

        loaded = store.get_artifacts("t1")
        assert len(loaded) == 1
        assert loaded[0].artifact_id == "art-1"
        assert loaded[0].parts[0].text == "result data"
        assert loaded[0].parts[0].kind == "text"

    def test_multiple_artifacts(self, store):
        store.save_run(Run(run_id="run-1"))
        store.save_task(Task(task_id="t1", context_id="c1", run_id="run-1"))

        store.save_artifact(Artifact(artifact_id="a1", task_id="t1", parts=[Part(text="r1")]))
        store.save_artifact(Artifact(artifact_id="a2", task_id="t1", parts=[Part(text="r2")]))

        loaded = store.get_artifacts("t1")
        assert len(loaded) == 2

    def test_artifact_with_data_part(self, store):
        store.save_run(Run(run_id="run-1"))
        store.save_task(Task(task_id="t1", context_id="c1", run_id="run-1"))

        art = Artifact(
            artifact_id="a1", task_id="t1",
            parts=[Part(kind="data", data={"key": "val"}, media_type="application/json")],
        )
        store.save_artifact(art)

        loaded = store.get_artifacts("t1")
        assert loaded[0].parts[0].kind == "data"
        assert loaded[0].parts[0].data == {"key": "val"}
        assert loaded[0].parts[0].media_type == "application/json"

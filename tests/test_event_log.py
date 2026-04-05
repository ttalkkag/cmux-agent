"""EventLog 테스트."""

from cmux_agent.domain.events import (
    artifact_created,
    run_created,
    agent_registered,
    task_created,
    task_state_changed,
)
from cmux_agent.infrastructure.event_log import EventLog


class TestEventLog:
    def test_append_and_read(self, tmp_path):
        log = EventLog(tmp_path / "events.jsonl")
        log.append(run_created("run-1", "ws-1"))
        log.append(agent_registered("run-1", "orch", "ORCHESTRATOR"))

        events = log.read_all()
        assert len(events) == 2
        assert events[0]["event"] == "run.created"
        assert events[1]["event"] == "agent.registered"

    def test_filter_by_run_id(self, tmp_path):
        log = EventLog(tmp_path / "events.jsonl")
        log.append(run_created("run-1"))
        log.append(run_created("run-2"))

        events = log.read_all("run-1")
        assert len(events) == 1

    def test_empty_log(self, tmp_path):
        log = EventLog(tmp_path / "events.jsonl")
        assert log.read_all() == []


class TestTaskEventFactories:
    def test_task_created(self):
        evt = task_created("run-1", "task-1", "ctx-1")
        assert evt.event == "task.created"
        assert evt.run_id == "run-1"
        assert evt.data["task_id"] == "task-1"
        assert evt.data["context_id"] == "ctx-1"

    def test_task_state_changed(self):
        evt = task_state_changed("run-1", "task-1", "WORKING", "COMPLETED")
        assert evt.event == "task.state_changed"
        assert evt.data["task_id"] == "task-1"
        assert evt.data["old"] == "WORKING"
        assert evt.data["new"] == "COMPLETED"

    def test_artifact_created(self):
        evt = artifact_created("run-1", "task-1", "art-1")
        assert evt.event == "artifact.created"
        assert evt.data["task_id"] == "task-1"
        assert evt.data["artifact_id"] == "art-1"

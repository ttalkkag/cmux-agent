"""PromptBuilder 테스트."""

import shutil

import pytest

from cmux_agent.application.prompting import PromptBuilder, _TEMPLATE_FILENAMES
from cmux_agent.domain.models import Agent, AgentRole, MessageType

PROMPTS_DIR = str(
    (pytest.importorskip("pathlib").Path(__file__).resolve().parent.parent / ".cmux" / "prompts")
)


class TestPromptBuilder:
    def setup_method(self):
        self.builder = PromptBuilder(
            outbox_path="/tmp/outbox",
            inbox_base="/tmp/inbox",
            prompts_dir=PROMPTS_DIR,
        )

    def test_dispatch_delivery(self):
        result = self.builder.build_delivery(
            sender="orchestrator",
            recipient="worker-1",
            msg_type=MessageType.DISPATCH,
            payload={"message": "build login API"},
        )
        assert result["type"] == "dispatch"
        assert result["task"] == "build login API"
        assert "result" in result["artifact_format"]["type"]

    def test_result_delivery(self):
        result = self.builder.build_delivery(
            sender="worker-1",
            recipient="orchestrator",
            msg_type=MessageType.RESULT,
            payload={"message": "login API done"},
        )
        assert result["type"] == "result"
        assert result["result"] == "login API done"
        assert "dispatch" in result["artifact_format"]["type"]

    def test_initial_orchestrator(self):
        workers = [
            Agent(run_id="r", role=AgentRole.WORKER, name="worker-1"),
            Agent(run_id="r", role=AgentRole.WORKER, name="worker-2"),
        ]
        result = self.builder.build_initial_orchestrator(workers)
        assert result["role"] == "orchestrator"
        assert len(result["workers"]) == 2
        assert "dispatch" in result["artifact_format"]["type"]

    def test_initial_worker(self):
        result = self.builder.build_initial_worker("worker-1")
        assert result["role"] == "worker"
        assert result["name"] == "worker-1"
        assert "result" in result["artifact_format"]["type"]

    def test_injection_prompt_dispatch(self):
        result = self.builder.build_injection_prompt(
            sender="orchestrator",
            recipient="worker-1",
            msg_type=MessageType.DISPATCH,
            payload={"message": "implement auth"},
        )
        assert "orchestrator" in result
        assert "implement auth" in result
        assert "result" in result

    def test_injection_prompt_result(self):
        result = self.builder.build_injection_prompt(
            sender="worker-1",
            recipient="orchestrator",
            msg_type=MessageType.RESULT,
            payload={"message": "auth done"},
        )
        assert "worker-1" in result
        assert "auth done" in result
        assert "dispatch" in result

    def test_write_protocol_files(self, tmp_path):
        workers = [
            Agent(run_id="r", role=AgentRole.ORCHESTRATOR, name="orchestrator"),
            Agent(run_id="r", role=AgentRole.WORKER, name="worker-1"),
            Agent(run_id="r", role=AgentRole.WORKER, name="worker-2"),
        ]
        self.builder.write_protocol_files(tmp_path, workers)

        orch_file = tmp_path / "ORCHESTRATOR.md"
        assert orch_file.exists()
        content = orch_file.read_text()
        assert "orchestrator" in content
        assert "worker-1" in content
        assert "worker-2" in content

        w1_file = tmp_path / "WORKER-1.md"
        assert w1_file.exists()
        assert "worker-1" in w1_file.read_text()

        w2_file = tmp_path / "WORKER-2.md"
        assert w2_file.exists()


class TestPromptTemplates:
    def test_check_prompts_missing(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        builder = PromptBuilder("/tmp/outbox", "/tmp/inbox", str(prompts_dir))
        missing = builder.check_prompts()
        assert set(missing) == set(_TEMPLATE_FILENAMES)

    def test_check_prompts_all_present(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        for name in _TEMPLATE_FILENAMES:
            (prompts_dir / name).write_text("template")
        builder = PromptBuilder("/tmp/outbox", "/tmp/inbox", str(prompts_dir))
        assert builder.check_prompts() == []

    def test_load_template_missing_raises(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        builder = PromptBuilder("/tmp/outbox", "/tmp/inbox", str(prompts_dir))
        import pytest
        with pytest.raises(FileNotFoundError):
            builder._load_template("orchestrator.md")

    def test_custom_protocol_template(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        shutil.copytree(PROMPTS_DIR, prompts_dir)
        (prompts_dir / "orchestrator.md").write_text(
            "CUSTOM orchestrator\noutbox=$outbox\nworkers=$worker_list",
        )

        builder = PromptBuilder("/tmp/outbox", "/tmp/inbox", str(prompts_dir))
        workers = [
            Agent(run_id="r", role=AgentRole.WORKER, name="worker-1"),
        ]
        builder.write_protocol_files(tmp_path, workers)

        content = (tmp_path / "ORCHESTRATOR.md").read_text()
        assert "CUSTOM orchestrator" in content
        assert "outbox=/tmp/outbox" in content
        assert "worker-1" in content

    def test_custom_worker_template(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        shutil.copytree(PROMPTS_DIR, prompts_dir)
        (prompts_dir / "worker.md").write_text(
            "CUSTOM $worker_name\noutbox=$outbox",
        )

        builder = PromptBuilder("/tmp/outbox", "/tmp/inbox", str(prompts_dir))
        workers = [
            Agent(run_id="r", role=AgentRole.WORKER, name="worker-1"),
        ]
        builder.write_protocol_files(tmp_path, workers)

        content = (tmp_path / "WORKER-1.md").read_text()
        assert "CUSTOM worker-1" in content
        assert "outbox=/tmp/outbox" in content

    def test_custom_injection_dispatch(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "dispatch.md").write_text(
            "TASK from ${sender}: $message\nreply to $outbox",
        )

        builder = PromptBuilder("/tmp/outbox", "/tmp/inbox", str(prompts_dir))
        result = builder.build_injection_prompt(
            sender="orchestrator",
            recipient="worker-1",
            msg_type=MessageType.DISPATCH,
            payload={"message": "do stuff"},
        )
        assert "TASK from orchestrator: do stuff" in result
        assert "reply to /tmp/outbox" in result

    def test_custom_injection_result(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "result.md").write_text(
            "RESULT from ${sender}: $message",
        )

        builder = PromptBuilder("/tmp/outbox", "/tmp/inbox", str(prompts_dir))
        result = builder.build_injection_prompt(
            sender="worker-1",
            recipient="orchestrator",
            msg_type=MessageType.RESULT,
            payload={"message": "done"},
        )
        assert "RESULT from worker-1: done" in result

"""PromptBuilder 테스트."""

from pathlib import Path

from cmux_agent.application.prompting import PromptBuilder
from cmux_agent.domain.models import Agent, AgentRole, MessageType

PROMPTS_DIR = str(
    Path(__file__).resolve().parent.parent / ".cmux" / "prompts"
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

    def test_injection_prompt_dispatch(self):
        result = self.builder.build_injection_prompt(
            sender="orchestrator",
            recipient="worker-1",
            msg_type=MessageType.DISPATCH,
            payload={"message": "implement auth"},
        )
        assert "orchestrator" in result
        assert "implement auth" in result
        assert "worker" in result  # worker.md 내용 포함

    def test_injection_prompt_result(self):
        result = self.builder.build_injection_prompt(
            sender="worker-1",
            recipient="orchestrator",
            msg_type=MessageType.RESULT,
            payload={"message": "auth done"},
        )
        assert "worker-1" in result
        assert "auth done" in result

    def test_injection_dispatch_includes_worker_prompt(self):
        result = self.builder.build_injection_prompt(
            sender="orchestrator",
            recipient="worker-1",
            msg_type=MessageType.DISPATCH,
            payload={"message": "build API"},
        )
        # worker.md 프로토콜 내용이 포함되어야 함
        assert ".cmux/outbox" in result
        assert "result" in result

    def test_read_prompt(self):
        content = self.builder.read_prompt("orchestrator.md")
        assert content is not None
        assert "orchestrator" in content

    def test_read_prompt_missing(self):
        content = self.builder.read_prompt("nonexistent.md")
        assert content is None

    def test_read_prompt_no_dir(self):
        builder = PromptBuilder("/tmp/outbox", "/tmp/inbox")
        assert builder.read_prompt("orchestrator.md") is None

    def test_custom_worker_prompt(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "worker.md").write_text("CUSTOM worker protocol")

        builder = PromptBuilder("/tmp/outbox", "/tmp/inbox", str(prompts_dir))
        result = builder.build_injection_prompt(
            sender="orchestrator",
            recipient="worker-1",
            msg_type=MessageType.DISPATCH,
            payload={"message": "do stuff"},
        )
        assert "CUSTOM worker protocol" in result
        assert "do stuff" in result

"""PromptBuilder 테스트."""

from cmux_agent.application.prompting import PromptBuilder
from cmux_agent.domain.models import Agent, AgentRole, MessageType


class TestPromptBuilder:
    def setup_method(self):
        self.builder = PromptBuilder(
            outbox_path="/tmp/outbox",
            inbox_base="/tmp/inbox",
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

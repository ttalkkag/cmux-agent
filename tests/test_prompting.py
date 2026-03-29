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

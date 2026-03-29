"""EventLog 테스트."""

from cmux_agent.domain.events import run_created, agent_registered
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

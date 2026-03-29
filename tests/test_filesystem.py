"""AgentFileSystem 테스트."""

import json

from cmux_agent.infrastructure.filesystem import AgentFileSystem


class TestAgentFileSystem:
    def test_init_creates_directories(self, tmp_path):
        fs = AgentFileSystem(tmp_path / ".agent")
        fs.init()

        assert fs.outbox.exists()
        assert fs.inbox.exists()
        assert fs.processed.exists()
        assert fs.failed.exists()

    def test_create_inbox(self, tmp_path):
        fs = AgentFileSystem(tmp_path / ".agent")
        fs.init()
        inbox = fs.create_inbox("worker-1")
        assert inbox.exists()
        assert inbox.name == "worker-1"

    def test_write_to_inbox(self, tmp_path):
        fs = AgentFileSystem(tmp_path / ".agent")
        fs.init()

        data = {"type": "dispatch", "message": "hello"}
        path = fs.write_to_inbox("worker-1", "msg-1", data)

        assert path.exists()
        content = json.loads(path.read_text())
        assert content["message"] == "hello"

    def test_move_to_processed(self, tmp_path):
        fs = AgentFileSystem(tmp_path / ".agent")
        fs.init()

        artifact = fs.outbox / "test.json"
        artifact.write_text("{}")

        dst = fs.move_to_processed(artifact)
        assert dst.exists()
        assert not artifact.exists()

    def test_move_to_failed(self, tmp_path):
        fs = AgentFileSystem(tmp_path / ".agent")
        fs.init()

        artifact = fs.outbox / "bad.json"
        artifact.write_text("{}")

        dst = fs.move_to_failed(artifact)
        assert dst.exists()
        assert dst.parent == fs.failed

    def test_list_outbox(self, tmp_path):
        fs = AgentFileSystem(tmp_path / ".agent")
        fs.init()

        (fs.outbox / "a.json").write_text("{}")
        (fs.outbox / "b.xml").write_text("<x/>")
        (fs.outbox / ".hidden.json").write_text("{}")
        (fs.outbox / "c.txt").write_text("nope")

        files = fs.list_outbox()
        names = [f.name for f in files]
        assert "a.json" in names
        assert "b.xml" in names
        assert ".hidden.json" not in names
        assert "c.txt" not in names

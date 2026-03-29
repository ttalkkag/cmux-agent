"""ArtifactWatcher 테스트."""

import json
import time
from pathlib import Path

from cmux_agent.application.watcher import ArtifactWatcher, validate_artifact


class FakeConsumer:
    def __init__(self):
        self.artifacts: list[tuple[Path, dict]] = []

    def handle_artifact(self, artifact_path: Path, data: dict) -> None:
        self.artifacts.append((artifact_path, data))


class TestValidateArtifact:
    def test_valid(self):
        data = {
            "type": "dispatch",
            "sender": "orchestrator",
            "recipient": "worker-1",
            "message": "do stuff",
        }
        assert validate_artifact(data) is None

    def test_missing_fields(self):
        assert validate_artifact({"type": "dispatch"}) is not None

    def test_invalid_type(self):
        data = {
            "type": "unknown",
            "sender": "a",
            "recipient": "b",
            "message": "x",
        }
        assert "알 수 없는 type" in validate_artifact(data)


class TestArtifactWatcher:
    def test_process_existing(self, tmp_path):
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        artifact = outbox / "test.json"
        artifact.write_text(json.dumps({
            "type": "dispatch",
            "sender": "orch",
            "recipient": "w1",
            "message": "hello",
        }))

        consumer = FakeConsumer()
        watcher = ArtifactWatcher(outbox, consumer)
        watcher._process_existing()

        assert len(consumer.artifacts) == 1
        assert consumer.artifacts[0][1]["sender"] == "orch"

    def test_background_watcher(self, tmp_path):
        outbox = tmp_path / "outbox"
        outbox.mkdir()

        consumer = FakeConsumer()
        watcher = ArtifactWatcher(outbox, consumer)
        watcher.start_background()

        time.sleep(0.3)

        # 파일 생성 → watcher가 감지
        artifact = outbox / "new.json"
        artifact.write_text(json.dumps({
            "type": "result",
            "sender": "w1",
            "recipient": "orch",
            "message": "done",
        }))

        time.sleep(1.0)
        watcher.stop()

        assert len(consumer.artifacts) == 1

    def test_ignores_non_json(self, tmp_path):
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        (outbox / "readme.txt").write_text("not json")

        consumer = FakeConsumer()
        watcher = ArtifactWatcher(outbox, consumer)
        watcher._process_existing()

        assert len(consumer.artifacts) == 0

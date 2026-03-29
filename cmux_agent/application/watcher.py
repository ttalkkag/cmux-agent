"""Artifact Watcher — outbox 디렉토리 감시 및 트리거."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from watchdog.observers.api import BaseObserver

logger = logging.getLogger(__name__)

VALID_EXTENSIONS = {".json", ".xml"}
REQUIRED_FIELDS = {"type", "sender", "recipient", "message"}


class ArtifactConsumer(Protocol):
    """Watcher가 감지한 artifact를 처리하는 인터페이스."""

    def handle_artifact(self, artifact_path: Path, data: dict) -> None: ...


def validate_artifact(data: dict) -> str | None:
    """artifact의 유효성을 검증한다. 오류 시 사유 문자열 반환."""
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        return f"필수 필드 누락: {missing}"
    if data["type"] not in ("dispatch", "result"):
        return f"알 수 없는 type: {data['type']}"
    return None


class _OutboxHandler(FileSystemEventHandler):
    """outbox 디렉토리의 파일 생성 이벤트를 처리한다."""

    def __init__(self, consumer: ArtifactConsumer) -> None:
        self._consumer = consumer

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        self._try_process(Path(event.src_path))

    def on_moved(self, event: FileMovedEvent) -> None:
        if event.is_directory:
            return
        self._try_process(Path(event.dest_path))

    def _try_process(self, path: Path) -> None:
        if path.suffix not in VALID_EXTENSIONS:
            return
        if path.name.startswith("."):
            return
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("artifact 파싱 실패: %s — %s", path, exc)
            return

        error = validate_artifact(data)
        if error:
            logger.warning("artifact 검증 실패: %s — %s", path, error)
            self._consumer.handle_artifact(path, {"_error": error, **data})
            return

        logger.info("artifact 처리: %s", path.name)
        self._consumer.handle_artifact(path, data)


class ArtifactWatcher:
    """outbox 디렉토리를 감시하여 artifact를 감지하고 consumer에 전달한다."""

    def __init__(self, outbox_path: str | Path, consumer: ArtifactConsumer) -> None:
        self._outbox = Path(outbox_path)
        self._consumer = consumer
        self._observer: BaseObserver | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """감시를 시작한다 (포그라운드, 블로킹)."""
        self._outbox.mkdir(parents=True, exist_ok=True)

        # 기존 미처리 파일 처리
        self._process_existing()

        handler = _OutboxHandler(self._consumer)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._outbox), recursive=False)
        self._observer.start()
        logger.info("watcher 시작: %s", self._outbox)

        try:
            self._stop_event.wait()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def start_background(self) -> None:
        """감시를 백그라운드 스레드에서 시작한다."""
        self._outbox.mkdir(parents=True, exist_ok=True)
        self._process_existing()

        handler = _OutboxHandler(self._consumer)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._outbox), recursive=False)
        self._observer.daemon = True
        self._observer.start()
        logger.info("watcher 시작 (백그라운드): %s", self._outbox)

    def stop(self) -> None:
        """감시를 중지한다."""
        self._stop_event.set()
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=5)
            logger.info("watcher 중지")

    def _process_existing(self) -> None:
        handler = _OutboxHandler(self._consumer)
        for path in sorted(self._outbox.iterdir()):
            if path.suffix in VALID_EXTENSIONS and not path.name.startswith("."):
                handler._try_process(path)

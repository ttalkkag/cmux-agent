"""Inbox / Outbox 파일 시스템 관리."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path


class AgentFileSystem:
    """`.cmux/` 디렉토리 구조를 관리한다."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir)
        self.outbox = self.base / "outbox"
        self.inbox = self.base / "inbox"
        self.processed = self.base / "processed"
        self.failed = self.processed / "failed"
        self.prompts = self.base / "prompts"

    def init(self) -> None:
        for d in (self.outbox, self.inbox, self.processed, self.failed, self.prompts):
            d.mkdir(parents=True, exist_ok=True)

    def create_inbox(self, agent_name: str) -> Path:
        inbox_dir = self.inbox / agent_name
        inbox_dir.mkdir(parents=True, exist_ok=True)
        return inbox_dir

    def write_to_inbox(self, recipient: str, message_id: str, data: dict) -> Path:
        inbox_dir = self.create_inbox(recipient)
        path = inbox_dir / f"{message_id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.rename(path)
        return path

    def move_to_processed(self, artifact_path: str | Path) -> Path:
        src = Path(artifact_path)
        dst = self.processed / src.name
        if dst.exists():
            dst = self.processed / f"{int(time.time())}-{src.name}"
        shutil.move(str(src), str(dst))
        return dst

    def move_to_failed(self, artifact_path: str | Path) -> Path:
        src = Path(artifact_path)
        dst = self.failed / src.name
        if dst.exists():
            dst = self.failed / f"{int(time.time())}-{src.name}"
        shutil.move(str(src), str(dst))
        return dst

    def list_outbox(self) -> list[Path]:
        if not self.outbox.exists():
            return []
        return sorted(
            p for p in self.outbox.iterdir()
            if p.suffix in (".json", ".xml") and not p.name.startswith(".")
        )

    @property
    def db_path(self) -> Path:
        return self.base / "control-plane.sqlite3"

    @property
    def event_log_path(self) -> Path:
        return self.base / "events.jsonl"

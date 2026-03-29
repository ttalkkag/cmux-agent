"""Append-only JSONL 이벤트 로그."""

from __future__ import annotations

import json
from pathlib import Path

from cmux_agent.domain.events import DomainEvent


class EventLog:
    """JSONL 파일에 도메인 이벤트를 기록한다."""

    def __init__(self, log_path: str | Path) -> None:
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: DomainEvent) -> None:
        record = {
            "ts": event.ts.isoformat(),
            "event": event.event,
            "run_id": event.run_id,
            "data": event.data,
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_all(self, run_id: str | None = None) -> list[dict]:
        if not self._path.exists():
            return []
        events = []
        with self._path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if run_id is None or record.get("run_id") == run_id:
                    events.append(record)
        return events

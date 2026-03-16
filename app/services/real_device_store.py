"""Simple file-backed event store for externally reported real-device telemetry."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_DIR = PROJECT_ROOT / "storage"
REAL_DEVICE_EVENTS_PATH = STORAGE_DIR / "real_device_events.jsonl"


def append_real_device_event(payload: dict[str, Any], event_path: Path | None = None) -> dict[str, Any]:
    path = event_path or REAL_DEVICE_EVENTS_PATH
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    event = {
        "instance_id": payload.get("instance_id") or payload.get("device_id"),
        "timestamp": payload.get("timestamp") or datetime.now().isoformat(timespec="seconds"),
        "metrics": payload.get("metrics") or {},
        "meta": payload.get("meta") or {},
    }
    if not event["instance_id"]:
        raise ValueError("Telemetry payload must contain instance_id or device_id.")

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    return event


def load_real_device_history(
    instance_id: str,
    limit: int = 120,
    event_path: Path | None = None,
) -> list[dict[str, Any]]:
    path = event_path or REAL_DEVICE_EVENTS_PATH
    if not path.exists():
        return []

    matched: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("instance_id") == instance_id:
                matched.append(event)

    return matched[-limit:]

"""MQTT payload helpers for future Aliyun IoT integration."""

from __future__ import annotations

import json
from typing import Any

from app.models import DeviceReading


def build_mqtt_payload(reading: DeviceReading) -> str:
    return json.dumps(reading.to_dict(), ensure_ascii=False)


def parse_mqtt_payload(payload: str | bytes) -> dict[str, Any]:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    return json.loads(payload)

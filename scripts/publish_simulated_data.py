"""Publish simulated device readings to an MQTT broker."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.mqtt_adapter import build_mqtt_payload
from app.data.simulator import generate_batch


MQTT_HOST = os.getenv("MQTT_HOST", "broker.emqx.io")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sgcc/demo/device/status")


def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    for reading in generate_batch(device_count=5):
        payload = build_mqtt_payload(reading)
        client.publish(MQTT_TOPIC, payload)
        print(f"published to {MQTT_TOPIC}: {payload}")
        time.sleep(1)

    client.disconnect()


if __name__ == "__main__":
    main()

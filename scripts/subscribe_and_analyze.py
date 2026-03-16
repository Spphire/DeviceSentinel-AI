"""Subscribe to an MQTT topic, analyze incoming device readings, and print reports."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paho.mqtt.client as mqtt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.report_generator import generate_report
from app.data.mqtt_adapter import parse_mqtt_payload
from app.mpc.skill_adapter import invoke_local_skill


MQTT_HOST = os.getenv("MQTT_HOST", "broker.emqx.io")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sgcc/demo/device/status")


def on_connect(client: mqtt.Client, _userdata, _flags, reason_code, _properties) -> None:
    print(f"connected to MQTT broker, reason_code={reason_code}")
    client.subscribe(MQTT_TOPIC)
    print(f"subscribed topic: {MQTT_TOPIC}")


def on_message(_client: mqtt.Client, _userdata, msg: mqtt.MQTTMessage) -> None:
    payload = parse_mqtt_payload(msg.payload)
    analysis_result = invoke_local_skill(payload)
    report = generate_report(analysis_result)
    print("\n=== incoming payload ===")
    print(payload)
    print("=== analysis result ===")
    print(analysis_result)
    print("=== AI report ===")
    print(report)


def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()

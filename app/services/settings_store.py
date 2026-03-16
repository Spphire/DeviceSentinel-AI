"""Persist dashboard settings and configured devices to local storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import DashboardDeviceConfig
from app.services.gateway_service import DEFAULT_GATEWAY_PATH, normalize_gateway_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_DIR = PROJECT_ROOT / "storage"
SETTINGS_PATH = STORAGE_DIR / "dashboard_settings.json"


DEFAULT_SETTINGS = {
    "system": {
        "history_window": 60,
        "refresh_interval_seconds": 2,
        "developer_mode": False,
        "show_structured_analysis": False,
        "agent_mode": "local_rule",
        "agent_model": "gpt-5.4",
        "agent_use_local_fallback": True,
    },
    "gateway": {
        "listen_host": "127.0.0.1",
        "port": 10570,
        "path": DEFAULT_GATEWAY_PATH,
        "advertised_host": "",
    },
    "devices": [
        {
            "instance_id": "sgcc-demo-001",
            "name": "SGCC 配电箱 1",
            "template_id": "sgcc_simulated",
            "simulation_profile": "stable",
        },
        {
            "instance_id": "sgcc-demo-002",
            "name": "SGCC 配电箱 2",
            "template_id": "sgcc_simulated",
            "simulation_profile": "intermittent_fault",
        },
        {
            "instance_id": "temp-demo-001",
            "name": "温湿度传感器 1",
            "template_id": "temp_humidity_simulated",
            "simulation_profile": "stable",
        },
    ],
}


def _extract_legacy_gateway_settings(devices: list[dict[str, Any]]) -> dict[str, Any]:
    for device in devices:
        communication = device.get("communication") or {}
        if not communication:
            continue
        return {
            "listen_host": communication.get("host", DEFAULT_SETTINGS["gateway"]["listen_host"]),
            "port": communication.get("port", DEFAULT_SETTINGS["gateway"]["port"]),
            "path": communication.get("path", DEFAULT_SETTINGS["gateway"]["path"]),
        }
    return {}


def _normalize_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    system = {**DEFAULT_SETTINGS["system"], **payload.get("system", {})}
    devices = payload.get("devices") or DEFAULT_SETTINGS["devices"]
    gateway = normalize_gateway_config(
        {
            **DEFAULT_SETTINGS["gateway"],
            **_extract_legacy_gateway_settings(devices),
            **(payload.get("gateway") or {}),
        }
    ).to_dict()
    normalized_devices: list[dict[str, Any]] = []

    for index, device in enumerate(devices):
        normalized_devices.append(
            {
                "instance_id": device.get("instance_id") or f"device-{index + 1}",
                "name": device.get("name") or f"设备 {index + 1}",
                "template_id": device.get("template_id") or "sgcc_simulated",
                "simulation_profile": device.get("simulation_profile"),
            }
        )

    return {"system": system, "gateway": gateway, "devices": normalized_devices}


def load_dashboard_settings(settings_path: Path | None = None) -> dict[str, Any]:
    path = settings_path or SETTINGS_PATH
    if not path.exists():
        return _normalize_settings(DEFAULT_SETTINGS)

    payload = json.loads(path.read_text(encoding="utf-8"))
    return _normalize_settings(payload)


def save_dashboard_settings(payload: dict[str, Any], settings_path: Path | None = None) -> None:
    path = settings_path or SETTINGS_PATH
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_settings(payload)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")


def build_device_config(payload: dict[str, Any]) -> DashboardDeviceConfig:
    return DashboardDeviceConfig(
        instance_id=payload["instance_id"],
        name=payload["name"],
        template_id=payload["template_id"],
        simulation_profile=payload.get("simulation_profile"),
    )


def build_settings_device_payload(config: DashboardDeviceConfig) -> dict[str, Any]:
    return config.to_dict()


def create_new_device_payload(template_id: str) -> dict[str, Any]:
    short_token = uuid4().hex[:8]
    return {
        "instance_id": f"{template_id}-{short_token}",
        "name": "新设备",
        "template_id": template_id,
        "simulation_profile": None,
    }

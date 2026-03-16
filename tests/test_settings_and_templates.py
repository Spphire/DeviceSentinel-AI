from pathlib import Path

from app.services.settings_store import load_dashboard_settings, save_dashboard_settings
from app.services.template_service import load_device_templates


def test_load_device_templates_reads_expected_templates():
    templates = load_device_templates()

    assert "sgcc_simulated" in templates
    assert "personal_pc_real" in templates
    assert "temp_humidity_simulated" in templates
    assert templates["sgcc_simulated"].source_type == "simulated"
    assert len(templates["temp_humidity_simulated"].metrics) == 2
    assert [metric.metric_id for metric in templates["personal_pc_real"].metrics] == [
        "cpu_usage",
        "memory_usage",
        "disk_activity",
        "gpu_usage",
    ]


def test_dashboard_settings_roundtrip(tmp_path: Path):
    settings_path = tmp_path / "dashboard_settings.json"
    payload = {
        "system": {
            "history_window": 80,
            "refresh_interval_seconds": 3,
            "developer_mode": True,
            "show_structured_analysis": True,
        },
        "devices": [
            {
                "instance_id": "pc-001",
                "name": "我的电脑",
                "template_id": "personal_pc_real",
                "simulation_profile": None,
                "communication": {"protocol": "http_json", "host": "127.0.0.1", "port": 10570, "path": "/telemetry"},
            }
        ],
    }

    save_dashboard_settings(payload, settings_path=settings_path)
    loaded = load_dashboard_settings(settings_path=settings_path)

    assert loaded["system"]["history_window"] == 80
    assert loaded["devices"][0]["instance_id"] == "pc-001"
    assert loaded["devices"][0]["communication"]["port"] == 10570


def test_dashboard_settings_defaults_to_sixty_minute_history(tmp_path: Path):
    settings_path = tmp_path / "dashboard_settings.json"

    loaded = load_dashboard_settings(settings_path=settings_path)

    assert loaded["system"]["history_window"] == 60

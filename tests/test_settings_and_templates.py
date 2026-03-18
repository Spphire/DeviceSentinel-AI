from pathlib import Path

from app.services.settings_store import load_dashboard_settings, save_dashboard_settings
from app.services.template_service import load_device_templates


def test_load_device_templates_reads_expected_templates():
    templates = load_device_templates()

    assert "sgcc_simulated" in templates
    assert "switchgear_simulated" in templates
    assert "distribution_transformer_simulated" in templates
    assert "mobile_device_real" in templates
    assert "personal_pc_real" in templates
    assert "temp_humidity_simulated" in templates
    assert templates["sgcc_simulated"].source_type == "simulated"
    assert [metric.metric_id for metric in templates["switchgear_simulated"].metrics] == [
        "contact_temperature",
        "cabinet_temperature",
        "load_current",
    ]
    assert [metric.metric_id for metric in templates["distribution_transformer_simulated"].metrics] == [
        "voltage",
        "current",
        "load_rate",
        "imbalance_ratio",
    ]
    assert len(templates["temp_humidity_simulated"].metrics) == 2
    assert [metric.metric_id for metric in templates["mobile_device_real"].metrics] == [
        "battery_level",
        "battery_temperature",
        "memory_usage",
        "storage_usage",
    ]
    assert [metric.metric_id for metric in templates["personal_pc_real"].metrics] == [
        "cpu_usage",
        "memory_usage",
        "disk_activity",
        "gpu_usage",
        "gpu_memory_usage",
    ]


def test_dashboard_settings_roundtrip(tmp_path: Path):
    settings_path = tmp_path / "dashboard_settings.json"
    payload = {
        "system": {
            "history_window": 80,
            "refresh_interval_seconds": 3,
            "developer_mode": True,
            "show_structured_analysis": True,
            "agent_mode": "real_llm",
            "agent_model": "gpt-5.4",
            "agent_use_local_fallback": False,
        },
        "gateway": {
            "listen_host": "0.0.0.0",
            "port": 11570,
            "path": "/telemetry",
            "advertised_host": "192.168.1.20",
        },
        "devices": [
            {
                "instance_id": "pc-001",
                "name": "我的电脑",
                "template_id": "personal_pc_real",
                "simulation_profile": None,
            }
        ],
    }

    save_dashboard_settings(payload, settings_path=settings_path)
    loaded = load_dashboard_settings(settings_path=settings_path)

    assert loaded["system"]["history_window"] == 80
    assert loaded["system"]["agent_mode"] == "real_llm"
    assert loaded["gateway"]["listen_host"] == "0.0.0.0"
    assert loaded["gateway"]["port"] == 11570
    assert loaded["devices"][0]["instance_id"] == "pc-001"
    assert "communication" not in loaded["devices"][0]


def test_dashboard_settings_defaults_to_sixty_minute_history(tmp_path: Path):
    settings_path = tmp_path / "dashboard_settings.json"

    loaded = load_dashboard_settings(settings_path=settings_path)

    assert loaded["system"]["history_window"] == 60
    assert loaded["system"]["agent_mode"] == "local_rule"
    assert loaded["gateway"]["path"] == "/telemetry"


def test_dashboard_settings_migrates_legacy_device_communication_to_global_gateway(tmp_path: Path):
    settings_path = tmp_path / "dashboard_settings.json"
    legacy_payload = {
        "system": {
            "history_window": 60,
            "refresh_interval_seconds": 2,
        },
        "devices": [
            {
                "instance_id": "pc-legacy-001",
                "name": "旧版电脑",
                "template_id": "personal_pc_real",
                "simulation_profile": None,
                "communication": {"protocol": "http_json", "host": "127.0.0.1", "port": 12570, "path": "/telemetry"},
            }
        ],
    }

    save_dashboard_settings(legacy_payload, settings_path=settings_path)
    loaded = load_dashboard_settings(settings_path=settings_path)

    assert loaded["gateway"]["listen_host"] == "127.0.0.1"
    assert loaded["gateway"]["port"] == 12570
    assert loaded["devices"][0]["instance_id"] == "pc-legacy-001"
    assert "communication" not in loaded["devices"][0]

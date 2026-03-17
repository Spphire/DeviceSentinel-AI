from app.services.settings_store import save_dashboard_settings
from scripts.check_agent_backends import build_smoke_context


def test_build_smoke_context_uses_selected_device_and_generates_devices(tmp_path):
    settings_path = tmp_path / "dashboard_settings.json"
    save_dashboard_settings(
        {
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
                "path": "/telemetry",
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
                    "instance_id": "temp-demo-001",
                    "name": "温湿度传感器 1",
                    "template_id": "temp_humidity_simulated",
                    "simulation_profile": "stable",
                },
            ],
        },
        settings_path=settings_path,
    )

    settings, context = build_smoke_context(
        settings_path=settings_path,
        selected_device_id="temp-demo-001",
        seed=11,
    )

    assert settings["devices"][0]["instance_id"] == "sgcc-demo-001"
    assert context["selected_device_id"] == "temp-demo-001"
    assert "sgcc-demo-001" in context["devices"]
    assert "temp-demo-001" in context["devices"]

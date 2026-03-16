import json

from app.services.status_publisher import (
    build_status_snapshot,
    extract_snapshot_from_event_payload,
    render_status_site,
)


def test_build_status_snapshot_includes_counts_and_devices(monkeypatch):
    monkeypatch.setattr("app.services.status_publisher.load_gateway_manager_status", lambda: None)
    settings = {
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
            }
        ],
    }

    snapshot = build_status_snapshot(settings=settings, seed=11)

    assert snapshot["counts"]["total_devices"] == 1
    assert snapshot["devices"][0]["instance_id"] == "sgcc-demo-001"
    assert snapshot["devices"][0]["metrics"]
    assert snapshot["gateway"]["client_target"]["path"] == "/telemetry"


def test_extract_snapshot_from_event_payload_reads_repository_dispatch_payload():
    event = {
        "client_payload": {
            "snapshot": {
                "generated_at": "2026-03-17T01:00:00",
                "counts": {"total_devices": 1},
            }
        }
    }

    snapshot = extract_snapshot_from_event_payload(event)

    assert snapshot["counts"]["total_devices"] == 1


def test_render_status_site_writes_html_and_json(tmp_path):
    snapshot = {
        "generated_at": "2026-03-17T01:00:00",
        "title": "DeviceSentinel AI Status",
        "counts": {
            "total_devices": 1,
            "online_devices": 1,
            "offline_devices": 0,
            "abnormal_devices": 0,
            "high_risk_devices": 0,
        },
        "gateway": {
            "running": True,
            "manager_pid": 1234,
            "listen_host": "127.0.0.1",
            "port": 10570,
            "path": "/telemetry",
            "client_target": {"host": "127.0.0.1", "port": 10570, "path": "/telemetry"},
            "last_error": None,
        },
        "agent": {
            "mode": "local_ollama",
            "model": "qwen2.5:7b",
            "use_local_fallback": True,
        },
        "focus_devices": [],
        "devices": [
            {
                "instance_id": "demo-001",
                "name": "演示设备",
                "template_id": "sgcc_simulated",
                "template_name": "SGCC 模拟设备",
                "category_name": "SGCC 配电设备",
                "source_type": "simulated",
                "device_status": "online",
                "status": "normal",
                "risk_level": "low",
                "last_heartbeat": "2026-03-17T01:00:00",
                "metrics": [{"metric_id": "temperature", "label": "温度", "unit": "℃", "value": 36.5}],
                "issue_count": 0,
                "issues": [],
                "summary": "运行平稳",
                "report_excerpt": "设备运行平稳。",
            }
        ],
        "recent_events": [],
    }

    render_status_site(snapshot, tmp_path)

    assert (tmp_path / "index.html").exists()
    data = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert data["gateway"]["port"] == 10570

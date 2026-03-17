import json

from app.services.gateway_service import (
    GatewayConfig,
    build_gateway_client_target,
    load_gateway_manager_status,
    normalize_gateway_config,
    probe_gateway_health,
    write_gateway_manager_status,
    ManagedTelemetryGateway,
)


def test_normalize_gateway_config_adds_leading_slash():
    config = normalize_gateway_config({"listen_host": "127.0.0.1", "port": 10570, "path": "telemetry"})

    assert config.path == "/telemetry"


def test_build_gateway_client_target_prefers_advertised_host():
    target = build_gateway_client_target(
        GatewayConfig(
            listen_host="0.0.0.0",
            port=10570,
            path="/telemetry",
            advertised_host="192.168.1.50",
        )
    )

    assert target == {
        "host": "192.168.1.50",
        "port": 10570,
        "path": "/telemetry",
    }


def test_managed_gateway_start_returns_effective_ephemeral_port():
    gateway = ManagedTelemetryGateway()
    try:
        config = gateway.start(
            GatewayConfig(
                listen_host="127.0.0.1",
                port=0,
                path="/telemetry",
            )
        )

        assert config.port > 0
        assert gateway.is_running()
    finally:
        gateway.stop()


def test_probe_gateway_health_reports_ok():
    gateway = ManagedTelemetryGateway()
    try:
        config = gateway.start(
            GatewayConfig(
                listen_host="127.0.0.1",
                port=0,
                path="/telemetry",
            )
        )

        health = probe_gateway_health(config, timeout=2.0)

        assert health["ok"] is True
        assert health["status_code"] == 200
        assert health["response"]["service"] == "telemetry_gateway"
    finally:
        gateway.stop()


def test_load_gateway_manager_status_marks_dead_manager_stale(tmp_path, monkeypatch):
    status_path = tmp_path / "gateway_manager_status.json"
    write_gateway_manager_status(
        running=True,
        config=GatewayConfig(listen_host="127.0.0.1", port=10570, path="/telemetry"),
        desired_config=GatewayConfig(listen_host="127.0.0.1", port=10570, path="/telemetry"),
        health={"ok": True, "checked_at": "2026-03-17T10:00:00", "url": "http://127.0.0.1:10570/health"},
        status_path=status_path,
    )
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["manager_pid"] = 424242
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr("app.services.gateway_service.is_process_alive", lambda pid: False)

    status = load_gateway_manager_status(status_path=status_path)

    assert status["running"] is False
    assert status["stale_status"] is True
    assert status["manager_pid_alive"] is False
    assert status["health"]["ok"] is False
    assert "进程已退出" in status["health"]["error"]

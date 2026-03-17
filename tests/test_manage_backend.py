from scripts.manage_backend import build_backend_command, format_status_summary


def test_build_backend_command_includes_forwarded_options():
    command = build_backend_command(
        settings_path=r"C:\repo\storage\dashboard_settings.json",
        poll_interval=2.5,
        health_timeout=3.0,
    )

    assert command[1].endswith("run_backend.py")
    assert "--poll-interval" in command
    assert "--health-timeout" in command
    assert "--settings-path" in command


def test_format_status_summary_mentions_gateway_and_health():
    summary = format_status_summary(
        {
            "running": True,
            "manager_pid": 4321,
            "stale_status": False,
            "gateway": {
                "listen_host": "127.0.0.1",
                "port": 10570,
                "path": "/telemetry",
                "advertised_host": "",
            },
            "health": {
                "ok": True,
            },
        }
    )

    assert "运行中" in summary
    assert "127.0.0.1:10570/telemetry" in summary
    assert "健康状态=健康" in summary

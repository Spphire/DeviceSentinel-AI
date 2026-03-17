from scripts.personal_pc_client_app import (
    PersonalPcClientConfig,
    build_arg_parser,
    build_autostart_command,
    build_gateway_preview,
    compute_retry_delay,
    get_startup_path,
    is_autostart_enabled,
    load_saved_config,
    merge_config_with_args,
    save_config,
    set_autostart_enabled,
)


def test_personal_pc_client_app_accepts_headless_gateway_args():
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "--instance-id",
            "pc-001",
            "--gateway-host",
            "192.168.1.15",
            "--gateway-port",
            "11570",
            "--gateway-path",
            "/telemetry",
            "--interval",
            "2",
            "--headless",
            "--start-minimized",
            "--once",
        ]
    )

    assert args.instance_id == "pc-001"
    assert args.gateway_host == "192.168.1.15"
    assert args.gateway_port == 11570
    assert args.gateway_path == "/telemetry"
    assert args.interval == 2
    assert args.headless is True
    assert args.start_minimized is True
    assert args.once is True


def test_merge_config_with_args_prefers_cli_values():
    parser = build_arg_parser()
    saved = PersonalPcClientConfig(
        instance_id="pc-saved",
        gateway_host="127.0.0.1",
        gateway_port=10570,
        gateway_path="/telemetry",
        interval=5,
    )

    args = parser.parse_args(
        [
            "--instance-id",
            "pc-cli",
            "--gateway-host",
            "10.0.0.8",
            "--gateway-port",
            "12570",
            "--gateway-path",
            "/push",
            "--interval",
            "1",
        ]
    )

    merged = merge_config_with_args(saved, args)

    assert merged.instance_id == "pc-cli"
    assert merged.gateway_host == "10.0.0.8"
    assert merged.gateway_port == 12570
    assert merged.gateway_path == "/push"
    assert merged.interval == 1


def test_save_and_load_personal_pc_client_app_config(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    config = PersonalPcClientConfig(
        instance_id="pc-config-001",
        gateway_host="192.168.1.30",
        gateway_port=14570,
        gateway_path="/telemetry",
        interval=3,
    )

    save_config(config)
    loaded = load_saved_config()

    assert loaded == config


def test_compute_retry_delay_grows_with_failures_and_caps():
    assert compute_retry_delay(5, 1) == 5
    assert compute_retry_delay(5, 2) == 10
    assert compute_retry_delay(5, 9) == 20
    assert compute_retry_delay(12, 4) == 30


def test_build_gateway_preview_uses_current_config():
    preview = build_gateway_preview(
        PersonalPcClientConfig(
            instance_id="pc-001",
            gateway_host="192.168.1.15",
            gateway_port=11570,
            gateway_path="/telemetry",
            interval=2,
        )
    )

    assert preview == "http://192.168.1.15:11570/telemetry"


def test_build_autostart_command_uses_pythonw_for_script_mode(tmp_path):
    python_exe = tmp_path / "python.exe"
    pythonw_exe = tmp_path / "pythonw.exe"
    script_path = tmp_path / "personal_pc_client_app.py"
    python_exe.write_text("", encoding="utf-8")
    pythonw_exe.write_text("", encoding="utf-8")
    script_path.write_text("", encoding="utf-8")

    command = build_autostart_command(
        executable_path=str(python_exe),
        script_path=str(script_path),
        start_minimized=True,
    )

    assert "pythonw.exe" in command
    assert "personal_pc_client_app.py" in command
    assert "--start-minimized" in command


def test_set_autostart_enabled_creates_and_removes_launcher(tmp_path):
    startup_path = tmp_path / "Startup" / "DeviceSentinel-Personal-PC-Client.cmd"
    set_autostart_enabled(
        True,
        startup_path=startup_path,
        executable_path=r"C:\Python311\python.exe",
        script_path=r"C:\repo\scripts\personal_pc_client_app.py",
    )

    assert startup_path.exists()
    assert is_autostart_enabled(startup_path) is True
    assert "--start-minimized" in startup_path.read_text(encoding="utf-8")

    set_autostart_enabled(False, startup_path=startup_path)

    assert startup_path.exists() is False
    assert is_autostart_enabled(startup_path) is False

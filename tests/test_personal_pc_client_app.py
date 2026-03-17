from scripts.personal_pc_client_app import (
    PersonalPcClientConfig,
    build_arg_parser,
    load_saved_config,
    merge_config_with_args,
    save_config,
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
            "--once",
        ]
    )

    assert args.instance_id == "pc-001"
    assert args.gateway_host == "192.168.1.15"
    assert args.gateway_port == 11570
    assert args.gateway_path == "/telemetry"
    assert args.interval == 2
    assert args.headless is True
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

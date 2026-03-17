from pathlib import Path

from scripts.mobile_device_client import (
    _collect_storage_usage,
    _parse_meminfo_usage,
    _parse_termux_battery_status,
    build_arg_parser,
    collect_metrics,
    collect_simulated_metrics,
)


def test_parse_termux_battery_status_reads_percentage_and_temperature():
    metrics = _parse_termux_battery_status('{"percentage": 67, "temperature": 33.8}')

    assert metrics == {
        "battery_level": 67.0,
        "battery_temperature": 33.8,
    }


def test_parse_meminfo_usage_prefers_memavailable():
    usage = _parse_meminfo_usage(
        "\n".join(
            [
                "MemTotal:        8000000 kB",
                "MemFree:         1000000 kB",
                "MemAvailable:    2500000 kB",
            ]
        )
    )

    assert usage == 68.8


def test_collect_storage_usage_calculates_ratio(monkeypatch):
    monkeypatch.setattr(
        "scripts.mobile_device_client.shutil.disk_usage",
        lambda _path: (1000, 450, 550),
    )

    usage = _collect_storage_usage(str(Path.home()))

    assert usage == 45.0


def test_mobile_device_client_accepts_gateway_argument_names():
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "--instance-id",
            "mobile-001",
            "--gateway-host",
            "192.168.1.13",
            "--gateway-port",
            "14570",
            "--gateway-path",
            "/mobile",
            "--simulate",
        ]
    )

    assert args.gateway_host == "192.168.1.13"
    assert args.gateway_port == 14570
    assert args.gateway_path == "/mobile"
    assert args.simulate is True


def test_collect_simulated_metrics_stays_within_expected_range():
    metrics = collect_simulated_metrics()

    assert 0.0 <= metrics["battery_level"] <= 100.0
    assert 0.0 <= metrics["memory_usage"] <= 100.0
    assert 0.0 <= metrics["storage_usage"] <= 100.0


def test_collect_metrics_uses_manual_overrides(monkeypatch):
    parser = build_arg_parser()
    args = parser.parse_args(
        [
            "--instance-id",
            "mobile-001",
            "--battery-level",
            "12",
            "--battery-temperature",
            "43",
            "--memory-usage",
            "88",
            "--storage-usage",
            "77",
        ]
    )
    monkeypatch.setattr("scripts.mobile_device_client._collect_termux_metrics", lambda *_args, **_kwargs: {})

    metrics, mode = collect_metrics(args)

    assert mode == "manual"
    assert metrics["battery_level"] == 12.0
    assert metrics["battery_temperature"] == 43.0
    assert metrics["memory_usage"] == 88.0
    assert metrics["storage_usage"] == 77.0

import subprocess

from scripts.personal_pc_client import (
    _collect_nvidia_gpu_metrics,
    _parse_nvidia_smi_gpu_metrics,
    build_arg_parser,
    collect_metrics,
)
from scripts.temp_humidity_client import build_arg_parser as build_temp_humidity_arg_parser


def test_parse_nvidia_smi_gpu_metrics_returns_peak_usage_and_vram_ratio():
    output = "7, 2000, 10000\n12, 6000, 12000\n3, 1000, 12000"

    metrics = _parse_nvidia_smi_gpu_metrics(output)

    assert metrics == {
        "gpu_usage": 12.0,
        "gpu_memory_usage": 50.0,
    }


def test_collect_nvidia_gpu_metrics_uses_peak_sample(monkeypatch):
    outputs = iter(["7, 1000, 12000", "92, 9000, 12000", "11, 3000, 12000"])

    monkeypatch.setattr(
        "scripts.personal_pc_client._run_command",
        lambda *_args, **_kwargs: next(outputs),
    )
    monkeypatch.setattr("scripts.personal_pc_client.time.sleep", lambda *_args, **_kwargs: None)

    metrics = _collect_nvidia_gpu_metrics()

    assert metrics == {
        "gpu_usage": 92.0,
        "gpu_memory_usage": 75.0,
    }


def test_collect_metrics_falls_back_to_powershell_gpu_when_nvidia_smi_unavailable(monkeypatch):
    monkeypatch.setattr(
        "scripts.personal_pc_client._run_powershell",
        lambda _command: '{"cpu_usage": 20.0, "memory_usage": 30.0, "disk_activity": 40.0, "gpu_usage": 55.0}',
    )
    monkeypatch.setattr(
        "scripts.personal_pc_client._run_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError("nvidia-smi not found")),
    )

    metrics = collect_metrics()

    assert metrics["cpu_usage"] == 20.0
    assert metrics["gpu_usage"] == 55.0
    assert metrics["gpu_memory_usage"] == 0.0


def test_collect_metrics_prefers_nvidia_smi_gpu_usage(monkeypatch):
    monkeypatch.setattr(
        "scripts.personal_pc_client._run_powershell",
        lambda _command: '{"cpu_usage": 20.0, "memory_usage": 30.0, "disk_activity": 40.0, "gpu_usage": 3.0}',
    )
    outputs = iter(["7, 1000, 12000", "92, 9000, 12000", "11, 3000, 12000"])
    monkeypatch.setattr(
        "scripts.personal_pc_client._run_command",
        lambda *_args, **_kwargs: next(outputs),
    )
    monkeypatch.setattr("scripts.personal_pc_client.time.sleep", lambda *_args, **_kwargs: None)

    metrics = collect_metrics()

    assert metrics["gpu_usage"] == 92.0
    assert metrics["gpu_memory_usage"] == 75.0


def test_personal_pc_client_accepts_gateway_argument_names():
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "--instance-id",
            "pc-001",
            "--gateway-host",
            "192.168.1.10",
            "--gateway-port",
            "11570",
            "--gateway-path",
            "/pc",
        ]
    )

    assert args.gateway_host == "192.168.1.10"
    assert args.gateway_port == 11570
    assert args.gateway_path == "/pc"


def test_personal_pc_client_keeps_legacy_host_arguments_compatible():
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "--instance-id",
            "pc-001",
            "--host",
            "192.168.1.11",
            "--port",
            "12570",
            "--path",
            "/legacy",
        ]
    )

    assert args.gateway_host == "192.168.1.11"
    assert args.gateway_port == 12570
    assert args.gateway_path == "/legacy"


def test_temp_humidity_client_accepts_gateway_argument_names():
    parser = build_temp_humidity_arg_parser()

    args = parser.parse_args(
        [
            "--instance-id",
            "sensor-001",
            "--gateway-host",
            "192.168.1.12",
            "--gateway-port",
            "13570",
            "--gateway-path",
            "/env",
        ]
    )

    assert args.gateway_host == "192.168.1.12"
    assert args.gateway_port == 13570
    assert args.gateway_path == "/env"

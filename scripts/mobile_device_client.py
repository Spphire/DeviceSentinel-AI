"""Push mobile device telemetry to the dashboard gateway.

The client supports three modes:
1. Real Android/Termux collection (default when `termux-battery-status` is available)
2. Manual metric override via command-line flags
3. Desktop/mobile demo mode via `--simulate`
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.telemetry_client import add_gateway_arguments, build_gateway_url, build_payload, send_payload


TERMUX_BATTERY_COMMAND = ["termux-battery-status"]


def _run_command(command: list[str], timeout: int = 10) -> str:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
    )
    return completed.stdout.strip()


def _round_percentage(value: float) -> float:
    return round(min(max(value, 0.0), 100.0), 1)


def _parse_termux_battery_status(output: str) -> dict[str, float]:
    payload = json.loads(output)
    level = payload.get("percentage", payload.get("level"))
    if level is None:
        raise ValueError("termux-battery-status output missing percentage.")

    temperature = payload.get("temperature")
    return {
        "battery_level": _round_percentage(float(level)),
        "battery_temperature": round(float(temperature), 1) if temperature is not None else 0.0,
    }


def _parse_meminfo_usage(meminfo: str) -> float:
    values: dict[str, float] = {}
    for raw_line in meminfo.splitlines():
        if ":" not in raw_line:
            continue
        key, raw_value = raw_line.split(":", 1)
        number_text = raw_value.strip().split()[0]
        try:
            values[key] = float(number_text)
        except ValueError:
            continue

    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    free = values.get("MemFree")
    if not total:
        raise ValueError("meminfo missing MemTotal.")

    baseline_available = available if available is not None else free
    if baseline_available is None:
        raise ValueError("meminfo missing MemAvailable and MemFree.")

    used_ratio = (total - baseline_available) / total * 100
    return _round_percentage(used_ratio)


def _collect_storage_usage(storage_path: str | None = None) -> float:
    candidate = Path(storage_path) if storage_path else _get_default_storage_path()
    usage = shutil.disk_usage(candidate)
    total = usage.total if hasattr(usage, "total") else usage[0]
    used = usage.used if hasattr(usage, "used") else usage[1]
    if total <= 0:
        return 0.0
    return _round_percentage(used / total * 100)


def _get_default_storage_path() -> Path:
    if Path("/data").exists():
        return Path("/data")
    return Path.home()


def _collect_termux_metrics(storage_path: str | None = None) -> dict[str, float]:
    battery = _parse_termux_battery_status(_run_command(TERMUX_BATTERY_COMMAND, timeout=10))
    meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")
    return {
        **battery,
        "memory_usage": _parse_meminfo_usage(meminfo),
        "storage_usage": _collect_storage_usage(storage_path),
    }


def collect_simulated_metrics() -> dict[str, float]:
    return {
        "battery_level": _round_percentage(random.uniform(28.0, 96.0)),
        "battery_temperature": round(random.uniform(29.0, 41.5), 1),
        "memory_usage": _round_percentage(random.uniform(32.0, 89.0)),
        "storage_usage": _round_percentage(random.uniform(35.0, 84.0)),
    }


def _has_manual_metric_overrides(args: argparse.Namespace) -> bool:
    return any(
        value is not None
        for value in [
            args.battery_level,
            args.battery_temperature,
            args.memory_usage,
            args.storage_usage,
        ]
    )


def _build_manual_metrics(args: argparse.Namespace) -> dict[str, float]:
    return {
        "battery_level": _round_percentage(float(args.battery_level if args.battery_level is not None else 76.0)),
        "battery_temperature": round(
            float(args.battery_temperature if args.battery_temperature is not None else 34.5),
            1,
        ),
        "memory_usage": _round_percentage(float(args.memory_usage if args.memory_usage is not None else 58.0)),
        "storage_usage": _round_percentage(float(args.storage_usage if args.storage_usage is not None else 61.0)),
    }


def collect_metrics(args: argparse.Namespace) -> tuple[dict[str, float], str]:
    if _has_manual_metric_overrides(args):
        return _build_manual_metrics(args), "manual"
    if args.simulate:
        return collect_simulated_metrics(), "simulate"
    return _collect_termux_metrics(args.storage_path), "termux"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mobile device telemetry client.")
    add_gateway_arguments(parser)
    parser.add_argument("--simulate", action="store_true", help="Use generated demo metrics instead of real mobile metrics.")
    parser.add_argument(
        "--storage-path",
        help="Optional storage path used when computing storage usage. Defaults to /data or the current home directory.",
    )
    parser.add_argument("--battery-level", type=float, help="Manual battery level override (0-100).")
    parser.add_argument("--battery-temperature", type=float, help="Manual battery temperature override (C).")
    parser.add_argument("--memory-usage", type=float, help="Manual memory usage override (0-100).")
    parser.add_argument("--storage-usage", type=float, help="Manual storage usage override (0-100).")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    url = build_gateway_url(
        gateway_host=args.gateway_host,
        gateway_port=args.gateway_port,
        gateway_path=args.gateway_path,
    )

    while True:
        metrics, mode = collect_metrics(args)
        payload = build_payload(
            instance_id=args.instance_id,
            metrics=metrics,
            client_name="mobile_device_client",
            meta={"mode": mode},
        )
        print(send_payload(url=url, payload=payload))

        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()

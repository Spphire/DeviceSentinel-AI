"""Collect local PC metrics and push them to the telemetry gateway."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from urllib import request


def send_payload(url: str, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url=url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=5) as response:
        print(response.read().decode("utf-8"))


def _run_powershell(command: str) -> float:
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=True,
    )
    return round(float(completed.stdout.strip()), 1)


def collect_metrics() -> dict:
    cpu_usage = _run_powershell(
        "(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples[0].CookedValue"
    )
    memory_usage = _run_powershell(
        "$os = Get-CimInstance Win32_OperatingSystem; "
        "[math]::Round((($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize) * 100, 1)"
    )
    disk_usage = _run_powershell(
        "$disk = Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\"; "
        "[math]::Round((($disk.Size - $disk.FreeSpace) / $disk.Size) * 100, 1)"
    )
    return {
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
        "disk_usage": disk_usage,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Personal PC telemetry client.")
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10570)
    parser.add_argument("--path", default="/telemetry")
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}{args.path}"
    while True:
        payload = {
            "instance_id": args.instance_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "metrics": collect_metrics(),
            "meta": {"client": "personal_pc_client"},
        }
        send_payload(url=url, payload=payload)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()

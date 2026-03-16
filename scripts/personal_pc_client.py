"""Collect local PC metrics and push them to the telemetry gateway."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from urllib import request


POWERSHELL_METRIC_SCRIPT = r"""
$cpu = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq '_Total' } |
    Select-Object -First 1
$os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
$disk = Get-CimInstance Win32_PerfFormattedData_PerfDisk_LogicalDisk -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq '_Total' } |
    Select-Object -First 1
$gpuSamples = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine -ErrorAction SilentlyContinue

$gpuUsage = 0.0
if ($gpuSamples) {
    $maxPerGpu = @{}
    foreach ($sample in $gpuSamples) {
        $usage = [double]$sample.UtilizationPercentage
        if ($sample.Name -match 'phys_(\d+)') {
            $gpuId = $Matches[1]
            if (-not $maxPerGpu.ContainsKey($gpuId) -or $usage -gt $maxPerGpu[$gpuId]) {
                $maxPerGpu[$gpuId] = $usage
            }
        }
    }

    if ($maxPerGpu.Count -gt 0) {
        $gpuUsage = ($maxPerGpu.Values | Measure-Object -Maximum).Maximum
    } else {
        $gpuUsage = ($gpuSamples | Measure-Object -Property UtilizationPercentage -Maximum).Maximum
    }
}

$memoryUsage = (($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize) * 100
$diskActivity = if ($disk) { [double]$disk.PercentDiskTime } else { 0.0 }
$cpuUsage = if ($cpu) { [double]$cpu.PercentProcessorTime } else { 0.0 }

$result = @{
    cpu_usage = [math]::Round([math]::Min([math]::Max($cpuUsage, 0), 100), 1)
    memory_usage = [math]::Round([math]::Min([math]::Max($memoryUsage, 0), 100), 1)
    disk_activity = [math]::Round([math]::Min([math]::Max($diskActivity, 0), 100), 1)
    gpu_usage = [math]::Round([math]::Min([math]::Max([double]$gpuUsage, 0), 100), 1)
}

$result | ConvertTo-Json -Compress
"""


def send_payload(url: str, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url=url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=5) as response:
        print(response.read().decode("utf-8"))


def _run_powershell(command: str) -> str:
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def collect_metrics() -> dict:
    payload = json.loads(_run_powershell(POWERSHELL_METRIC_SCRIPT))
    return {
        "cpu_usage": round(float(payload.get("cpu_usage", 0.0)), 1),
        "memory_usage": round(float(payload.get("memory_usage", 0.0)), 1),
        "disk_activity": round(float(payload.get("disk_activity", 0.0)), 1),
        "gpu_usage": round(float(payload.get("gpu_usage", 0.0)), 1),
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

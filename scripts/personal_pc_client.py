"""Collect local PC metrics and push them to the dashboard telemetry gateway."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.telemetry_client import add_gateway_arguments, build_gateway_url, build_payload, send_payload


NVIDIA_SMI_QUERY = [
    "nvidia-smi",
    "--query-gpu=utilization.gpu,memory.used,memory.total",
    "--format=csv,noheader,nounits",
]

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

def _run_command(command: list[str], timeout: int = 10) -> str:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
        creationflags=creationflags,
    )
    return completed.stdout.strip()


def _run_powershell(command: str) -> str:
    return _run_command(["powershell", "-NoProfile", "-Command", command])


def _parse_nvidia_smi_gpu_metrics(output: str) -> dict[str, float] | None:
    gpu_usage_values: list[float] = []
    gpu_memory_usage_values: list[float] = []

    for line in output.splitlines():
        columns = [column.strip() for column in line.split(",")]
        if len(columns) < 3:
            continue

        try:
            gpu_usage = float(columns[0])
            memory_used = float(columns[1])
            memory_total = float(columns[2])
        except ValueError:
            continue

        gpu_usage_values.append(gpu_usage)
        if memory_total > 0:
            gpu_memory_usage_values.append((memory_used / memory_total) * 100)

    if not gpu_usage_values:
        return None
    return {
        "gpu_usage": max(gpu_usage_values),
        "gpu_memory_usage": max(gpu_memory_usage_values) if gpu_memory_usage_values else 0.0,
    }


def _collect_nvidia_gpu_metrics(sample_count: int = 3, sample_interval_seconds: float = 0.25) -> dict[str, float] | None:
    samples: list[dict[str, float]] = []
    for index in range(sample_count):
        try:
            output = _run_command(NVIDIA_SMI_QUERY, timeout=5)
        except (FileNotFoundError, subprocess.SubprocessError):
            return None

        metrics = _parse_nvidia_smi_gpu_metrics(output)
        if metrics is not None:
            samples.append(metrics)

        if index < sample_count - 1:
            time.sleep(sample_interval_seconds)

    if not samples:
        return None

    return {
        "gpu_usage": round(min(max(max(sample["gpu_usage"] for sample in samples), 0.0), 100.0), 1),
        "gpu_memory_usage": round(
            min(max(max(sample["gpu_memory_usage"] for sample in samples), 0.0), 100.0),
            1,
        ),
    }


def collect_metrics() -> dict:
    nvidia_gpu_metrics = _collect_nvidia_gpu_metrics()
    payload = json.loads(_run_powershell(POWERSHELL_METRIC_SCRIPT))
    if nvidia_gpu_metrics is None:
        gpu_usage = round(float(payload.get("gpu_usage", 0.0)), 1)
        gpu_memory_usage = 0.0
    else:
        gpu_usage = nvidia_gpu_metrics["gpu_usage"]
        gpu_memory_usage = nvidia_gpu_metrics["gpu_memory_usage"]

    return {
        "cpu_usage": round(float(payload.get("cpu_usage", 0.0)), 1),
        "memory_usage": round(float(payload.get("memory_usage", 0.0)), 1),
        "disk_activity": round(float(payload.get("disk_activity", 0.0)), 1),
        "gpu_usage": gpu_usage,
        "gpu_memory_usage": gpu_memory_usage,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Personal PC telemetry client.")
    add_gateway_arguments(parser)
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
        payload = build_payload(
            instance_id=args.instance_id,
            metrics=collect_metrics(),
            client_name="personal_pc_client",
            meta={"platform": "windows"},
        )
        print(send_payload(url=url, payload=payload))
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()

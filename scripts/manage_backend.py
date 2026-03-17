"""Convenience wrapper for starting, stopping, and inspecting the backend manager."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.gateway_service import (
    GATEWAY_MANAGER_PID_PATH,
    STORAGE_DIR,
    build_gateway_health_url,
    is_process_alive,
    load_gateway_manager_status,
    normalize_gateway_config,
)


BACKEND_LOG_PATH = STORAGE_DIR / "backend_manager.log"
RUN_BACKEND_SCRIPT = PROJECT_ROOT / "scripts" / "run_backend.py"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the shared telemetry backend manager.")
    parser.add_argument("command", choices=["start", "stop", "restart", "status"])
    parser.add_argument("--settings-path")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--health-timeout", type=float, default=1.5)
    parser.add_argument("--wait-timeout", type=float, default=8.0)
    return parser


def build_backend_command(
    *,
    settings_path: str | None = None,
    poll_interval: float = 1.0,
    health_timeout: float = 1.5,
) -> list[str]:
    command = [
        sys.executable,
        str(RUN_BACKEND_SCRIPT),
        "--poll-interval",
        str(poll_interval),
        "--health-timeout",
        str(health_timeout),
    ]
    if settings_path:
        command.extend(["--settings-path", settings_path])
    return command


def read_manager_pid(pid_path: Path | None = None) -> int | None:
    path = pid_path or GATEWAY_MANAGER_PID_PATH
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def start_backend_manager(
    *,
    settings_path: str | None = None,
    poll_interval: float = 1.0,
    health_timeout: float = 1.5,
    wait_timeout: float = 8.0,
) -> dict:
    existing_pid = read_manager_pid()
    if is_process_alive(existing_pid):
        return {
            "ok": True,
            "action": "already_running",
            "pid": existing_pid,
            "summary": format_status_summary(load_gateway_manager_status()),
        }

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with BACKEND_LOG_PATH.open("a", encoding="utf-8") as log_file:
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess,
            "CREATE_NEW_PROCESS_GROUP",
            0,
        )
        process = subprocess.Popen(
            build_backend_command(
                settings_path=settings_path,
                poll_interval=poll_interval,
                health_timeout=health_timeout,
            ),
            cwd=PROJECT_ROOT,
            stdout=log_file,
            stderr=log_file,
            creationflags=creationflags,
        )

    deadline = time.time() + max(wait_timeout, 1.0)
    status = None
    while time.time() < deadline:
        status = load_gateway_manager_status()
        if status and status.get("manager_pid") == process.pid:
            return {
                "ok": bool(status.get("running")),
                "action": "started",
                "pid": process.pid,
                "summary": format_status_summary(status),
            }
        time.sleep(0.4)

    return {
        "ok": False,
        "action": "timeout",
        "pid": process.pid,
        "summary": "已启动 backend manager 进程，但在等待超时内未检测到状态文件更新。",
    }


def stop_backend_manager(*, wait_timeout: float = 8.0) -> dict:
    pid = read_manager_pid()
    if not is_process_alive(pid):
        return {"ok": True, "action": "already_stopped", "pid": pid, "summary": "当前未检测到 backend manager 在运行。"}

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True)

    deadline = time.time() + max(wait_timeout, 1.0)
    while time.time() < deadline:
        if not is_process_alive(pid):
            return {"ok": True, "action": "stopped", "pid": pid, "summary": "backend manager 已停止。"}
        time.sleep(0.4)

    return {"ok": False, "action": "timeout", "pid": pid, "summary": "已发送停止请求，但进程仍未退出。"}


def format_status_summary(status: dict | None) -> str:
    if not status:
        return "当前未检测到 backend manager 状态文件。"

    gateway = normalize_gateway_config(status.get("gateway"))
    health = status.get("health") or {}
    health_text = "健康" if health.get("ok") else "未探测" if not health else "异常"
    stale_suffix = "；状态文件已过期" if status.get("stale_status") else ""
    return (
        f"运行状态：{'运行中' if status.get('running') else '未运行'}"
        f"；PID={status.get('manager_pid') or '-'}"
        f"；监听 {gateway.listen_host}:{gateway.port}{gateway.path}"
        f"；探针 {build_gateway_health_url(gateway)}"
        f"；健康状态={health_text}{stale_suffix}"
    )


def print_result(result: dict) -> None:
    print(f"[{result.get('action')}] pid={result.get('pid') or '-'}")
    print(result.get("summary", ""))


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.command == "status":
        print(format_status_summary(load_gateway_manager_status()))
        return

    if args.command == "start":
        result = start_backend_manager(
            settings_path=args.settings_path,
            poll_interval=args.poll_interval,
            health_timeout=args.health_timeout,
            wait_timeout=args.wait_timeout,
        )
        print_result(result)
        if not result["ok"]:
            raise SystemExit(1)
        return

    if args.command == "stop":
        result = stop_backend_manager(wait_timeout=args.wait_timeout)
        print_result(result)
        if not result["ok"]:
            raise SystemExit(1)
        return

    stop_result = stop_backend_manager(wait_timeout=args.wait_timeout)
    print_result(stop_result)
    if not stop_result["ok"]:
        raise SystemExit(1)
    start_result = start_backend_manager(
        settings_path=args.settings_path,
        poll_interval=args.poll_interval,
        health_timeout=args.health_timeout,
        wait_timeout=args.wait_timeout,
    )
    print_result(start_result)
    if not start_result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

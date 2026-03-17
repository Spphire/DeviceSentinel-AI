"""Run the backend manager that owns the shared telemetry gateway."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.gateway_service import (
    GatewayConfig,
    ManagedTelemetryGateway,
    clear_gateway_manager_status,
    normalize_gateway_config,
    probe_gateway_health,
    write_gateway_manager_status,
)
from app.services.settings_store import load_dashboard_settings


def _load_desired_gateway_config(settings_path: Path | None = None) -> GatewayConfig:
    settings = load_dashboard_settings(settings_path=settings_path)
    return normalize_gateway_config(settings.get("gateway"))


def _apply_gateway_config(
    gateway: ManagedTelemetryGateway,
    desired_config: GatewayConfig,
    current_config: GatewayConfig | None,
) -> tuple[GatewayConfig | None, str | None]:
    if current_config == desired_config:
        return current_config, None

    previous_config = current_config
    try:
        applied_config = gateway.start(desired_config)
        return applied_config, None
    except OSError as exc:
        error_message = (
            f"无法应用新网关配置 {desired_config.listen_host}:{desired_config.port}{desired_config.path}: {exc}"
        )
        if previous_config is None:
            return None, error_message

        try:
            restored_config = gateway.start(previous_config)
            return restored_config, f"{error_message}；已回退到旧配置。"
        except OSError as rollback_exc:
            return None, f"{error_message}；回退旧配置失败：{rollback_exc}"


def _ensure_gateway_healthy(
    gateway: ManagedTelemetryGateway,
    current_config: GatewayConfig | None,
    *,
    timeout: float,
) -> tuple[GatewayConfig | None, dict | None, str | None]:
    if current_config is None:
        return None, None, None

    health = probe_gateway_health(current_config, timeout=timeout)
    if health.get("ok"):
        return current_config, health, None

    restart_error: str | None = None
    try:
        current_config = gateway.restart(current_config)
        health = probe_gateway_health(current_config, timeout=timeout)
        if health.get("ok"):
            restart_error = "检测到共享网关健康检查失败，已自动重启并恢复。"
        else:
            restart_error = (
                "共享网关健康检查失败，自动重启后仍不可用："
                f" {health.get('error') or '未返回健康响应。'}"
            )
    except OSError as exc:
        restart_error = f"共享网关健康检查失败，自动重启也失败：{exc}"
        health = {
            **(health or {}),
            "ok": False,
            "error": restart_error,
        }
    return current_config, health, restart_error


def main() -> None:
    parser = argparse.ArgumentParser(description="Backend manager for the shared telemetry gateway.")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--health-timeout", type=float, default=1.5)
    parser.add_argument("--settings-path")
    args = parser.parse_args()

    settings_path = None if not args.settings_path else Path(args.settings_path)
    gateway = ManagedTelemetryGateway()
    current_config: GatewayConfig | None = None
    last_error: str | None = None

    try:
        while True:
            desired_config = _load_desired_gateway_config(settings_path=settings_path)
            current_config, last_error = _apply_gateway_config(
                gateway=gateway,
                desired_config=desired_config,
                current_config=current_config,
            )
            current_config, health, health_error = _ensure_gateway_healthy(
                gateway=gateway,
                current_config=current_config,
                timeout=max(args.health_timeout, 0.2),
            )
            if health_error:
                last_error = f"{last_error}；{health_error}" if last_error else health_error
            write_gateway_manager_status(
                running=current_config is not None,
                config=current_config,
                desired_config=desired_config,
                last_error=last_error,
                health=health,
            )
            time.sleep(max(args.poll_interval, 0.5))
    except KeyboardInterrupt:
        pass
    finally:
        gateway.stop()
        clear_gateway_manager_status()


if __name__ == "__main__":
    main()

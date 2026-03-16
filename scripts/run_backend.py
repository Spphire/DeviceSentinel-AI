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
        gateway.start(desired_config)
        return desired_config, None
    except OSError as exc:
        error_message = (
            f"无法应用新网关配置 {desired_config.listen_host}:{desired_config.port}{desired_config.path}: {exc}"
        )
        if previous_config is None:
            return None, error_message

        try:
            gateway.start(previous_config)
            return previous_config, f"{error_message}；已回退到旧配置。"
        except OSError as rollback_exc:
            return None, f"{error_message}；回退旧配置失败：{rollback_exc}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backend manager for the shared telemetry gateway.")
    parser.add_argument("--poll-interval", type=float, default=1.0)
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
            write_gateway_manager_status(
                running=current_config is not None,
                config=current_config,
                desired_config=desired_config,
                last_error=last_error,
            )
            time.sleep(max(args.poll_interval, 0.5))
    except KeyboardInterrupt:
        pass
    finally:
        gateway.stop()
        clear_gateway_manager_status()


if __name__ == "__main__":
    main()

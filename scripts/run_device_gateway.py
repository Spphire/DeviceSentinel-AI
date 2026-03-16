"""Run a lightweight HTTP gateway for real-device telemetry."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.gateway_service import ManagedTelemetryGateway, normalize_gateway_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-device telemetry HTTP gateway.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=10570)
    parser.add_argument("--path", default="/telemetry")
    args = parser.parse_args()

    config = normalize_gateway_config(
        {
            "listen_host": args.host,
            "port": args.port,
            "path": args.path,
        }
    )
    gateway = ManagedTelemetryGateway()
    gateway.start(config)
    print(f"Gateway listening on http://{config.listen_host}:{config.port}{config.path}")

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        gateway.stop()


if __name__ == "__main__":
    main()

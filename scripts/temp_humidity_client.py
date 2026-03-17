"""Push temperature/humidity telemetry to the dashboard gateway."""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.telemetry_client import add_gateway_arguments, build_gateway_url, build_payload, send_payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Temperature/humidity telemetry client.")
    add_gateway_arguments(parser)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--humidity", type=float)
    parser.add_argument("--simulate", action="store_true")
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
        temperature = args.temperature if args.temperature is not None else round(random.uniform(21.0, 27.0), 1)
        humidity = args.humidity if args.humidity is not None else round(random.uniform(42.0, 68.0), 1)

        payload = build_payload(
            instance_id=args.instance_id,
            metrics={
                "temperature": temperature,
                "humidity": humidity,
            },
            client_name="temp_humidity_client",
            meta={"mode": "simulate" if args.simulate else "manual"},
        )
        print(send_payload(url=url, payload=payload))

        if args.once or not args.simulate:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()

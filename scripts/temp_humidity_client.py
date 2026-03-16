"""Push temperature/humidity telemetry to the gateway."""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime
from urllib import request


def send_payload(url: str, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url=url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=5) as response:
        print(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Temperature/humidity telemetry client.")
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10570)
    parser.add_argument("--path", default="/telemetry")
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--humidity", type=float)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}{args.path}"

    while True:
        temperature = args.temperature if args.temperature is not None else round(random.uniform(21.0, 27.0), 1)
        humidity = args.humidity if args.humidity is not None else round(random.uniform(42.0, 68.0), 1)

        payload = {
            "instance_id": args.instance_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "metrics": {
                "temperature": temperature,
                "humidity": humidity,
            },
            "meta": {"client": "temp_humidity_client"},
        }
        send_payload(url=url, payload=payload)

        if args.once or not args.simulate:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()

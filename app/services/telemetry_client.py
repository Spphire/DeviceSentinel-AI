"""Shared helpers for telemetry client scripts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any
from urllib import request


def send_payload(url: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url=url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=5) as response:
        return response.read().decode("utf-8")


def add_gateway_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--instance-id", required=True)
    parser.add_argument(
        "--gateway-host",
        "--host",
        dest="gateway_host",
        default="127.0.0.1",
        help="Dashboard telemetry gateway host or IP.",
    )
    parser.add_argument(
        "--gateway-port",
        "--port",
        dest="gateway_port",
        type=int,
        default=10570,
        help="Dashboard telemetry gateway port.",
    )
    parser.add_argument(
        "--gateway-path",
        "--path",
        dest="gateway_path",
        default="/telemetry",
        help="Dashboard telemetry gateway path.",
    )
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--once", action="store_true")
    return parser


def build_gateway_url(*, gateway_host: str, gateway_port: int, gateway_path: str) -> str:
    return f"http://{gateway_host}:{gateway_port}{gateway_path}"


def build_payload(
    *,
    instance_id: str,
    metrics: dict[str, Any],
    client_name: str,
    meta: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    payload_meta = {"client": client_name}
    if meta:
        payload_meta.update(meta)

    return {
        "instance_id": instance_id,
        "timestamp": timestamp or datetime.now().isoformat(timespec="seconds"),
        "metrics": metrics,
        "meta": payload_meta,
    }

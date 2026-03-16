"""Run a lightweight HTTP gateway for real-device telemetry."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.real_device_store import append_real_device_event


def build_handler(accepted_path: str):
    class TelemetryHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            if accepted_path and self.path != accepted_path:
                self.send_error(404, "Path not found.")
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            payload["meta"] = {
                **payload.get("meta", {}),
                "remote_addr": self.client_address[0],
            }
            event = append_real_device_event(payload)

            response = {"status": "ok", "instance_id": event["instance_id"], "timestamp": event["timestamp"]}
            body = json.dumps(response, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    return TelemetryHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-device telemetry HTTP gateway.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=10570)
    parser.add_argument("--path", default="/telemetry")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), build_handler(args.path))
    print(f"Gateway listening on http://{args.host}:{args.port}{args.path}")
    server.serve_forever()


if __name__ == "__main__":
    main()

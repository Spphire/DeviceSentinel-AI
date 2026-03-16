"""Shared telemetry gateway runtime helpers and status management."""

from __future__ import annotations

import json
import os
import socket
from dataclasses import asdict, dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from app.services.real_device_store import append_real_device_event


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_DIR = PROJECT_ROOT / "storage"
GATEWAY_MANAGER_STATUS_PATH = STORAGE_DIR / "gateway_manager_status.json"
DEFAULT_GATEWAY_PATH = "/telemetry"


@dataclass(frozen=True)
class GatewayConfig:
    listen_host: str = "127.0.0.1"
    port: int = 10570
    path: str = DEFAULT_GATEWAY_PATH
    advertised_host: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_gateway_config(payload: dict[str, Any] | None = None) -> GatewayConfig:
    payload = payload or {}
    listen_host = str(payload.get("listen_host", "127.0.0.1")).strip() or "127.0.0.1"
    port = int(payload.get("port", 10570))
    path = str(payload.get("path", DEFAULT_GATEWAY_PATH)).strip() or DEFAULT_GATEWAY_PATH
    if not path.startswith("/"):
        path = f"/{path}"
    advertised_host = str(payload.get("advertised_host", "")).strip()
    return GatewayConfig(
        listen_host=listen_host,
        port=port,
        path=path,
        advertised_host=advertised_host,
    )


def resolve_gateway_client_host(config: GatewayConfig) -> str:
    if config.advertised_host:
        return config.advertised_host

    lowered = config.listen_host.lower()
    if lowered in {"127.0.0.1", "localhost"}:
        return "127.0.0.1"
    if lowered in {"0.0.0.0", "::", ""}:
        detected = _detect_local_ip()
        return detected or "127.0.0.1"
    return config.listen_host


def build_gateway_client_target(config: GatewayConfig) -> dict[str, Any]:
    return {
        "host": resolve_gateway_client_host(config),
        "port": config.port,
        "path": config.path,
    }


def load_gateway_manager_status(status_path: Path | None = None) -> dict[str, Any] | None:
    path = status_path or GATEWAY_MANAGER_STATUS_PATH
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_gateway_manager_status(
    *,
    running: bool,
    config: GatewayConfig | None,
    desired_config: GatewayConfig | None = None,
    last_error: str | None = None,
    status_path: Path | None = None,
) -> None:
    path = status_path or GATEWAY_MANAGER_STATUS_PATH
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "running": running,
        "manager_pid": os.getpid(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "gateway": None if config is None else config.to_dict(),
        "desired_gateway": None if desired_config is None else desired_config.to_dict(),
        "client_target": None if config is None else build_gateway_client_target(config),
        "last_error": last_error,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_gateway_manager_status(status_path: Path | None = None) -> None:
    path = status_path or GATEWAY_MANAGER_STATUS_PATH
    if path.exists():
        path.unlink()


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


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class ManagedTelemetryGateway:
    def __init__(self) -> None:
        self._config: GatewayConfig | None = None
        self._server: _ReusableThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._lock = Lock()

    @property
    def config(self) -> GatewayConfig | None:
        return self._config

    def start(self, config: GatewayConfig) -> GatewayConfig:
        with self._lock:
            if self._config == config and self._server is not None and self._thread is not None and self._thread.is_alive():
                return config

            self._stop_locked()

            server = _ReusableThreadingHTTPServer((config.listen_host, config.port), build_handler(config.path))
            thread = Thread(target=server.serve_forever, name="telemetry-gateway", daemon=True)
            thread.start()

            self._server = server
            self._thread = thread
            self._config = config
            return config

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def _stop_locked(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        self._config = None

        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)


def _detect_local_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            detected = probe.getsockname()[0]
            if detected:
                return detected
    except OSError:
        pass

    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return None

"""Personal PC telemetry app with GUI and headless modes."""

from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import ttk

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - optional dependency
    pystray = None
    Image = None
    ImageDraw = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.telemetry_client import build_gateway_url, build_payload, send_payload
from scripts.personal_pc_client import collect_metrics


SETTINGS_FILENAME = "personal_pc_client_app.json"
AUTOSTART_FILENAME = "DeviceSentinel-Personal-PC-Client.cmd"
APP_TITLE = "DeviceSentinel Personal PC Client"
MAX_RETRY_DELAY_SECONDS = 30
METRIC_DEFINITIONS = [
    ("cpu_usage", "CPU", "%"),
    ("memory_usage", "内存", "%"),
    ("disk_activity", "磁盘", "%"),
    ("gpu_usage", "GPU", "%"),
    ("gpu_memory_usage", "显存", "%"),
]


@dataclass
class PersonalPcClientConfig:
    instance_id: str
    gateway_host: str
    gateway_port: int
    gateway_path: str
    interval: int = 5


def get_settings_path() -> Path:
    appdata = os.getenv("APPDATA")
    base_dir = Path(appdata) / "DeviceSentinel" if appdata else Path.home() / ".device_sentinel"
    return base_dir / SETTINGS_FILENAME


def get_startup_path() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / AUTOSTART_FILENAME
    return Path.home() / ".config" / AUTOSTART_FILENAME


def _resolve_pythonw_executable(executable: str | None = None) -> str:
    current = Path(executable or sys.executable)
    if current.name.lower() == "python.exe":
        candidate = current.with_name("pythonw.exe")
        if candidate.exists():
            return str(candidate)
    return str(current)


def build_autostart_command(
    *,
    executable_path: str | None = None,
    script_path: str | None = None,
    start_minimized: bool = True,
) -> str:
    args: list[str]
    if getattr(sys, "frozen", False):
        args = [executable_path or sys.executable]
    else:
        args = [
            _resolve_pythonw_executable(executable_path),
            script_path or str(Path(__file__).resolve()),
        ]
    if start_minimized:
        args.append("--start-minimized")
    return subprocess.list2cmdline(args)


def is_autostart_enabled(startup_path: Path | None = None) -> bool:
    return (startup_path or get_startup_path()).exists()


def set_autostart_enabled(
    enabled: bool,
    *,
    startup_path: Path | None = None,
    executable_path: str | None = None,
    script_path: str | None = None,
) -> Path:
    path = startup_path or get_startup_path()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        command = build_autostart_command(
            executable_path=executable_path,
            script_path=script_path,
            start_minimized=True,
        )
        path.write_text(f"@echo off\r\nstart \"\" {command}\r\n", encoding="utf-8")
    elif path.exists():
        path.unlink()
    return path


def supports_system_tray() -> bool:
    return pystray is not None and Image is not None and ImageDraw is not None


def build_default_instance_id() -> str:
    hostname = socket.gethostname().lower()
    safe_hostname = "".join(char for char in hostname if char.isalnum() or char == "-")[:24]
    return f"personal_pc_real-{safe_hostname or 'local'}"


def load_saved_config() -> PersonalPcClientConfig:
    settings_path = get_settings_path()
    if settings_path.exists():
        try:
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            return PersonalPcClientConfig(
                instance_id=payload.get("instance_id") or build_default_instance_id(),
                gateway_host=payload.get("gateway_host") or "127.0.0.1",
                gateway_port=int(payload.get("gateway_port") or 10570),
                gateway_path=payload.get("gateway_path") or "/telemetry",
                interval=int(payload.get("interval") or 5),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return PersonalPcClientConfig(
        instance_id=build_default_instance_id(),
        gateway_host="127.0.0.1",
        gateway_port=10570,
        gateway_path="/telemetry",
        interval=5,
    )


def save_config(config: PersonalPcClientConfig) -> None:
    settings_path = get_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "instance_id": config.instance_id,
                "gateway_host": config.gateway_host,
                "gateway_port": config.gateway_port,
                "gateway_path": config.gateway_path,
                "interval": config.interval,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _try_save_current_config(build_config) -> None:
    try:
        save_config(build_config())
    except ValueError:
        pass


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Personal PC telemetry app.")
    parser.add_argument("--instance-id")
    parser.add_argument("--gateway-host", "--host", dest="gateway_host")
    parser.add_argument("--gateway-port", "--port", dest="gateway_port", type=int)
    parser.add_argument("--gateway-path", "--path", dest="gateway_path")
    parser.add_argument("--interval", type=int)
    parser.add_argument("--headless", action="store_true", help="Run the client without opening the GUI.")
    parser.add_argument("--start-minimized", action="store_true", help="Start the GUI hidden in the system tray.")
    parser.add_argument("--once", action="store_true", help="Send a single telemetry payload and exit.")
    return parser


def merge_config_with_args(saved: PersonalPcClientConfig, args: argparse.Namespace) -> PersonalPcClientConfig:
    return PersonalPcClientConfig(
        instance_id=(args.instance_id or saved.instance_id).strip(),
        gateway_host=(args.gateway_host or saved.gateway_host).strip(),
        gateway_port=int(args.gateway_port or saved.gateway_port),
        gateway_path=(args.gateway_path or saved.gateway_path).strip(),
        interval=max(1, int(args.interval or saved.interval)),
    )


def _parse_positive_int(value: str, *, field_name: str, fallback: int) -> int:
    text = value.strip()
    if not text:
        return fallback
    parsed = int(text)
    if parsed <= 0:
        raise ValueError(f"{field_name} 必须大于 0。")
    return parsed


def compute_retry_delay(interval: int, consecutive_failures: int) -> int:
    safe_interval = max(1, int(interval))
    failure_multiplier = min(max(1, int(consecutive_failures)), 4)
    return min(MAX_RETRY_DELAY_SECONDS, safe_interval * failure_multiplier)


def push_metrics(config: PersonalPcClientConfig, *, mode: str) -> tuple[dict[str, float], str]:
    metrics = collect_metrics()
    url = build_gateway_url(
        gateway_host=config.gateway_host,
        gateway_port=config.gateway_port,
        gateway_path=config.gateway_path,
    )
    payload = build_payload(
        instance_id=config.instance_id,
        metrics=metrics,
        client_name="personal_pc_client",
        meta={"platform": "windows", "mode": mode},
    )
    response = send_payload(url=url, payload=payload)
    return metrics, response


def build_gateway_preview(config: PersonalPcClientConfig) -> str:
    return build_gateway_url(
        gateway_host=config.gateway_host,
        gateway_port=config.gateway_port,
        gateway_path=config.gateway_path,
    )


def run_headless(config: PersonalPcClientConfig, *, once: bool) -> None:
    save_config(config)
    consecutive_failures = 0
    while True:
        try:
            metrics, response = push_metrics(config, mode="headless")
            consecutive_failures = 0
            metric_summary = " / ".join(
                f"{label}={metrics[metric_id]}{unit}" for metric_id, label, unit in METRIC_DEFINITIONS
            )
            print(f"[headless] {metric_summary}")
            print(response)
        except Exception as exc:
            if once:
                raise
            consecutive_failures += 1
            retry_delay = compute_retry_delay(config.interval, consecutive_failures)
            print(
                f"[headless] 上报失败：{exc}；将在 {retry_delay} 秒后自动重试，目标网关 {build_gateway_preview(config)}。",
                file=sys.stderr,
            )
            time.sleep(retry_delay)
            continue
        if once:
            break
        time.sleep(config.interval)


class PersonalPcClientApp(tk.Tk):
    def __init__(self, config: PersonalPcClientConfig, *, start_minimized: bool = False) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x760")
        self.minsize(1000, 680)

        self.worker_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.event_queue: queue.Queue[dict[str, object]] = queue.Queue()
        self.history = {metric_id: deque(maxlen=48) for metric_id, _, _ in METRIC_DEFINITIONS}
        self.tray_icon = None
        self.tray_thread: threading.Thread | None = None
        self.tray_supported = supports_system_tray()
        self.start_minimized = start_minimized
        self.force_exit = False

        self.instance_id_var = tk.StringVar(value=config.instance_id)
        self.gateway_host_var = tk.StringVar(value=config.gateway_host)
        self.gateway_port_var = tk.StringVar(value=str(config.gateway_port))
        self.gateway_path_var = tk.StringVar(value=config.gateway_path)
        self.interval_var = tk.StringVar(value=str(config.interval))
        self.autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        self.status_var = tk.StringVar(value="待连接")
        self.gateway_var = tk.StringVar(value=build_gateway_preview(config))
        self.last_push_var = tk.StringVar(value="尚未发送")
        self.response_var = tk.StringVar(value="等待首次上报")
        self.retry_var = tk.StringVar(value="未触发")
        self.metric_vars = {
            metric_id: tk.StringVar(value="--")
            for metric_id, _, _ in METRIC_DEFINITIONS
        }
        self.chart_canvases: dict[str, tk.Canvas] = {}

        self._build_layout()
        self._register_persistence_hooks()
        self._poll_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if self.start_minimized:
            self.after(250, self._minimize_to_tray)

    def _build_layout(self) -> None:
        self.configure(bg="#eef2f6")

        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 19, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="面向 C 端用户的个人 PC 上报程序，可直接填写仪表盘地址并查看本机资源曲线。",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        config_card = ttk.LabelFrame(root, text="连接配置", padding=14)
        config_card.grid(row=1, column=0, sticky="ew", pady=(14, 12))
        for index in range(5):
            config_card.columnconfigure(index, weight=1)

        ttk.Label(config_card, text="设备实例 ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(config_card, textvariable=self.instance_id_var).grid(row=1, column=0, sticky="ew", padx=(0, 10))

        ttk.Label(config_card, text="仪表盘 IP").grid(row=0, column=1, sticky="w")
        ttk.Entry(config_card, textvariable=self.gateway_host_var).grid(row=1, column=1, sticky="ew", padx=(0, 10))

        ttk.Label(config_card, text="端口").grid(row=0, column=2, sticky="w")
        ttk.Entry(config_card, textvariable=self.gateway_port_var, width=8).grid(
            row=1,
            column=2,
            sticky="ew",
            padx=(0, 10),
        )

        ttk.Label(config_card, text="路径").grid(row=0, column=3, sticky="w")
        ttk.Entry(config_card, textvariable=self.gateway_path_var).grid(row=1, column=3, sticky="ew", padx=(0, 10))

        ttk.Label(config_card, text="上报间隔（秒）").grid(row=0, column=4, sticky="w")
        ttk.Entry(config_card, textvariable=self.interval_var, width=8).grid(row=1, column=4, sticky="ew")

        action_bar = ttk.Frame(config_card)
        action_bar.grid(row=2, column=0, columnspan=5, sticky="ew", pady=(12, 0))
        self.start_button = ttk.Button(action_bar, text="开始上报", command=self._start_worker)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(action_bar, text="停止上报", command=self._stop_worker, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        self.minimize_button = ttk.Button(
            action_bar,
            text="最小化到托盘",
            command=self._minimize_to_tray,
            state="normal" if self.tray_supported else "disabled",
        )
        self.minimize_button.pack(side="left")
        ttk.Checkbutton(
            action_bar,
            text="开机自启动",
            variable=self.autostart_var,
            command=self._handle_autostart_toggle,
        ).pack(side="left", padx=12)
        ttk.Label(
            action_bar,
            text="配置会自动保存在系统缓存目录；再次点击“开始上报”会按最新参数重新启动。",
        ).pack(side="left", padx=8)
        if not self.tray_supported:
            ttk.Label(action_bar, text="当前环境未安装 pystray，托盘功能将自动禁用。").pack(side="left", padx=8)
        ttk.Label(
            config_card,
            text=f"本地配置缓存：{get_settings_path()}",
        ).grid(row=3, column=0, columnspan=5, sticky="w", pady=(10, 0))
        ttk.Label(
            config_card,
            text=f"开机自启动脚本：{get_startup_path()}",
        ).grid(row=4, column=0, columnspan=5, sticky="w", pady=(4, 0))

        meta_card = ttk.Frame(root)
        meta_card.grid(row=2, column=0, sticky="nsew")
        meta_card.columnconfigure(0, weight=1)
        meta_card.columnconfigure(1, weight=1)
        meta_card.rowconfigure(1, weight=1)

        status_card = ttk.LabelFrame(meta_card, text="运行状态", padding=14)
        status_card.grid(row=0, column=0, columnspan=2, sticky="ew")
        for column in range(5):
            status_card.columnconfigure(column, weight=1)

        self._build_status_field(status_card, 0, "连接状态", self.status_var)
        self._build_status_field(status_card, 1, "目标网关", self.gateway_var)
        self._build_status_field(status_card, 2, "最后上报", self.last_push_var)
        self._build_status_field(status_card, 3, "网关响应", self.response_var)
        self._build_status_field(status_card, 4, "自动重试", self.retry_var)

        current_card = ttk.LabelFrame(meta_card, text="当前指标", padding=14)
        current_card.grid(row=1, column=0, sticky="nsew", pady=(12, 0), padx=(0, 8))
        current_card.columnconfigure(0, weight=1)
        current_card.columnconfigure(1, weight=1)
        current_card.columnconfigure(2, weight=1)
        current_card.columnconfigure(3, weight=1)
        current_card.columnconfigure(4, weight=1)

        for index, (metric_id, label, unit) in enumerate(METRIC_DEFINITIONS):
            card = ttk.Frame(current_card, padding=10)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 6, 0))
            ttk.Label(card, text=label).pack(anchor="w")
            ttk.Label(card, textvariable=self.metric_vars[metric_id], font=("Segoe UI", 18, "bold")).pack(anchor="w")
            ttk.Label(card, text=unit).pack(anchor="w")

        chart_card = ttk.LabelFrame(meta_card, text="资源曲线", padding=14)
        chart_card.grid(row=1, column=1, sticky="nsew", pady=(12, 0), padx=(8, 0))
        for row in range(2):
            chart_card.rowconfigure(row, weight=1)
        for col in range(3):
            chart_card.columnconfigure(col, weight=1)

        for index, (metric_id, label, unit) in enumerate(METRIC_DEFINITIONS):
            frame = ttk.Frame(chart_card)
            frame.grid(row=index // 3, column=index % 3, sticky="nsew", padx=6, pady=6)
            ttk.Label(frame, text=f"{label}曲线").pack(anchor="w")
            canvas = tk.Canvas(frame, width=240, height=120, bg="#ffffff", highlightthickness=1, highlightbackground="#d4dbe3")
            canvas.pack(fill="both", expand=True)
            self.chart_canvases[metric_id] = canvas

    def _register_persistence_hooks(self) -> None:
        for variable in [
            self.instance_id_var,
            self.gateway_host_var,
            self.gateway_port_var,
            self.gateway_path_var,
            self.interval_var,
        ]:
            variable.trace_add("write", self._persist_form_state)

    def _persist_form_state(self, *_args) -> None:
        try:
            self.gateway_var.set(build_gateway_preview(self._build_config()))
        except ValueError:
            self.gateway_var.set("配置待修正")
        _try_save_current_config(self._build_config)

    def _handle_autostart_toggle(self) -> None:
        try:
            path = set_autostart_enabled(self.autostart_var.get())
        except OSError as exc:
            self.autostart_var.set(is_autostart_enabled())
            self.response_var.set(f"开机自启动设置失败：{exc}")
            return

        if self.autostart_var.get():
            self.response_var.set(f"已启用开机自启动：{path}")
        else:
            self.response_var.set("已关闭开机自启动。")

    def _create_tray_image(self):
        image = Image.new("RGB", (64, 64), "#0f172a")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 8, 56, 56), radius=12, fill="#2563eb")
        draw.rectangle((20, 18, 30, 46), fill="#f8fafc")
        draw.rectangle((34, 26, 44, 46), fill="#bfdbfe")
        return image

    def _ensure_tray_icon(self) -> None:
        if not self.tray_supported or self.tray_icon is not None:
            return

        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", lambda _icon, _item: self.after(0, self._restore_from_tray)),
            pystray.MenuItem("开始上报", lambda _icon, _item: self.after(0, self._start_worker)),
            pystray.MenuItem("停止上报", lambda _icon, _item: self.after(0, self._stop_worker)),
            pystray.MenuItem("退出程序", lambda _icon, _item: self.after(0, self._exit_from_tray)),
        )
        self.tray_icon = pystray.Icon("devicesentinel-personal-pc", self._create_tray_image(), APP_TITLE, menu)
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True, name="personal-pc-tray")
        self.tray_thread.start()

    def _shutdown_tray_icon(self) -> None:
        if self.tray_icon is not None:
            self.tray_icon.stop()
            self.tray_icon = None
        self.tray_thread = None

    def _minimize_to_tray(self) -> None:
        if not self.tray_supported:
            self.iconify()
            return
        self._ensure_tray_icon()
        self.withdraw()
        self.status_var.set("托盘运行中")
        self.response_var.set("窗口已隐藏到系统托盘，可通过托盘菜单恢复。")

    def _restore_from_tray(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self.status_var.set("窗口已恢复")

    def _exit_from_tray(self) -> None:
        self.force_exit = True
        self._on_close()

    def _build_status_field(self, parent: ttk.Frame, column: int, label: str, variable: tk.StringVar) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
        ttk.Label(frame, text=label).pack(anchor="w")
        ttk.Label(frame, textvariable=variable, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(4, 0))

    def _build_config(self) -> PersonalPcClientConfig:
        return PersonalPcClientConfig(
            instance_id=self.instance_id_var.get().strip() or build_default_instance_id(),
            gateway_host=self.gateway_host_var.get().strip() or "127.0.0.1",
            gateway_port=_parse_positive_int(
                self.gateway_port_var.get(),
                field_name="端口",
                fallback=10570,
            ),
            gateway_path=self.gateway_path_var.get().strip() or "/telemetry",
            interval=_parse_positive_int(
                self.interval_var.get(),
                field_name="上报间隔",
                fallback=5,
            ),
        )

    def _start_worker(self) -> None:
        self._stop_worker(wait=True, update_status=False)

        try:
            config = self._build_config()
        except ValueError as exc:
            self.status_var.set("配置错误")
            self.response_var.set(str(exc))
            return

        save_config(config)
        self.stop_event.clear()
        self.status_var.set("连接中...")
        self.gateway_var.set(build_gateway_preview(config))
        self.retry_var.set("未触发")
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.worker_thread = threading.Thread(target=self._worker_loop, args=(config,), daemon=True)
        self.worker_thread.start()

    def _stop_worker(self, *, wait: bool = False, update_status: bool = True) -> None:
        self.stop_event.set()
        if wait and self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2)
        self.worker_thread = None
        if update_status:
            self.status_var.set("已停止")
            self.retry_var.set("已停止")
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")

    def _worker_loop(self, config: PersonalPcClientConfig) -> None:
        consecutive_failures = 0
        while not self.stop_event.is_set():
            try:
                metrics, response = push_metrics(config, mode="gui")
                consecutive_failures = 0
                self.event_queue.put(
                    {
                        "kind": "metrics",
                        "metrics": metrics,
                        "response": response,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
                wait_seconds = config.interval
            except Exception as exc:
                consecutive_failures += 1
                wait_seconds = compute_retry_delay(config.interval, consecutive_failures)
                self.event_queue.put(
                    {
                        "kind": "error",
                        "message": str(exc),
                        "retry_delay": wait_seconds,
                        "failure_count": consecutive_failures,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            if self.stop_event.wait(wait_seconds):
                break

    def _poll_queue(self) -> None:
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            if event["kind"] == "metrics":
                metrics = event["metrics"]
                for metric_id, _label, unit in METRIC_DEFINITIONS:
                    value = metrics.get(metric_id, 0.0)
                    self.metric_vars[metric_id].set(f"{value:.1f}{unit}")
                    self.history[metric_id].append(float(value))
                    self._render_chart(metric_id)
                self.last_push_var.set(str(event["timestamp"]))
                self.response_var.set(str(event["response"]))
                self.status_var.set("上报中")
                self.retry_var.set("未触发")
            else:
                self.status_var.set("连接异常，自动重试中")
                self.response_var.set(str(event["message"]))
                self.retry_var.set(
                    f"失败 {event['failure_count']} 次，{event['retry_delay']} 秒后重试"
                )
        self.after(250, self._poll_queue)

    def _render_chart(self, metric_id: str) -> None:
        canvas = self.chart_canvases[metric_id]
        width = int(canvas["width"])
        height = int(canvas["height"])
        values = list(self.history[metric_id])
        canvas.delete("all")
        canvas.create_rectangle(1, 1, width - 1, height - 1, outline="#d4dbe3")

        if not values:
            canvas.create_text(width / 2, height / 2, text="等待数据", fill="#718096")
            return

        padding = 16
        chart_width = width - padding * 2
        chart_height = height - padding * 2
        scale_min, scale_max = 0.0, 100.0
        if metric_id == "gpu_memory_usage":
            scale_max = 100.0

        points: list[tuple[float, float]] = []
        for index, value in enumerate(values):
            x = padding + chart_width * (index / max(1, len(values) - 1))
            normalized = (value - scale_min) / max(1.0, scale_max - scale_min)
            y = padding + chart_height * (1 - normalized)
            points.append((x, y))

        for guide in [0, 50, 100]:
            y = padding + chart_height * (1 - guide / 100)
            canvas.create_line(padding, y, width - padding, y, fill="#eef2f6")
            canvas.create_text(8, y, text=str(guide), fill="#94a3b8", anchor="w")

        if len(points) == 1:
            x, y = points[0]
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#2563eb", outline="")
        else:
            flat_points = [coordinate for point in points for coordinate in point]
            canvas.create_line(*flat_points, fill="#2563eb", width=2, smooth=True)

        latest_value = values[-1]
        canvas.create_text(width - 8, 10, text=f"{latest_value:.1f}", fill="#0f172a", anchor="ne")

    def _on_close(self) -> None:
        if self.tray_supported and not self.force_exit:
            self._minimize_to_tray()
            return
        _try_save_current_config(self._build_config)
        self._stop_worker(wait=True)
        self._shutdown_tray_icon()
        self.destroy()


def run_gui(config: PersonalPcClientConfig, *, start_minimized: bool = False) -> None:
    save_config(config)
    app = PersonalPcClientApp(config, start_minimized=start_minimized)
    app.mainloop()


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = merge_config_with_args(load_saved_config(), args)

    if args.headless:
        run_headless(config, once=args.once)
        return

    run_gui(config, start_minimized=args.start_minimized)


if __name__ == "__main__":
    main()

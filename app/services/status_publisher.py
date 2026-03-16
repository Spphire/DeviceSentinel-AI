"""Build compact monitoring snapshots and render a static status site."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.agent.chat_agent import build_agent_backend_config
from app.agent.report_generator import RISK_LABELS, STATUS_LABELS, generate_report
from app.services.demo_service import MAX_HISTORY_POINTS, create_dashboard_runtime, load_runtime_templates
from app.services.gateway_service import (
    build_gateway_client_target,
    load_gateway_manager_status,
    normalize_gateway_config,
)
from app.services.real_device_store import load_real_device_history
from app.services.settings_store import load_dashboard_settings


DEVICE_STATUS_LABELS = {"online": "在线", "offline": "离线", "unknown": "未知"}
SITE_TITLE = "DeviceSentinel AI Status"


def build_status_snapshot(
    *,
    settings: dict[str, Any] | None = None,
    history_window: int | None = None,
    seed: int = 11,
    max_recent_events: int = 6,
) -> dict[str, Any]:
    settings = settings or load_dashboard_settings()
    templates = load_runtime_templates()
    history_limit = max(history_window or int(settings["system"].get("history_window", 60)), 12)
    runtime = create_dashboard_runtime(
        templates=templates,
        device_payloads=settings["devices"],
        history_limit=MAX_HISTORY_POINTS,
        seed=seed,
    )
    runtime.step()

    overview_rows = runtime.get_overview_rows()
    counts = {
        "total_devices": len(overview_rows),
        "online_devices": sum(1 for row in overview_rows if row["device_status"] == "online"),
        "offline_devices": sum(1 for row in overview_rows if row["device_status"] == "offline"),
        "abnormal_devices": sum(1 for row in overview_rows if row["status"] in {"warning", "critical", "offline"}),
        "high_risk_devices": sum(1 for row in overview_rows if row["risk_level"] == "high"),
    }

    gateway_config = normalize_gateway_config(settings.get("gateway"))
    gateway_status = load_gateway_manager_status() or {}
    gateway_runtime = gateway_status.get("gateway")
    active_gateway = normalize_gateway_config(gateway_runtime) if gateway_runtime else gateway_config
    client_target = gateway_status.get("client_target") or build_gateway_client_target(active_gateway)
    agent_backend = build_agent_backend_config(settings)

    devices: list[dict[str, Any]] = []
    recent_events: list[dict[str, Any]] = []

    for device_payload in settings["devices"]:
        instance_id = device_payload["instance_id"]
        snapshot = runtime.get_device_snapshot(instance_id)
        template = snapshot["template"]
        point = snapshot["point"]
        analysis = snapshot["analysis"] or {}
        metric_definitions = [metric.to_dict() for metric in template.metrics]
        metrics = []
        for metric in metric_definitions:
            value = None if point is None else point.metrics.get(metric["metric_id"])
            metrics.append(
                {
                    "metric_id": metric["metric_id"],
                    "label": metric["label"],
                    "unit": metric.get("unit", ""),
                    "value": value,
                }
            )

        report = generate_report(analysis, metric_definitions=metric_definitions) if analysis else "暂无分析结果。"
        device_item = {
            "instance_id": instance_id,
            "name": snapshot["config"].name,
            "template_id": template.template_id,
            "template_name": template.display_name,
            "category_name": template.category_name,
            "source_type": template.source_type,
            "device_status": analysis.get("device_status", point.device_status if point else "unknown"),
            "status": analysis.get("status", "unknown"),
            "risk_level": analysis.get("risk_level", "unknown"),
            "last_heartbeat": snapshot["last_heartbeat"],
            "metrics": metrics,
            "issue_count": len(analysis.get("issues", [])),
            "issues": analysis.get("issues", [])[:3],
            "summary": analysis.get("summary") or report.splitlines()[-2] if report else "暂无摘要。",
            "report_excerpt": _truncate_text(report.replace("\n", " "), 280),
        }
        devices.append(device_item)

        if template.source_type == "real":
            history = load_real_device_history(instance_id, limit=max_recent_events)
            for event in history[-max_recent_events:]:
                recent_events.append(
                    {
                        "instance_id": instance_id,
                        "device_name": snapshot["config"].name,
                        "timestamp": event["timestamp"],
                        "metrics": event.get("metrics", {}),
                    }
                )

    devices.sort(key=lambda item: _device_sort_key(item["status"], item["risk_level"], item["name"]))
    recent_events.sort(key=lambda item: item["timestamp"], reverse=True)
    recent_events = recent_events[:max_recent_events]

    focus_devices = [
        {
            "instance_id": device["instance_id"],
            "name": device["name"],
            "status": device["status"],
            "risk_level": device["risk_level"],
            "summary": device["summary"],
        }
        for device in devices
        if device["status"] in {"warning", "critical", "offline"}
    ][:6]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "title": SITE_TITLE,
        "counts": counts,
        "gateway": {
            "running": bool(gateway_status.get("running")),
            "manager_pid": gateway_status.get("manager_pid"),
            "listen_host": active_gateway.listen_host,
            "port": active_gateway.port,
            "path": active_gateway.path,
            "client_target": client_target,
            "last_error": gateway_status.get("last_error"),
        },
        "agent": {
            "mode": agent_backend.mode,
            "model": agent_backend.model,
            "use_local_fallback": agent_backend.use_local_fallback,
        },
        "focus_devices": focus_devices,
        "devices": devices,
        "recent_events": recent_events,
    }


def extract_snapshot_from_event_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    payload = payload or {}
    client_payload = payload.get("client_payload") or {}
    snapshot = client_payload.get("snapshot")
    if isinstance(snapshot, dict) and snapshot:
        return snapshot
    return None


def render_status_site(snapshot: dict[str, Any], output_dir: str | Path) -> Path:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    (target_dir / "status.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target_dir / "index.html").write_text(_build_status_html(snapshot), encoding="utf-8")
    return target_dir


def _build_status_html(snapshot: dict[str, Any]) -> str:
    counts = snapshot["counts"]
    gateway = snapshot["gateway"]
    agent = snapshot["agent"]
    focus_devices = snapshot["focus_devices"]
    devices = snapshot["devices"]
    recent_events = snapshot["recent_events"]

    count_cards = "".join(
        _render_count_card(label, value, tone)
        for label, value, tone in [
            ("设备总数", counts["total_devices"], "ink"),
            ("在线设备", counts["online_devices"], "green"),
            ("异常设备", counts["abnormal_devices"], "amber"),
            ("高风险设备", counts["high_risk_devices"], "red"),
        ]
    )

    focus_markup = (
        "".join(_render_focus_device(device) for device in focus_devices)
        if focus_devices
        else "<div class='empty'>当前没有需要优先追踪的异常设备。</div>"
    )
    device_markup = "".join(_render_device_card(device) for device in devices)
    event_markup = (
        "".join(_render_event_row(event) for event in recent_events)
        if recent_events
        else "<div class='empty'>当前没有可同步的真实设备最近事件。</div>"
    )
    gateway_status = "运行中" if gateway["running"] else "未检测到 manager"
    gateway_error = (
        f"<div class='note warning'>{html.escape(gateway['last_error'])}</div>"
        if gateway.get("last_error")
        else ""
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{SITE_TITLE}</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --paper: #fffdfa;
      --ink: #1c2a39;
      --muted: #627282;
      --line: rgba(28, 42, 57, 0.12);
      --green: #1f7a4d;
      --amber: #b67718;
      --red: #b94132;
      --teal: #0d7a76;
      --accent: #184e77;
      --shadow: 0 18px 40px rgba(22, 38, 56, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Noto Sans SC", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(24, 78, 119, 0.12), transparent 32%),
        radial-gradient(circle at bottom right, rgba(13, 122, 118, 0.10), transparent 28%),
        var(--bg);
    }}
    .shell {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0 48px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(255, 253, 250, 0.95), rgba(240, 247, 246, 0.95));
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 28px;
      position: relative;
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      right: -80px;
      top: -80px;
      width: 220px;
      height: 220px;
      background: rgba(24, 78, 119, 0.08);
      border-radius: 999px;
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 12px;
      color: var(--teal);
      font-weight: 700;
    }}
    h1 {{
      margin: 10px 0 8px;
      font-size: clamp(30px, 5vw, 46px);
      line-height: 1.05;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 22px;
      align-items: end;
    }}
    .hero-meta, .grid, .device-grid, .event-list {{
      margin-top: 24px;
    }}
    .hero-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 8px 14px;
      background: rgba(255,255,255,0.76);
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 14px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }}
    .count-card, .panel, .device-card, .event-row {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: var(--shadow);
    }}
    .count-card {{
      padding: 18px;
    }}
    .count-label {{
      color: var(--muted);
      font-size: 14px;
    }}
    .count-value {{
      margin-top: 10px;
      font-size: 34px;
      font-weight: 700;
    }}
    .count-card.green .count-value {{ color: var(--green); }}
    .count-card.amber .count-value {{ color: var(--amber); }}
    .count-card.red .count-value {{ color: var(--red); }}
    .panel {{
      padding: 22px;
      margin-top: 20px;
    }}
    .panel h2 {{
      margin: 0 0 14px;
      font-size: 20px;
    }}
    .focus-list, .device-grid {{
      display: grid;
      gap: 14px;
    }}
    .focus-list {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .focus-card {{
      border-radius: 16px;
      border: 1px solid var(--line);
      padding: 16px;
      background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(244,239,230,0.85));
    }}
    .device-grid {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .device-card {{
      padding: 18px;
    }}
    .device-head, .event-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }}
    .device-name {{
      margin: 0;
      font-size: 20px;
    }}
    .device-sub {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }}
    .badge {{
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.02em;
      color: white;
      white-space: nowrap;
    }}
    .badge.normal {{ background: var(--green); }}
    .badge.warning {{ background: var(--amber); }}
    .badge.critical, .badge.offline {{ background: var(--red); }}
    .badge.unknown {{ background: var(--muted); }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 16px;
    }}
    .metric {{
      padding: 12px;
      border-radius: 14px;
      background: rgba(24, 78, 119, 0.04);
      border: 1px solid rgba(24, 78, 119, 0.08);
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 12px;
    }}
    .metric-value {{
      margin-top: 6px;
      font-size: 22px;
      font-weight: 700;
    }}
    .section-label {{
      margin-top: 16px;
      font-size: 13px;
      font-weight: 700;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .issue-list {{
      margin: 10px 0 0;
      padding-left: 18px;
      color: var(--muted);
    }}
    .note, .empty {{
      margin-top: 12px;
      padding: 14px 16px;
      border-radius: 14px;
      border: 1px dashed var(--line);
      color: var(--muted);
      background: rgba(255,255,255,0.7);
    }}
    .note.warning {{
      border-style: solid;
      border-color: rgba(185, 65, 50, 0.22);
      background: rgba(185, 65, 50, 0.06);
      color: var(--red);
    }}
    .event-list {{
      display: grid;
      gap: 12px;
    }}
    .event-row {{
      padding: 16px;
    }}
    .event-meta {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 8px;
    }}
    .footer {{
      margin-top: 24px;
      color: var(--muted);
      font-size: 13px;
      text-align: center;
    }}
    @media (max-width: 900px) {{
      .hero-grid, .grid, .focus-list, .device-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">Monitoring Snapshot</div>
          <h1>{SITE_TITLE}</h1>
          <div>自动生成的设备状态摘要页，可由本地系统通过 GitHub Actions 同步发布。</div>
          <div class="hero-meta">
            <div class="pill">生成时间：{html.escape(snapshot["generated_at"])}</div>
            <div class="pill">共享网关：{html.escape(gateway_status)} / {html.escape(str(gateway["port"]))}{html.escape(gateway["path"])}</div>
            <div class="pill">Agent：{html.escape(agent["mode"])} / {html.escape(agent["model"])}</div>
          </div>
          {gateway_error}
        </div>
        <div class="panel" style="margin-top: 0;">
          <h2>客户端目标</h2>
          <div class="note">
            推荐上报地址：{html.escape(gateway["client_target"]["host"])}:{html.escape(str(gateway["client_target"]["port"]))}{html.escape(gateway["client_target"]["path"])}
          </div>
          <div class="note">
            Manager PID：{html.escape(str(gateway.get("manager_pid") or "-"))}<br>
            监听地址：{html.escape(gateway["listen_host"])}:{html.escape(str(gateway["port"]))}{html.escape(gateway["path"])}
          </div>
        </div>
      </div>
    </section>

    <section class="grid">{count_cards}</section>

    <section class="panel">
      <h2>重点关注设备</h2>
      <div class="focus-list">{focus_markup}</div>
    </section>

    <section class="panel">
      <h2>全部设备摘要</h2>
      <div class="device-grid">{device_markup}</div>
    </section>

    <section class="panel">
      <h2>最近真实设备事件</h2>
      <div class="event-list">{event_markup}</div>
    </section>

    <div class="footer">
      原始结构化快照可直接查看 <a href="./status.json">status.json</a>
    </div>
  </div>
</body>
</html>"""


def _render_count_card(label: str, value: int, tone: str) -> str:
    return (
        f"<div class='count-card {tone}'>"
        f"<div class='count-label'>{html.escape(label)}</div>"
        f"<div class='count-value'>{value}</div>"
        "</div>"
    )


def _render_focus_device(device: dict[str, Any]) -> str:
    return (
        "<div class='focus-card'>"
        f"<div class='device-head'><strong>{html.escape(device['name'])}</strong>"
        f"<span class='badge {device['status']}'>{html.escape(_status_label(device['status']))}</span></div>"
        f"<div class='device-sub'>{html.escape(device['instance_id'])} / 风险 {html.escape(_risk_label(device['risk_level']))}</div>"
        f"<div class='note'>{html.escape(device['summary'] or '暂无摘要')}</div>"
        "</div>"
    )


def _render_device_card(device: dict[str, Any]) -> str:
    metrics_markup = "".join(
        (
            "<div class='metric'>"
            f"<div class='metric-label'>{html.escape(metric['label'])}</div>"
            f"<div class='metric-value'>{html.escape(_format_metric(metric['value'], metric['unit']))}</div>"
            "</div>"
        )
        for metric in device["metrics"]
    )

    issues_markup = (
        "<ul class='issue-list'>"
        + "".join(f"<li>{html.escape(issue['message'])}</li>" for issue in device["issues"])
        + "</ul>"
        if device["issues"]
        else "<div class='note'>当前没有识别到异常项。</div>"
    )

    return (
        "<article class='device-card'>"
        "<div class='device-head'>"
        f"<div><h3 class='device-name'>{html.escape(device['name'])}</h3>"
        f"<div class='device-sub'>{html.escape(device['instance_id'])} / {html.escape(device['category_name'])} / {html.escape(device['template_name'])}</div></div>"
        f"<span class='badge {device['status']}'>{html.escape(_status_label(device['status']))}</span>"
        "</div>"
        f"<div class='device-sub'>在线状态：{html.escape(DEVICE_STATUS_LABELS.get(device['device_status'], device['device_status']))} / 风险等级：{html.escape(_risk_label(device['risk_level']))}</div>"
        f"<div class='device-sub'>最后心跳：{html.escape(device['last_heartbeat'] or '暂无')}</div>"
        f"<div class='metric-grid'>{metrics_markup}</div>"
        "<div class='section-label'>异常摘要</div>"
        f"{issues_markup}"
        "<div class='section-label'>报告摘录</div>"
        f"<div class='note'>{html.escape(device['report_excerpt'])}</div>"
        "</article>"
    )


def _render_event_row(event: dict[str, Any]) -> str:
    metric_text = " / ".join(f"{key}={value}" for key, value in event["metrics"].items()) or "无指标"
    return (
        "<div class='event-row'>"
        "<div class='event-head'>"
        f"<strong>{html.escape(event['device_name'])}</strong>"
        f"<span>{html.escape(event['timestamp'])}</span>"
        "</div>"
        f"<div class='event-meta'>{html.escape(event['instance_id'])}</div>"
        f"<div class='note'>{html.escape(metric_text)}</div>"
        "</div>"
    )


def _format_metric(value: float | None, unit: str) -> str:
    if value is None:
        return "-"
    return f"{value}{unit}"


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def _risk_label(risk_level: str) -> str:
    return RISK_LABELS.get(risk_level, risk_level)


def _device_sort_key(status: str, risk_level: str, name: str) -> tuple[int, int, str]:
    status_weight = {"critical": 0, "offline": 1, "warning": 2, "normal": 3, "unknown": 4}
    risk_weight = {"high": 0, "medium": 1, "low": 2, "unknown": 3, "-": 4}
    return (
        status_weight.get(status, 9),
        risk_weight.get(risk_level, 9),
        name,
    )


def _truncate_text(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."

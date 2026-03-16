"""Local dashboard agent utilities for contextual Q&A."""

from __future__ import annotations

from statistics import mean

from app.agent.report_generator import generate_report


STATUS_LABELS = {
    "normal": "正常",
    "warning": "预警",
    "critical": "严重异常",
    "offline": "离线",
    "unknown": "未知",
}
RISK_LABELS = {"low": "低", "medium": "中", "high": "高", "unknown": "未知", "-": "-"}
DEVICE_STATUS_LABELS = {"online": "在线", "offline": "离线"}

COMMON_METRIC_SYNONYMS = {
    "temperature": ["温度", "temp"],
    "voltage": ["电压"],
    "current": ["电流", "current"],
    "humidity": ["湿度"],
    "cpu_usage": ["cpu", "处理器", "cpu使用率", "cpu占用"],
    "memory_usage": ["内存", "memory", "ram"],
    "disk_activity": ["磁盘", "disk", "磁盘活动", "磁盘活动率"],
    "gpu_usage": ["gpu", "显卡", "gpu使用率", "gpu占用"],
}

FLEET_KEYWORDS = ["总览", "总体", "整体", "全部", "所有设备", "设备总数", "在线设备", "异常设备", "高风险", "离线设备"]
ALERT_KEYWORDS = ["异常", "告警", "高风险", "离线"]
CAUSE_KEYWORDS = ["原因", "为什么", "建议", "怎么处理", "处置", "怎么办", "风险"]
TREND_KEYWORDS = ["趋势", "曲线", "变化", "波动", "最近", "过去", "历史"]
CURRENT_DEVICE_KEYWORDS = ["这台", "这个设备", "默认设备", "当前设备"]


def build_agent_context(runtime, settings: dict, selected_device_id: str, history_window: int) -> dict:
    overview_rows = runtime.get_overview_rows()
    devices: dict[str, dict] = {}

    for device in settings["devices"]:
        instance_id = device["instance_id"]
        snapshot = runtime.get_device_snapshot(instance_id)
        template = snapshot["template"]
        latest_analysis = snapshot["analysis"]
        metric_definitions = [metric.to_dict() for metric in template.metrics]
        report = "当前暂无可展示的分析结果。"
        if latest_analysis is not None:
            report = generate_report(latest_analysis, metric_definitions=metric_definitions)

        devices[instance_id] = {
            "instance_id": instance_id,
            "device_name": snapshot["config"].name,
            "template_id": template.template_id,
            "template_display_name": template.display_name,
            "category_name": template.category_name,
            "source_type": template.source_type,
            "metrics": metric_definitions,
            "latest_point": None if snapshot["point"] is None else snapshot["point"].to_dict(),
            "latest_analysis": latest_analysis,
            "history": [point.to_dict() for point in runtime.get_device_history(instance_id, limit=history_window)],
            "last_heartbeat": snapshot["last_heartbeat"],
            "report": report,
        }

    total_devices = len(overview_rows)
    offline_devices = sum(1 for row in overview_rows if row["device_status"] == "offline")
    abnormal_devices = sum(1 for row in overview_rows if row["status"] in ("warning", "critical", "offline"))
    high_risk_devices = sum(1 for row in overview_rows if row["risk_level"] == "high")

    return {
        "selected_device_id": selected_device_id,
        "history_window": history_window,
        "overview_rows": overview_rows,
        "counts": {
            "total_devices": total_devices,
            "online_devices": total_devices - offline_devices,
            "offline_devices": offline_devices,
            "abnormal_devices": abnormal_devices,
            "high_risk_devices": high_risk_devices,
        },
        "devices": devices,
    }


def generate_agent_reply(user_message: str, context: dict) -> str:
    message = (user_message or "").strip()
    if not message:
        return _build_help_reply(context)

    device_id, matched_explicitly = _match_device(message=message, context=context)
    selected_device_prompt = any(keyword in message for keyword in CURRENT_DEVICE_KEYWORDS)
    if _is_fleet_intent(message) and not matched_explicitly and not selected_device_prompt:
        return _build_fleet_reply(message=message, context=context)

    if device_id is None:
        return _build_help_reply(context)

    return _build_device_reply(
        message=message,
        context=context,
        device_id=device_id,
        matched_explicitly=matched_explicitly,
    )


def build_agent_hint(context: dict) -> str:
    selected_device_id = context.get("selected_device_id")
    device = context.get("devices", {}).get(selected_device_id)
    if device is None:
        return "你可以直接问“当前有哪些异常设备”或“这台设备现在怎么样”。"
    return (
        f"默认上下文设备是 {device['device_name']}（{device['instance_id']}）。"
        "你可以直接问“这台设备现在怎么样”“最近的 GPU 趋势如何”或“当前有哪些异常设备”。"
    )


def _build_help_reply(context: dict) -> str:
    selected_device_id = context.get("selected_device_id")
    device = context.get("devices", {}).get(selected_device_id)
    device_name = device["device_name"] if device else "当前设备"
    return (
        "我已经接入当前监测面板的设备上下文。\n"
        f"默认会优先参考 {device_name} 的最新状态。\n"
        "你可以这样问我：\n"
        "1. 当前有哪些异常设备？\n"
        "2. 这台设备现在怎么样？\n"
        "3. personal_pc_real-b6553a2f 的 GPU 趋势如何？\n"
        "4. 这台设备为什么告警，建议怎么处理？"
    )


def _build_fleet_reply(message: str, context: dict) -> str:
    counts = context["counts"]
    rows = context["overview_rows"]
    abnormal_rows = [row for row in rows if row["status"] in ("warning", "critical", "offline")]
    high_risk_rows = [row for row in rows if row["risk_level"] == "high"]
    offline_rows = [row for row in rows if row["device_status"] == "offline"]

    lines = [
        (
            f"当前共监测 {counts['total_devices']} 台设备，在线 {counts['online_devices']} 台，"
            f"异常 {counts['abnormal_devices']} 台，高风险 {counts['high_risk_devices']} 台，离线 {counts['offline_devices']} 台。"
        )
    ]

    if any(keyword in message for keyword in ["高风险", "严重"]):
        target_rows = high_risk_rows
        lead = "当前高风险设备如下："
    elif "离线" in message:
        target_rows = offline_rows
        lead = "当前离线设备如下："
    else:
        target_rows = abnormal_rows
        lead = "当前需要优先关注的设备如下："

    if not target_rows:
        lines.append("当前没有需要特别处理的对应设备，整体运行较平稳。")
        return "\n".join(lines)

    lines.append(lead)
    for index, row in enumerate(target_rows[:5], start=1):
        lines.append(
            f"{index}. {row['device_name']}（{row['instance_id']}），状态 {STATUS_LABELS.get(row['status'], row['status'])}，"
            f"风险等级 {RISK_LABELS.get(row['risk_level'], row['risk_level'])}。"
        )

    if len(target_rows) > 5:
        lines.append(f"其余还有 {len(target_rows) - 5} 台，可继续点名设备让我展开分析。")

    return "\n".join(lines)


def _build_device_reply(message: str, context: dict, device_id: str, matched_explicitly: bool) -> str:
    device = context["devices"][device_id]
    analysis = device.get("latest_analysis") or {}
    point = device.get("latest_point") or {}
    metric_definitions = device.get("metrics", [])
    metric = _detect_metric(message, metric_definitions)

    lines: list[str] = []
    if not matched_explicitly and device_id == context.get("selected_device_id"):
        lines.append(f"没有识别到明确设备名称，我先按当前选中设备 {device['device_name']} 来回答。")

    lines.append(f"已定位到设备：{device['device_name']}（{device['instance_id']}）。")
    lines.append(
        f"当前在线状态：{DEVICE_STATUS_LABELS.get(analysis.get('device_status', point.get('device_status', 'unknown')), '未知')}，"
        f"诊断状态：{STATUS_LABELS.get(analysis.get('status', 'unknown'), '未知')}，"
        f"风险等级：{RISK_LABELS.get(analysis.get('risk_level', 'unknown'), '未知')}。"
    )

    metric_summary = _build_metric_summary(point.get("metrics", {}), metric_definitions)
    if metric_summary:
        lines.append(f"最新指标：{metric_summary}。")

    if metric is not None:
        lines.append(_build_metric_trend_reply(device=device, metric=metric))
    elif _message_requests_cause_or_action(message):
        lines.append(_build_issue_reply(device=device))
    else:
        lines.append(_build_device_summary_reply(device=device))

    return "\n".join(line for line in lines if line)


def _build_device_summary_reply(device: dict) -> str:
    analysis = device.get("latest_analysis") or {}
    issues = analysis.get("issues", [])
    if not issues:
        return analysis.get("summary") or "当前没有识别到明显异常，建议继续观察后续状态变化。"

    issue_text = "；".join(issue["message"] for issue in issues[:2])
    summary = analysis.get("summary") or "检测到设备存在异常。"
    return f"{summary} 主要问题包括：{issue_text}。如需我展开原因或建议，可以继续追问。"


def _build_issue_reply(device: dict) -> str:
    analysis = device.get("latest_analysis") or {}
    issues = analysis.get("issues", [])
    if not issues:
        return "当前没有识别到异常项，暂时不需要额外处置，建议继续跟踪趋势变化。"

    lines = ["我整理了当前最值得关注的问题和建议："]
    for index, issue in enumerate(issues[:3], start=1):
        lines.append(f"{index}. {issue['message']} 建议：{issue['suggestion']}")
    return "\n".join(lines)


def _build_metric_trend_reply(device: dict, metric: dict) -> str:
    history = device.get("history", [])
    metric_id = metric["metric_id"]
    label = metric.get("label", metric_id)
    unit = metric.get("unit", "")
    values = [point.get("metrics", {}).get(metric_id) for point in history]
    values = [value for value in values if value is not None]

    if not values:
        return f"{label} 当前没有可用历史数据，暂时无法判断趋势。"

    sample = values[-min(len(values), 12) :]
    current_value = sample[-1]
    minimum = min(sample)
    maximum = max(sample)
    average = mean(sample)

    if len(sample) == 1:
        trend_label = "样本不足，暂不判断趋势"
    else:
        split_index = max(1, len(sample) // 2)
        early_mean = mean(sample[:split_index])
        late_mean = mean(sample[split_index:])
        delta = late_mean - early_mean
        dynamic_threshold = max(0.6, (maximum - minimum) * 0.18)
        if abs(delta) <= dynamic_threshold:
            trend_label = "整体平稳"
        elif delta > 0:
            trend_label = "呈上升趋势"
        else:
            trend_label = "呈下降趋势"

    return (
        f"最近 {len(sample)} 个有效点的 {label} 当前值为 {current_value}{unit}，"
        f"均值约 {round(average, 1)}{unit}，波动区间 {round(minimum, 1)} 到 {round(maximum, 1)}{unit}，"
        f"趋势判断为：{trend_label}。"
    )


def _build_metric_summary(metrics: dict, metric_definitions: list[dict]) -> str:
    parts: list[str] = []
    for metric in metric_definitions:
        value = metrics.get(metric["metric_id"])
        if value is None:
            continue
        parts.append(f"{metric['label']} {value}{metric.get('unit', '')}")
    return "，".join(parts)


def _match_device(message: str, context: dict) -> tuple[str | None, bool]:
    lowered = message.lower()
    devices = context.get("devices", {})

    for device_id, device in devices.items():
        device_name = device["device_name"].lower()
        if device_id.lower() in lowered or device_name in lowered:
            return device_id, True

    if any(keyword in message for keyword in CURRENT_DEVICE_KEYWORDS):
        return context.get("selected_device_id"), False

    if len(devices) == 1:
        return next(iter(devices.keys())), False

    selected_device_id = context.get("selected_device_id")
    if selected_device_id is not None:
        return selected_device_id, False

    return None, False


def _detect_metric(message: str, metric_definitions: list[dict]) -> dict | None:
    lowered = message.lower()
    for metric in metric_definitions:
        metric_id = metric["metric_id"]
        keywords = COMMON_METRIC_SYNONYMS.get(metric_id, [])
        keywords = [keyword.lower() for keyword in keywords] + [metric_id.lower(), metric.get("label", "").lower()]
        if any(keyword and keyword in lowered for keyword in keywords):
            return metric
    return None


def _is_fleet_intent(message: str) -> bool:
    return any(keyword in message for keyword in FLEET_KEYWORDS) or (
        any(keyword in message for keyword in ALERT_KEYWORDS) and "设备" in message
    )


def _message_requests_cause_or_action(message: str) -> bool:
    return any(keyword in message for keyword in CAUSE_KEYWORDS)

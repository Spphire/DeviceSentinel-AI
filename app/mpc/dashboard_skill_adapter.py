"""MPC-style adapter and local orchestration for the dashboard skill registry."""

from __future__ import annotations

from typing import Any

from app.agent.dashboard_tools import (
    COMMON_METRIC_SYNONYMS,
    CURRENT_DEVICE_KEYWORDS,
    DEVICE_STATUS_LABELS,
    RISK_LABELS,
    STATUS_LABELS,
    build_metric_summary,
    get_dashboard_tool_definitions,
    invoke_dashboard_tool,
)


FLEET_KEYWORDS = ["总览", "总体", "整体", "全部", "所有设备", "设备总数", "在线设备", "异常设备", "高风险", "离线设备"]
ALERT_KEYWORDS = ["异常", "告警", "高风险", "离线"]
CAUSE_KEYWORDS = ["原因", "为什么", "建议", "怎么处理", "处置", "怎么办", "风险"]


def get_dashboard_skill_definitions() -> list[dict]:
    return get_dashboard_tool_definitions()


def invoke_dashboard_skill(name: str, arguments: dict, context: dict) -> dict:
    return invoke_dashboard_tool(name=name, arguments=arguments, context=context)


def generate_local_skill_reply(user_message: str, context: dict[str, Any]) -> str:
    message = (user_message or "").strip()
    if not message:
        return build_local_skill_help_reply(context)

    device_id, matched_explicitly = match_device_reference(message=message, context=context)
    selected_device_prompt = any(keyword in message for keyword in CURRENT_DEVICE_KEYWORDS)
    if is_fleet_intent(message) and not matched_explicitly and not selected_device_prompt:
        focus = determine_overview_focus(message)
        result = invoke_dashboard_skill("get_dashboard_overview", {"focus": focus}, context)
        return _format_fleet_reply(message=message, result=result)

    if device_id is None:
        return build_local_skill_help_reply(context)

    detail_arguments = {"device_query": device_id} if matched_explicitly else {}
    detail_result = invoke_dashboard_skill("get_device_detail", detail_arguments, context)
    if not detail_result.get("ok"):
        return _format_tool_error(detail_result)

    device = detail_result["device"]
    lines: list[str] = []
    if detail_result.get("resolved_by_default"):
        lines.append(f"没有识别到明确设备名称，我先按当前选中设备 {device['device_name']} 来回答。")

    lines.append(f"已定位到设备：{device['device_name']}（{device['instance_id']}）。")
    lines.append(
        f"当前在线状态：{device['device_status']}，"
        f"诊断状态：{device['status']}，"
        f"风险等级：{device['risk_level']}。"
    )

    metric_summary = device.get("metric_summary")
    if metric_summary:
        lines.append(f"最新指标：{metric_summary}。")

    metric = detect_metric_reference(message, device.get("supported_metrics", []))
    if metric is not None:
        trend_arguments = {"metric_query": metric.get("label", metric["metric_id"])}
        if matched_explicitly:
            trend_arguments["device_query"] = device_id
        trend_result = invoke_dashboard_skill("get_device_metric_trend", trend_arguments, context)
        lines.append(_format_metric_trend_reply(trend_result))
    elif message_requests_cause_or_action(message):
        issue_arguments = {"device_query": device_id} if matched_explicitly else {}
        issue_result = invoke_dashboard_skill("get_device_issue_analysis", issue_arguments, context)
        lines.append(_format_issue_reply(issue_result))
    else:
        lines.append(_format_device_summary_reply(device))

    return "\n".join(line for line in lines if line)


def build_local_skill_help_reply(context: dict[str, Any]) -> str:
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


def determine_overview_focus(message: str) -> str:
    if any(keyword in message for keyword in ["高风险", "严重"]):
        return "high_risk"
    if "离线" in message:
        return "offline"
    if any(keyword in message for keyword in ALERT_KEYWORDS):
        return "abnormal"
    return "all"


def match_device_reference(message: str, context: dict[str, Any]) -> tuple[str | None, bool]:
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


def detect_metric_reference(message: str, metric_definitions: list[dict[str, Any]]) -> dict[str, Any] | None:
    lowered = message.lower()
    for metric in metric_definitions:
        metric_id = metric["metric_id"]
        keywords = COMMON_METRIC_SYNONYMS.get(metric_id, [])
        searchable = [keyword.lower() for keyword in keywords] + [metric_id.lower(), metric.get("label", "").lower()]
        if any(keyword and keyword in lowered for keyword in searchable):
            return metric
    return None


def is_fleet_intent(message: str) -> bool:
    return any(keyword in message for keyword in FLEET_KEYWORDS) or (
        any(keyword in message for keyword in ALERT_KEYWORDS) and "设备" in message
    )


def message_requests_cause_or_action(message: str) -> bool:
    return any(keyword in message for keyword in CAUSE_KEYWORDS)


def _format_fleet_reply(message: str, result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return _format_tool_error(result)

    counts = result.get("counts", {})
    rows = result.get("devices", [])
    focus = result.get("focus", "all")
    lines = [
        (
            f"当前共监测 {counts.get('total_devices', 0)} 台设备，在线 {counts.get('online_devices', 0)} 台，"
            f"异常 {counts.get('abnormal_devices', 0)} 台，高风险 {counts.get('high_risk_devices', 0)} 台，"
            f"离线 {counts.get('offline_devices', 0)} 台。"
        )
    ]

    if focus == "high_risk":
        lead = "当前高风险设备如下："
    elif focus == "offline":
        lead = "当前离线设备如下："
    elif focus == "abnormal":
        lead = "当前需要优先关注的设备如下："
    else:
        lead = "当前设备概览如下："

    if not rows:
        lines.append("当前没有需要特别处理的对应设备，整体运行较平稳。")
        return "\n".join(lines)

    lines.append(lead)
    for index, row in enumerate(rows[:5], start=1):
        metric_summary = row.get("metric_summary") or "暂无指标"
        lines.append(
            f"{index}. {row['device_name']}（{row['instance_id']}），状态 {row['status']}，"
            f"风险等级 {row['risk_level']}，最新指标 {metric_summary}。"
        )

    if focus != "all" and len(rows) > 5:
        lines.append(f"其余还有 {len(rows) - 5} 台，可继续点名设备让我展开分析。")
    elif focus == "all" and len(rows) > 5:
        lines.append(f"当前共返回前 5 台设备摘要，如需异常/离线/高风险列表可以继续追问。")

    return "\n".join(lines)


def _format_metric_trend_reply(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return _format_tool_error(result)

    return (
        f"最近 {result['sample_points']} 个有效点的 {result['metric_label']} 当前值为 "
        f"{result['current_value']}{result['unit']}，均值约 {result['average']}{result['unit']}，"
        f"波动区间 {result['minimum']} 到 {result['maximum']}{result['unit']}，"
        f"趋势判断为：{result['trend_label']}。"
    )


def _format_issue_reply(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return _format_tool_error(result)

    issues = result.get("issues", [])
    if not issues:
        return "当前没有识别到异常项，暂时不需要额外处置，建议继续跟踪趋势变化。"

    lines = ["我整理了当前最值得关注的问题和建议："]
    for index, issue in enumerate(issues[:3], start=1):
        lines.append(f"{index}. {issue['message']} 建议：{issue['suggestion']}")
    return "\n".join(lines)


def _format_device_summary_reply(device: dict[str, Any]) -> str:
    summary = (device.get("summary") or "").strip()
    report = (device.get("report") or "").strip()
    if summary:
        return summary
    if report:
        compact_report = " ".join(report.split())
        return compact_report
    return "当前没有识别到明显异常，建议继续观察后续状态变化。"


def _format_tool_error(result: dict[str, Any]) -> str:
    error = result.get("error") or "当前无法完成查询。"
    available_devices = result.get("available_devices") or []
    if not available_devices:
        return error

    options = "；".join(
        f"{item['device_name']}（{item['instance_id']}）"
        for item in available_devices[:5]
    )
    return f"{error} 可用设备包括：{options}。"

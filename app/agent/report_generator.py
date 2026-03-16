"""Generate SGCC-style natural language reports from structured analysis results."""

from __future__ import annotations

from app.config.thresholds import STANDARD_REFERENCE


STATUS_LABELS = {
    "normal": "正常",
    "warning": "预警",
    "critical": "严重异常",
    "offline": "离线",
    "unknown": "未知",
}
RISK_LABELS = {"low": "低", "medium": "中", "high": "高", "unknown": "未知"}


def _format_metric(value: float | None, unit: str) -> str:
    if value is None:
        return "-"
    return f"{value}{unit}"


def _format_metric_summary(analysis_result: dict, metric_definitions: list[dict] | None = None) -> str:
    metrics = analysis_result.get("metrics", {})
    metric_labels = analysis_result.get("metric_labels") or {}

    if metric_definitions:
        ordered_metrics = metric_definitions
    else:
        ordered_metrics = [
            {"metric_id": metric_id, "label": metric_labels.get(metric_id, metric_id), "unit": ""}
            for metric_id in metrics.keys()
        ]

    parts: list[str] = []
    for item in ordered_metrics:
        metric_id = item["metric_id"]
        label = item.get("label", metric_id)
        unit = item.get("unit", "")
        parts.append(f"{label} {_format_metric(metrics.get(metric_id), unit)}")

    return "，".join(parts) if parts else "暂无有效指标数据"


def generate_report(analysis_result: dict, metric_definitions: list[dict] | None = None) -> str:
    issues = analysis_result.get("issues", [])
    device_id = analysis_result.get("device_id", "UNKNOWN")
    device_name = analysis_result.get("device_name") or device_id
    category_name = analysis_result.get("category_name") or "设备"
    status = analysis_result.get("status", "unknown")
    risk_level = analysis_result.get("risk_level", "unknown")
    device_status = analysis_result.get("device_status", "online")
    last_heartbeat = analysis_result.get("last_heartbeat")
    status_label = STATUS_LABELS.get(status, status)
    risk_label = RISK_LABELS.get(risk_level, risk_level)

    if device_status == "offline" or status == "offline":
        header = (
            f"设备名称：{device_name}\n"
            f"设备编号：{device_id}\n"
            f"设备类型：{category_name}\n"
            f"运行状态：{STATUS_LABELS['offline']}\n"
            f"风险等级：{RISK_LABELS['high']}\n"
            f"最后上报时间：{last_heartbeat or '暂无有效心跳'}。"
        )
        body = (
            "智能研判结论：系统当前未接收到设备最新遥测数据，判定该设备存在离线或通信中断现象。"
            "在离线期间无法继续进行有效指标分析。\n"
            "处置建议：建议优先检查终端供电状态、通信链路、采集模块在线情况，并结合现场巡视确认设备是否停运或宕机。"
        )
        footer = (
            f"规范依据：本报告引用 {STANDARD_REFERENCE['code']} 相关运维表述进行规范化生成，"
            "可作为教学演示与课程设计样例。"
        )
        return f"{header}\n{body}\n{footer}"

    header = (
        f"设备名称：{device_name}\n"
        f"设备编号：{device_id}\n"
        f"设备类型：{category_name}\n"
        f"运行状态：{status_label}\n"
        f"风险等级：{risk_label}\n"
        f"监测数据：{_format_metric_summary(analysis_result, metric_definitions)}。"
    )

    if not issues:
        body = (
            "智能研判结论：当前设备运行总体平稳，主要参数均在设定阈值范围内，"
            "建议继续按常规周期开展巡视与状态跟踪。"
        )
    else:
        issue_lines = "\n".join(
            f"{index}. {issue['message']} 建议：{issue['suggestion']}"
            for index, issue in enumerate(issues, start=1)
        )
        body = (
            "智能研判结论：系统识别到以下异常情况：\n"
            f"{issue_lines}\n"
            "综合建议：建议运维人员结合现场红外测温、负荷核查和保护动作记录开展复核，"
            "必要时执行缺陷闭环处置。"
        )

    footer = (
        f"规范依据：本报告引用 {STANDARD_REFERENCE['code']} 相关运维表述进行规范化生成，"
        "可作为教学演示与课程设计样例。"
    )

    return f"{header}\n{body}\n{footer}"

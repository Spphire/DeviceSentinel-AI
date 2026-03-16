"""Template-aware telemetry analysis for simulated and real devices."""

from __future__ import annotations

from app.analysis.analyzer import analyze_device_status
from app.config.thresholds import STANDARD_REFERENCE
from app.models import AnalysisIssue, AnalysisResult, DeviceReading, DeviceTelemetryPoint, DeviceTemplateDefinition


def _build_offline_result(
    template: DeviceTemplateDefinition,
    point: DeviceTelemetryPoint,
    last_heartbeat: str | None,
) -> AnalysisResult:
    issue = AnalysisIssue(
        category="connectivity",
        severity="high",
        message="设备当前处于离线状态，系统暂未接收到最新遥测数据。",
        suggestion="建议检查设备供电、通信链路、采集程序或上报服务是否正常运行。",
        standard_reference=STANDARD_REFERENCE["code"],
    )
    return AnalysisResult(
        device_id=point.instance_id,
        status="offline",
        risk_level="high",
        issues=[issue],
        metrics={metric.metric_id: None for metric in template.metrics},
        summary="系统判定该设备已离线，建议优先恢复设备在线与通信状态。",
        device_status="offline",
        last_heartbeat=last_heartbeat,
        device_name=point.device_name,
        template_id=template.template_id,
        template_display_name=template.display_name,
        category_name=template.category_name,
        metric_labels=point.metric_labels,
    )


def _build_threshold_message(label: str, value: float, threshold: float, direction: str, unit: str) -> str:
    comparator = "超过" if direction == "high" else "低于"
    return f"{label}达到 {value}{unit}，{comparator} {threshold}{unit} 阈值。"


def _analyze_threshold_template(
    template: DeviceTemplateDefinition,
    point: DeviceTelemetryPoint,
) -> AnalysisResult:
    metric_map = {metric.metric_id: metric for metric in template.metrics}
    issues: list[AnalysisIssue] = []
    rules = template.analysis.get("metric_rules", {})

    for metric_id, rule in rules.items():
        value = point.metrics.get(metric_id)
        metric = metric_map.get(metric_id)
        if value is None or metric is None:
            continue

        high = rule.get("high")
        low = rule.get("low")
        severity = rule.get("severity", "medium")
        suggestion = rule.get("suggestion", "建议结合现场情况进行进一步排查。")
        label = rule.get("label", metric.label)

        if high is not None and value > high:
            issues.append(
                AnalysisIssue(
                    category=metric_id,
                    severity=severity,
                    message=_build_threshold_message(label, value, high, "high", metric.unit),
                    suggestion=suggestion,
                    standard_reference=STANDARD_REFERENCE["code"],
                )
            )
        elif low is not None and value < low:
            issues.append(
                AnalysisIssue(
                    category=metric_id,
                    severity=severity,
                    message=_build_threshold_message(label, value, low, "low", metric.unit),
                    suggestion=suggestion,
                    standard_reference=STANDARD_REFERENCE["code"],
                )
            )

    if not issues:
        status = "normal"
        risk_level = "low"
        summary = template.analysis.get("summary_normal", "设备运行指标整体正常。")
    else:
        high_severity_count = sum(1 for issue in issues if issue.severity == "high")
        status = "critical" if len(issues) > 1 or high_severity_count else "warning"
        risk_level = "high" if high_severity_count or len(issues) > 1 else "medium"
        summary = "检测到设备存在运行异常，建议结合现场环境或终端状态尽快复核。"

    return AnalysisResult(
        device_id=point.instance_id,
        status=status,
        risk_level=risk_level,
        issues=issues,
        metrics=point.metrics,
        summary=summary,
        device_status="online",
        last_heartbeat=point.timestamp,
        device_name=point.device_name,
        template_id=template.template_id,
        template_display_name=template.display_name,
        category_name=template.category_name,
        metric_labels=point.metric_labels,
    )


def _analyze_sgcc_template(template: DeviceTemplateDefinition, point: DeviceTelemetryPoint) -> AnalysisResult:
    reading = DeviceReading(
        device_id=point.instance_id,
        temperature=float(point.metrics.get("temperature", 0.0)),
        voltage=float(point.metrics.get("voltage", 0.0)),
        current=float(point.metrics.get("current", 0.0)),
        timestamp=point.timestamp,
    )
    result = analyze_device_status(reading)
    result.device_id = point.instance_id
    result.device_name = point.device_name
    result.template_id = template.template_id
    result.template_display_name = template.display_name
    result.category_name = template.category_name
    result.metric_labels = point.metric_labels
    result.last_heartbeat = point.timestamp
    return result


def analyze_device_point(
    template: DeviceTemplateDefinition,
    point: DeviceTelemetryPoint,
    last_heartbeat: str | None = None,
) -> AnalysisResult:
    if point.device_status == "offline":
        return _build_offline_result(template=template, point=point, last_heartbeat=last_heartbeat)

    analysis_kind = template.analysis.get("kind", "threshold")
    if analysis_kind == "sgcc":
        return _analyze_sgcc_template(template=template, point=point)
    return _analyze_threshold_template(template=template, point=point)

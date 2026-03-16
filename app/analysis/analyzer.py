"""Rule-based anomaly analysis for electrical device monitoring."""

from __future__ import annotations

from datetime import datetime

from app.config.thresholds import DEFAULT_THRESHOLDS, STANDARD_REFERENCE
from app.models import AnalysisIssue, AnalysisResult, DeviceReading, SimulationPoint


def analyze_device_status(reading: DeviceReading) -> AnalysisResult:
    """Analyze a device reading and return a structured result for MPC/Agent usage."""
    issues: list[AnalysisIssue] = []
    thresholds = DEFAULT_THRESHOLDS

    if reading.temperature > thresholds.over_temperature_celsius:
        issues.append(
            AnalysisIssue(
                category="temperature",
                severity="high",
                message=f"设备温度达到 {reading.temperature}℃，超过 {thresholds.over_temperature_celsius}℃ 阈值，判定为过温风险。",
                suggestion="建议立即安排现场测温复核，检查母排连接点、柜内散热和负荷情况。",
                standard_reference=STANDARD_REFERENCE["code"],
            )
        )

    if reading.voltage > thresholds.voltage_upper_limit:
        issues.append(
            AnalysisIssue(
                category="voltage",
                severity="medium",
                message=(
                    f"设备电压为 {reading.voltage}V，高于 {thresholds.voltage_upper_limit:.1f}V 上限，"
                    "存在电压偏高波动异常。"
                ),
                suggestion="建议核查分支回路负载平衡情况，并检查电压调节与接线状态。",
                standard_reference=STANDARD_REFERENCE["code"],
            )
        )
    elif reading.voltage < thresholds.voltage_lower_limit:
        issues.append(
            AnalysisIssue(
                category="voltage",
                severity="medium",
                message=(
                    f"设备电压为 {reading.voltage}V，低于 {thresholds.voltage_lower_limit:.1f}V 下限，"
                    "存在电压偏低波动异常。"
                ),
                suggestion="建议检查供电侧电压质量、回路压降以及接触点发热隐患。",
                standard_reference=STANDARD_REFERENCE["code"],
            )
        )

    if reading.current > thresholds.over_current_ampere:
        issues.append(
            AnalysisIssue(
                category="current",
                severity="high",
                message=f"设备电流达到 {reading.current}A，超过 {thresholds.over_current_ampere}A 阈值，存在过载风险。",
                suggestion="建议排查突增负荷、分支回路短时冲击及保护装置动作情况。",
                standard_reference=STANDARD_REFERENCE["code"],
            )
        )

    if not issues:
        status = "normal"
        risk_level = "low"
        summary = "设备运行参数处于设定阈值范围内，当前未发现明显异常。"
    else:
        status = "warning" if len(issues) == 1 else "critical"
        risk_level = "medium" if len(issues) == 1 else "high"
        summary = "检测到设备存在异常运行特征，建议结合现场巡视尽快复核。"

    return AnalysisResult(
        device_id=reading.device_id,
        status=status,
        risk_level=risk_level,
        issues=issues,
        metrics={
            "temperature": reading.temperature,
            "voltage": reading.voltage,
            "current": reading.current,
        },
        summary=summary,
        device_status="online",
        last_heartbeat=reading.timestamp,
    )


def analyze_offline_status(point: SimulationPoint, last_heartbeat: str | None = None) -> AnalysisResult:
    """Analyze an offline simulation point as a communication/device outage event."""
    issue = AnalysisIssue(
        category="connectivity",
        severity="high",
        message="设备当前处于离线状态，系统未接收到最新遥测数据，存在通信中断或终端掉电风险。",
        suggestion="建议优先检查通信链路、采集终端供电、设备在线状态及现场网络环境。",
        standard_reference=STANDARD_REFERENCE["code"],
    )

    summary = "系统判定设备已离线，建议优先排查终端在线性与通信链路状态。"

    return AnalysisResult(
        device_id=point.device_id,
        status="offline",
        risk_level="high",
        issues=[issue],
        metrics={"temperature": None, "voltage": None, "current": None},
        summary=summary,
        device_status="offline",
        template_name=point.template_name,
        last_heartbeat=last_heartbeat,
    )


def analyze_simulation_point(point: SimulationPoint, last_heartbeat: str | None = None) -> AnalysisResult:
    """Analyze a simulation point, including device offline events."""
    if point.device_status == "offline":
        return analyze_offline_status(point=point, last_heartbeat=last_heartbeat)

    result = analyze_device_status(point.to_reading())
    result.template_name = point.template_name
    result.last_heartbeat = point.timestamp
    return result


def analyze_device_status_for_mpc(payload: dict) -> dict:
    """MPC Skill friendly wrapper using dict in/out."""
    device_status = payload.get("device_status", "online")
    if device_status == "offline":
        point = SimulationPoint(
            device_id=payload["device_id"],
            timestamp=payload.get("timestamp") or datetime.now().isoformat(timespec="seconds"),
            device_status="offline",
            template_name=payload.get("template_name", "offline"),
            temperature=None,
            voltage=None,
            current=None,
            fault_label="offline",
        )
        result = analyze_simulation_point(point=point, last_heartbeat=payload.get("last_heartbeat"))
        return result.to_dict()

    reading = DeviceReading(
        device_id=payload["device_id"],
        temperature=float(payload["temperature"]),
        voltage=float(payload["voltage"]),
        current=float(payload["current"]),
        timestamp=payload.get("timestamp") or datetime.now().isoformat(timespec="seconds"),
    )
    result = analyze_device_status(reading)
    return result.to_dict()

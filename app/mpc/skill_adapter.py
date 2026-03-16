"""MPC Skill style function definition and local invocation helpers."""

from __future__ import annotations

from app.analysis.analyzer import analyze_device_status_for_mpc


MPC_SKILL_FUNCTION = {
    "name": "analyze_electrical_device_status",
    "description": "分析低压电气设备运行状态，返回异常类型、风险等级和运维建议。",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string", "description": "设备编号"},
            "temperature": {"type": "number", "description": "设备温度，单位摄氏度"},
            "voltage": {"type": "number", "description": "设备电压，单位伏特"},
            "current": {"type": "number", "description": "设备电流，单位安培"},
            "timestamp": {"type": "string", "description": "采集时间，ISO 8601 格式"},
        },
        "required": ["device_id", "temperature", "voltage", "current"],
    },
}


def get_skill_definition() -> dict:
    return MPC_SKILL_FUNCTION


def invoke_local_skill(arguments: dict) -> dict:
    """Simulate MPC Skill local function execution."""
    return analyze_device_status_for_mpc(arguments)

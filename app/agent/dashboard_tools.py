"""Reusable dashboard tools for local rules, MPC skills, and LLM tool calling."""

from __future__ import annotations

from statistics import mean
from typing import Any


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
    "gpu_memory_usage": ["显存", "显存占用", "显存使用率", "gpu显存", "gpu内存", "vram"],
}
CURRENT_DEVICE_KEYWORDS = ["这台", "这个设备", "默认设备", "当前设备", "selected", "current"]


def get_dashboard_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "get_dashboard_overview",
            "description": "获取当前监测面板的总览统计，可按全部、异常、离线或高风险设备筛选。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "description": "查询重点，可选 all、abnormal、offline、high_risk。",
                        "enum": ["all", "abnormal", "offline", "high_risk"],
                    }
                },
                "required": ["focus"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "get_device_detail",
            "description": "按设备名称、实例 ID 或“当前设备/这台设备”等描述获取单设备详情。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "device_query": {
                        "type": "string",
                        "description": "设备名称、实例 ID，或类似“这台设备”的描述；留空时默认当前选中设备。",
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "get_device_metric_trend",
            "description": "查询指定设备某项指标的近期趋势、均值和波动区间。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "device_query": {
                        "type": "string",
                        "description": "设备名称、实例 ID，或类似“这台设备”的描述；留空时默认当前选中设备。",
                    },
                    "metric_query": {
                        "type": "string",
                        "description": "指标名称，如 GPU、CPU、温度、电压、湿度、内存等。",
                    },
                },
                "required": ["metric_query"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "get_device_issue_analysis",
            "description": "获取指定设备当前异常原因、风险等级和处置建议。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "device_query": {
                        "type": "string",
                        "description": "设备名称、实例 ID，或类似“这台设备”的描述；留空时默认当前选中设备。",
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    ]


def invoke_dashboard_tool(name: str, arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handlers = {
        "get_dashboard_overview": _tool_get_dashboard_overview,
        "get_device_detail": _tool_get_device_detail,
        "get_device_metric_trend": _tool_get_device_metric_trend,
        "get_device_issue_analysis": _tool_get_device_issue_analysis,
    }
    handler = handlers.get(name)
    if handler is None:
        return {"ok": False, "error": f"未知工具：{name}"}
    return handler(arguments=arguments or {}, context=context)


def resolve_device_query(
    device_query: str | None,
    context: dict[str, Any],
) -> tuple[str | None, bool]:
    devices = context.get("devices", {})
    selected_device_id = context.get("selected_device_id")
    query = (device_query or "").strip()
    lowered = query.lower()

    if not query:
        return _fallback_device_id(context), False

    if any(keyword in lowered for keyword in CURRENT_DEVICE_KEYWORDS) or any(keyword in query for keyword in CURRENT_DEVICE_KEYWORDS):
        return _fallback_device_id(context), False

    exact_matches: list[str] = []
    fuzzy_matches: list[str] = []
    for device_id, device in devices.items():
        device_name = device.get("device_name", "")
        device_name_lower = device_name.lower()
        if device_id.lower() == lowered or device_name_lower == lowered:
            exact_matches.append(device_id)
        elif lowered in device_id.lower() or lowered in device_name_lower:
            fuzzy_matches.append(device_id)

    if len(exact_matches) == 1:
        return exact_matches[0], True
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0], True
    if selected_device_id in devices and not exact_matches and not fuzzy_matches and len(devices) == 1:
        return selected_device_id, False
    return None, True


def resolve_metric_query(metric_query: str | None, metric_definitions: list[dict[str, Any]]) -> dict[str, Any] | None:
    query = (metric_query or "").strip().lower()
    if not query:
        return None

    exact_matches: list[dict[str, Any]] = []
    fuzzy_matches: list[dict[str, Any]] = []
    for metric in metric_definitions:
        metric_id = metric["metric_id"]
        keywords = COMMON_METRIC_SYNONYMS.get(metric_id, [])
        searchable = [metric_id.lower(), metric.get("label", "").lower(), *[keyword.lower() for keyword in keywords]]
        if any(keyword == query for keyword in searchable if keyword):
            exact_matches.append(metric)
        elif any(query in keyword for keyword in searchable if keyword):
            fuzzy_matches.append(metric)

    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]
    return None


def compute_metric_trend(device: dict[str, Any], metric: dict[str, Any]) -> dict[str, Any]:
    history = device.get("history", [])
    metric_id = metric["metric_id"]
    values = [point.get("metrics", {}).get(metric_id) for point in history]
    values = [value for value in values if value is not None]
    label = metric.get("label", metric_id)
    unit = metric.get("unit", "")

    if not values:
        return {
            "ok": False,
            "metric_id": metric_id,
            "metric_label": label,
            "unit": unit,
            "error": f"{label} 当前没有可用历史数据。",
        }

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

    return {
        "ok": True,
        "metric_id": metric_id,
        "metric_label": label,
        "unit": unit,
        "sample_points": len(sample),
        "current_value": current_value,
        "average": round(average, 1),
        "minimum": round(minimum, 1),
        "maximum": round(maximum, 1),
        "trend_label": trend_label,
    }


def build_metric_summary(metrics: dict[str, Any], metric_definitions: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for metric in metric_definitions:
        value = metrics.get(metric["metric_id"])
        if value is None:
            continue
        parts.append(f"{metric['label']} {value}{metric.get('unit', '')}")
    return "，".join(parts)


def list_available_devices(context: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    rows = context.get("overview_rows", [])
    return [
        {
            "instance_id": row["instance_id"],
            "device_name": row["device_name"],
            "status": STATUS_LABELS.get(row.get("status", "unknown"), row.get("status", "unknown")),
            "risk_level": RISK_LABELS.get(row.get("risk_level", "-"), row.get("risk_level", "-")),
            "device_status": DEVICE_STATUS_LABELS.get(row.get("device_status", "unknown"), row.get("device_status", "unknown")),
        }
        for row in rows[:limit]
    ]


def _fallback_device_id(context: dict[str, Any]) -> str | None:
    devices = context.get("devices", {})
    selected_device_id = context.get("selected_device_id")
    if selected_device_id in devices:
        return selected_device_id
    if devices:
        return next(iter(devices.keys()))
    return None


def _build_device_error(context: dict[str, Any], device_query: str | None) -> dict[str, Any]:
    query = (device_query or "").strip() or "当前设备"
    return {
        "ok": False,
        "error": f"未找到与“{query}”匹配的设备。",
        "available_devices": list_available_devices(context),
    }


def _tool_get_dashboard_overview(arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    focus = arguments.get("focus", "all")
    rows = context.get("overview_rows", [])
    counts = context.get("counts", {})

    if focus == "abnormal":
        filtered_rows = [row for row in rows if row.get("status") in ("warning", "critical", "offline")]
    elif focus == "offline":
        filtered_rows = [row for row in rows if row.get("device_status") == "offline"]
    elif focus == "high_risk":
        filtered_rows = [row for row in rows if row.get("risk_level") == "high"]
    else:
        filtered_rows = rows

    return {
        "ok": True,
        "focus": focus,
        "counts": counts,
        "selected_device_id": context.get("selected_device_id"),
        "devices": [
            {
                "instance_id": row["instance_id"],
                "device_name": row["device_name"],
                "category_name": row["category_name"],
                "device_status": DEVICE_STATUS_LABELS.get(row["device_status"], row["device_status"]),
                "status": STATUS_LABELS.get(row["status"], row["status"]),
                "risk_level": RISK_LABELS.get(row["risk_level"], row["risk_level"]),
                "metric_summary": row["metric_summary"],
            }
            for row in filtered_rows[:10]
        ],
    }


def _tool_get_device_detail(arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    device_id, explicit_query = resolve_device_query(arguments.get("device_query"), context)
    if device_id is None:
        return _build_device_error(context, arguments.get("device_query") if explicit_query else None)

    device = context["devices"][device_id]
    analysis = device.get("latest_analysis") or {}
    point = device.get("latest_point") or {}
    metric_definitions = device.get("metrics", [])

    return {
        "ok": True,
        "resolved_by_default": not explicit_query,
        "device": {
            "instance_id": device["instance_id"],
            "device_name": device["device_name"],
            "category_name": device["category_name"],
            "template_id": device["template_id"],
            "template_display_name": device["template_display_name"],
            "source_type": device["source_type"],
            "device_status": DEVICE_STATUS_LABELS.get(
                analysis.get("device_status", point.get("device_status", "unknown")),
                "未知",
            ),
            "status": STATUS_LABELS.get(analysis.get("status", "unknown"), "未知"),
            "risk_level": RISK_LABELS.get(analysis.get("risk_level", "unknown"), "未知"),
            "last_heartbeat": device.get("last_heartbeat"),
            "latest_metrics": point.get("metrics", {}),
            "metric_summary": build_metric_summary(point.get("metrics", {}), metric_definitions),
            "supported_metrics": metric_definitions,
            "summary": analysis.get("summary") or "当前暂无可展示的分析结果。",
            "report": device.get("report") or "当前暂无可展示的分析结果。",
        },
    }


def _tool_get_device_metric_trend(arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    device_id, explicit_query = resolve_device_query(arguments.get("device_query"), context)
    if device_id is None:
        return _build_device_error(context, arguments.get("device_query") if explicit_query else None)

    device = context["devices"][device_id]
    metric = resolve_metric_query(arguments.get("metric_query"), device.get("metrics", []))
    if metric is None:
        return {
            "ok": False,
            "error": f"未识别指标“{(arguments.get('metric_query') or '').strip()}”。",
            "supported_metrics": [
                {"metric_id": item["metric_id"], "label": item.get("label", item["metric_id"])}
                for item in device.get("metrics", [])
            ],
            "device": {
                "instance_id": device["instance_id"],
                "device_name": device["device_name"],
            },
        }

    trend = compute_metric_trend(device=device, metric=metric)
    return {
        **trend,
        "device": {
            "instance_id": device["instance_id"],
            "device_name": device["device_name"],
        },
    }


def _tool_get_device_issue_analysis(arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    device_id, explicit_query = resolve_device_query(arguments.get("device_query"), context)
    if device_id is None:
        return _build_device_error(context, arguments.get("device_query") if explicit_query else None)

    device = context["devices"][device_id]
    analysis = device.get("latest_analysis") or {}
    issues = analysis.get("issues", [])

    return {
        "ok": True,
        "device": {
            "instance_id": device["instance_id"],
            "device_name": device["device_name"],
            "device_status": DEVICE_STATUS_LABELS.get(analysis.get("device_status", "unknown"), "未知"),
            "status": STATUS_LABELS.get(analysis.get("status", "unknown"), "未知"),
            "risk_level": RISK_LABELS.get(analysis.get("risk_level", "unknown"), "未知"),
        },
        "summary": analysis.get("summary") or "当前没有识别到明显异常。",
        "issues": [
            {
                "message": issue["message"],
                "suggestion": issue["suggestion"],
            }
            for issue in issues[:5]
        ],
    }

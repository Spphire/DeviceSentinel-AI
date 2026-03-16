"""Dashboard agent utilities for local rules and real LLM backends."""

from __future__ import annotations

import json
import os
from statistics import mean
from dataclasses import dataclass

import requests

from app.agent.report_generator import generate_report
from app.agent.dashboard_tools import (
    DEVICE_STATUS_LABELS,
    RISK_LABELS,
    STATUS_LABELS,
    build_metric_summary,
    get_dashboard_tool_definitions,
    invoke_dashboard_tool,
)


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

FLEET_KEYWORDS = ["总览", "总体", "整体", "全部", "所有设备", "设备总数", "在线设备", "异常设备", "高风险", "离线设备"]
ALERT_KEYWORDS = ["异常", "告警", "高风险", "离线"]
CAUSE_KEYWORDS = ["原因", "为什么", "建议", "怎么处理", "处置", "怎么办", "风险"]
TREND_KEYWORDS = ["趋势", "曲线", "变化", "波动", "最近", "过去", "历史"]
CURRENT_DEVICE_KEYWORDS = ["这台", "这个设备", "默认设备", "当前设备"]
DEFAULT_REAL_LLM_MODEL = "gpt-5.4"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"


@dataclass(frozen=True)
class AgentBackendConfig:
    mode: str = "local_rule"
    model: str = DEFAULT_REAL_LLM_MODEL
    use_local_fallback: bool = True
    api_key_override: str | None = None
    base_url_override: str | None = None


class AgentBackendError(RuntimeError):
    """Raised when the configured agent backend cannot serve the request."""


def build_agent_backend_config(settings: dict | None) -> AgentBackendConfig:
    system = (settings or {}).get("system", {})
    mode = str(system.get("agent_mode", "local_rule")).strip() or "local_rule"
    default_model = DEFAULT_OLLAMA_MODEL if mode == "local_ollama" else DEFAULT_REAL_LLM_MODEL
    model_name = str(system.get("agent_model", default_model)).strip() or default_model
    if mode == "local_ollama" and model_name == DEFAULT_REAL_LLM_MODEL:
        model_name = DEFAULT_OLLAMA_MODEL
    return AgentBackendConfig(
        mode=mode,
        model=model_name,
        use_local_fallback=bool(system.get("agent_use_local_fallback", True)),
    )


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


def generate_agent_reply(
    user_message: str,
    context: dict,
    backend_config: AgentBackendConfig | None = None,
    conversation_history: list[dict] | None = None,
) -> str:
    config = backend_config or AgentBackendConfig()
    if config.mode == "local_rule":
        return generate_local_rule_reply(user_message, context)

    if config.mode == "real_llm":
        try:
            return _generate_real_llm_reply(
                user_message=user_message,
                context=context,
                backend_config=config,
                conversation_history=conversation_history,
            )
        except AgentBackendError as exc:
            if config.use_local_fallback:
                fallback = generate_local_rule_reply(user_message, context)
                return f"真实模型当前不可用（{exc}），已切换到本地规则回答。\n\n{fallback}"
            return f"真实模型当前不可用：{exc}"

    if config.mode == "local_ollama":
        try:
            return _generate_local_ollama_reply(
                user_message=user_message,
                context=context,
                backend_config=config,
                conversation_history=conversation_history,
            )
        except AgentBackendError as exc:
            if config.use_local_fallback:
                fallback = generate_local_rule_reply(user_message, context)
                return f"本地 Ollama 模型当前不可用（{exc}），已切换到本地规则回答。\n\n{fallback}"
            return f"本地 Ollama 模型当前不可用：{exc}"

    fallback = generate_local_rule_reply(user_message, context)
    return f"未识别对话后端模式 {config.mode}，已改用本地规则。\n\n{fallback}"


def generate_local_rule_reply(user_message: str, context: dict) -> str:
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
    return build_metric_summary(metrics, metric_definitions)


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


def _generate_real_llm_reply(
    user_message: str,
    context: dict,
    backend_config: AgentBackendConfig,
    conversation_history: list[dict] | None = None,
) -> str:
    client = _create_openai_client(
        api_key_override=backend_config.api_key_override,
        base_url_override=backend_config.base_url_override,
    )
    input_messages = _build_llm_input_messages(
        user_message=user_message,
        context=context,
        conversation_history=conversation_history,
    )
    tool_definitions = get_dashboard_tool_definitions()

    try:
        response = client.responses.create(
            model=backend_config.model,
            input=input_messages,
            tools=tool_definitions,
        )
    except Exception as exc:  # pragma: no cover - exercised through fallback path
        raise AgentBackendError(str(exc)) from exc

    while True:
        tool_calls = [item for item in getattr(response, "output", []) if getattr(item, "type", "") == "function_call"]
        if not tool_calls:
            return _extract_response_text(response)

        for tool_call in tool_calls:
            try:
                arguments = json.loads(getattr(tool_call, "arguments", "{}") or "{}")
            except json.JSONDecodeError as exc:
                raise AgentBackendError(f"模型返回了无法解析的工具参数：{exc}") from exc

            result = invoke_dashboard_tool(
                name=getattr(tool_call, "name", ""),
                arguments=arguments,
                context=context,
            )
            input_messages.append(
                {
                    "type": "function_call_output",
                    "call_id": getattr(tool_call, "call_id", ""),
                    "output": json.dumps(result, ensure_ascii=False),
                }
            )

        try:
            response = client.responses.create(
                model=backend_config.model,
                input=input_messages,
                tools=tool_definitions,
            )
        except Exception as exc:  # pragma: no cover - exercised through fallback path
            raise AgentBackendError(str(exc)) from exc


def _create_openai_client(
    api_key_override: str | None = None,
    base_url_override: str | None = None,
):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AgentBackendError("未安装 openai 依赖，请先执行 `pip install -r requirements.txt`。") from exc

    api_key = (api_key_override or os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise AgentBackendError("未检测到 OpenAI API Key，请在页面设置中临时输入，或设置 OPENAI_API_KEY 环境变量。")

    client_kwargs = {"api_key": api_key}
    base_url = (base_url_override or os.getenv("OPENAI_BASE_URL") or "").strip()
    if base_url:
        client_kwargs["base_url"] = base_url

    return OpenAI(**client_kwargs)


def _build_llm_input_messages(
    user_message: str,
    context: dict,
    conversation_history: list[dict] | None = None,
) -> list[dict]:
    selected_device_id = context.get("selected_device_id")
    selected_device = context.get("devices", {}).get(selected_device_id, {})
    counts = context.get("counts", {})

    system_message = (
        "你是电气设备状态监测 AI Agent，需要使用工具获取当前面板里的实时设备信息。"
        "禁止编造设备状态、异常原因或指标值。"
        "回答使用中文，先给结论，再给依据和建议。"
        "如果工具返回未匹配设备、数据不足或无异常，就如实说明。"
    )
    context_message = (
        "当前面板上下文："
        f"默认设备为 {selected_device.get('device_name', '未知设备')}（{selected_device_id or 'unknown'}）；"
        f"总设备 {counts.get('total_devices', 0)} 台，在线 {counts.get('online_devices', 0)} 台，"
        f"异常 {counts.get('abnormal_devices', 0)} 台，高风险 {counts.get('high_risk_devices', 0)} 台，"
        f"离线 {counts.get('offline_devices', 0)} 台。"
        "如果用户问“这台设备”，默认指当前面板选中的设备。"
    )

    messages = [
        {"role": "system", "content": system_message},
        {"role": "system", "content": context_message},
    ]

    if conversation_history:
        for item in conversation_history:
            role = item.get("role")
            content = (item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            messages.append({"role": role, "content": content})

    if not conversation_history:
        messages.append({"role": "user", "content": user_message})

    return messages


def _extract_response_text(response) -> str:
    output_text = (getattr(response, "output_text", "") or "").strip()
    if output_text:
        return output_text

    parts: list[str] = []
    for item in getattr(response, "output", []):
        if getattr(item, "type", "") != "message":
            continue
        for content in getattr(item, "content", []):
            if getattr(content, "type", "") in {"output_text", "text"}:
                text_value = getattr(content, "text", "")
                if text_value:
                    parts.append(text_value)

    merged = "\n".join(part.strip() for part in parts if part and part.strip()).strip()
    if merged:
        return merged
    raise AgentBackendError("真实模型返回为空。")


def _generate_local_ollama_reply(
    user_message: str,
    context: dict,
    backend_config: AgentBackendConfig,
    conversation_history: list[dict] | None = None,
) -> str:
    base_url = (backend_config.base_url_override or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    payload = {
        "model": backend_config.model or DEFAULT_OLLAMA_MODEL,
        "stream": False,
        "messages": _build_ollama_messages(
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
        ),
        "options": {
            "temperature": 0.2,
        },
    }

    try:
        response = requests.post(
            f"{base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AgentBackendError(str(exc)) from exc

    data = response.json()
    content = (data.get("message", {}) or {}).get("content", "").strip()
    if content:
        return content
    raise AgentBackendError("本地 Ollama 返回为空。")


def _build_ollama_messages(
    user_message: str,
    context: dict,
    conversation_history: list[dict] | None = None,
) -> list[dict]:
    messages = [
        {
            "role": "system",
            "content": (
                "你是电气设备状态监测 AI Agent。"
                "必须严格根据我提供的面板上下文回答，不要编造设备、指标、异常或趋势。"
                "回答使用中文，优先给结论，再给依据和建议。"
                "如果用户问“这台设备”，默认指当前选中的设备。"
            ),
        },
        {
            "role": "system",
            "content": _build_ollama_context_snapshot(context),
        },
    ]

    if conversation_history:
        for item in conversation_history:
            role = item.get("role")
            content = (item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            messages.append({"role": role, "content": content})

    if not conversation_history:
        messages.append({"role": "user", "content": user_message})

    return messages


def _build_ollama_context_snapshot(context: dict) -> str:
    selected_device_id = context.get("selected_device_id")
    counts = context.get("counts", {})
    devices = context.get("devices", {})
    lines = [
        "当前监测面板结构化上下文如下。",
        (
            f"设备总数 {counts.get('total_devices', 0)}，在线 {counts.get('online_devices', 0)}，"
            f"异常 {counts.get('abnormal_devices', 0)}，高风险 {counts.get('high_risk_devices', 0)}，"
            f"离线 {counts.get('offline_devices', 0)}。"
        ),
        f"当前选中设备: {selected_device_id or 'unknown'}。",
        "设备详情：",
    ]

    for device_id, device in devices.items():
        analysis = device.get("latest_analysis") or {}
        point = device.get("latest_point") or {}
        metric_definitions = device.get("metrics", [])
        metrics_text = build_metric_summary(point.get("metrics", {}), metric_definitions) or "-"
        issue_text = "；".join(issue.get("message", "") for issue in analysis.get("issues", [])[:3]) or "无明显异常"

        lines.append(
            (
                f"- {device['device_name']}（{device_id}），类别 {device['category_name']}，"
                f"在线状态 {DEVICE_STATUS_LABELS.get(analysis.get('device_status', point.get('device_status', 'unknown')), '未知')}，"
                f"诊断状态 {STATUS_LABELS.get(analysis.get('status', 'unknown'), '未知')}，"
                f"风险等级 {RISK_LABELS.get(analysis.get('risk_level', 'unknown'), '未知')}，"
                f"最新指标 {metrics_text}，摘要 {analysis.get('summary') or '暂无摘要'}，"
                f"问题 {issue_text}。"
            )
        )

        history_rows = []
        for history_point in device.get("history", [])[-6:]:
            metric_parts = []
            for metric in metric_definitions:
                metric_id = metric["metric_id"]
                value = history_point.get("metrics", {}).get(metric_id)
                metric_parts.append(f"{metric['label']}={value}")
            history_rows.append("{" + ", ".join(metric_parts) + "}")

        if history_rows:
            lines.append(f"  最近历史: {' | '.join(history_rows)}")

    return "\n".join(lines)

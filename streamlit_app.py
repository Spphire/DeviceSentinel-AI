"""Streamlit dashboard for the template-driven mixed device monitoring demo."""

from __future__ import annotations

import copy
import html
import json
from datetime import datetime

import pandas as pd
import streamlit as st

from app.agent.chat_agent import (
    AgentBackendConfig,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_REAL_LLM_MODEL,
    build_agent_backend_config,
    build_agent_context,
    build_agent_hint,
    generate_agent_reply,
)
from app.agent.report_generator import generate_report
from app.services.demo_service import (
    MAX_HISTORY_POINTS,
    SIMULATION_STEP_MINUTES,
    create_dashboard_runtime,
    create_empty_device_payload,
    load_persisted_dashboard_settings,
    load_runtime_templates,
    save_persisted_dashboard_settings,
)
from app.services.gateway_service import (
    DEFAULT_GATEWAY_PATH,
    build_gateway_client_target,
    load_gateway_manager_status,
    normalize_gateway_config,
)


STATUS_LABELS = {
    "normal": "正常",
    "warning": "预警",
    "critical": "严重异常",
    "offline": "离线",
    "unknown": "未知",
}
RISK_LABELS = {"low": "低", "medium": "中", "high": "高", "unknown": "未知", "-": "-"}
DEVICE_STATUS_LABELS = {"online": "在线", "offline": "离线"}
SOURCE_TYPE_LABELS = {"simulated": "模拟设备", "real": "真实设备"}
DEVICE_EDITOR_WIDGET_PREFIXES = (
    "editor_name_",
    "editor_id_",
    "editor_template_",
    "editor_profile_",
)


def _initialize_state() -> None:
    if "templates" not in st.session_state:
        st.session_state.templates = load_runtime_templates()

    if "applied_settings" not in st.session_state:
        settings = load_persisted_dashboard_settings()
        st.session_state.applied_settings = settings

    if "runtime_signature" not in st.session_state:
        st.session_state.runtime_signature = None
    if "report_cache" not in st.session_state:
        st.session_state.report_cache = {}
    if "request_runtime_reload" not in st.session_state:
        st.session_state.request_runtime_reload = False
    if "running" not in st.session_state:
        st.session_state.running = True
    if "selected_device_id" not in st.session_state:
        first_device = st.session_state.applied_settings["devices"][0]["instance_id"]
        st.session_state.selected_device_id = first_device
    if "settings_dialog_open" not in st.session_state:
        st.session_state.settings_dialog_open = False
    if "settings_feedback" not in st.session_state:
        st.session_state.settings_feedback = None
    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = []
    if "agent_context" not in st.session_state:
        st.session_state.agent_context = {}
    if "session_openai_api_key" not in st.session_state:
        st.session_state.session_openai_api_key = ""
    if "session_openai_base_url" not in st.session_state:
        st.session_state.session_openai_base_url = ""

    if "device_editor_items" not in st.session_state:
        _sync_editor_state_from_settings(st.session_state.applied_settings, reset_device_widgets=True)


def _settings_signature(settings: dict) -> str:
    runtime_relevant_settings = {
        "devices": settings.get("devices", []),
    }
    return json.dumps(runtime_relevant_settings, ensure_ascii=False, sort_keys=True)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_relative_time(last_heartbeat: str | None, current_time: datetime | None) -> str:
    heartbeat_time = _parse_timestamp(last_heartbeat)
    if heartbeat_time is None:
        return "从未上报"
    if current_time is None:
        return heartbeat_time.strftime("%Y-%m-%d %H:%M")

    seconds = max(0, int((current_time - heartbeat_time).total_seconds()))
    if seconds < 60:
        return f"{seconds} 秒前"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86400:
        return f"{seconds // 3600} 小时前"
    return f"{seconds // 86400} 天前"


def _chunked(items: list, size: int) -> list[list]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _clear_device_editor_widget_state() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(DEVICE_EDITOR_WIDGET_PREFIXES):
            del st.session_state[key]


def _sync_editor_state_from_settings(settings: dict, reset_device_widgets: bool = False) -> None:
    st.session_state.device_editor_items = copy.deepcopy(settings["devices"])
    st.session_state.editor_history_window = int(settings["system"]["history_window"])
    st.session_state.editor_refresh_interval = int(settings["system"]["refresh_interval_seconds"])
    st.session_state.editor_developer_mode = bool(settings["system"].get("developer_mode", False))
    st.session_state.editor_show_structured_analysis = bool(settings["system"].get("show_structured_analysis", False))
    st.session_state.editor_agent_mode = settings["system"].get("agent_mode", "local_rule")
    st.session_state.editor_agent_model = settings["system"].get("agent_model", DEFAULT_REAL_LLM_MODEL)
    st.session_state.editor_agent_use_local_fallback = bool(settings["system"].get("agent_use_local_fallback", True))
    gateway = normalize_gateway_config(settings.get("gateway"))
    st.session_state.editor_gateway_listen_host = gateway.listen_host
    st.session_state.editor_gateway_port = gateway.port

    if reset_device_widgets:
        _clear_device_editor_widget_state()

    for device in st.session_state.device_editor_items:
        _prime_device_editor_widget_state(device)


def _prime_device_editor_widget_state(device: dict) -> None:
    instance_id = device["instance_id"]
    template = st.session_state.templates[device["template_id"]]

    defaults = {
        f"editor_name_{instance_id}": device["name"],
        f"editor_id_{instance_id}": device["instance_id"],
        f"editor_template_{instance_id}": device["template_id"],
        f"editor_profile_{instance_id}": device.get("simulation_profile") or _get_default_profile(template),
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _get_default_profile(template) -> str | None:
    profile_options = template.simulation.get("profile_options", [])
    if not profile_options:
        return None
    return profile_options[0]["id"]


def _get_profile_options(template) -> list[dict]:
    return template.simulation.get("profile_options", [])


def _build_device_payload_from_widgets(device: dict) -> dict:
    instance_id = device["instance_id"]
    template_id = st.session_state[f"editor_template_{instance_id}"]
    template = st.session_state.templates[template_id]

    payload = {
        "instance_id": st.session_state[f"editor_id_{instance_id}"].strip(),
        "name": st.session_state[f"editor_name_{instance_id}"].strip(),
        "template_id": template_id,
        "simulation_profile": None,
    }

    if template.source_type == "simulated":
        payload["simulation_profile"] = st.session_state.get(f"editor_profile_{instance_id}") or _get_default_profile(template)

    return payload


def _save_settings_from_editor() -> None:
    previous_settings = st.session_state.applied_settings
    settings = {
        "system": {
            "history_window": int(st.session_state.editor_history_window),
            "refresh_interval_seconds": int(st.session_state.editor_refresh_interval),
            "developer_mode": bool(st.session_state.editor_developer_mode),
            "show_structured_analysis": bool(st.session_state.editor_show_structured_analysis),
            "agent_mode": st.session_state.editor_agent_mode,
            "agent_model": (st.session_state.editor_agent_model or DEFAULT_REAL_LLM_MODEL).strip() or DEFAULT_REAL_LLM_MODEL,
            "agent_use_local_fallback": bool(st.session_state.editor_agent_use_local_fallback),
        },
        "gateway": normalize_gateway_config(
            {
                "listen_host": (st.session_state.editor_gateway_listen_host or "127.0.0.1").strip(),
                "port": int(st.session_state.editor_gateway_port),
                "path": DEFAULT_GATEWAY_PATH,
            }
        ).to_dict(),
        "devices": [_build_device_payload_from_widgets(item) for item in st.session_state.device_editor_items],
    }
    devices = settings["devices"]
    instance_ids = [device["instance_id"] for device in devices]

    if not all(instance_ids):
        st.session_state.settings_feedback = ("error", "设备实例 ID 不能为空。")
        return
    if len(instance_ids) != len(set(instance_ids)):
        st.session_state.settings_feedback = ("error", "设备实例 ID 必须唯一，请修改重复项。")
        return
    if not all(device["name"] for device in devices):
        st.session_state.settings_feedback = ("error", "设备名称不能为空。")
        return

    save_persisted_dashboard_settings(settings)
    st.session_state.applied_settings = settings
    _sync_editor_state_from_settings(settings, reset_device_widgets=True)
    st.session_state.report_cache = {}
    st.session_state.request_runtime_reload = previous_settings.get("devices") != settings["devices"]
    if st.session_state.selected_device_id not in {device["instance_id"] for device in devices}:
        st.session_state.selected_device_id = devices[0]["instance_id"]
    st.session_state.settings_feedback = ("success", "设置已自动保存并应用。")


def _add_device_row() -> None:
    template_ids = list(st.session_state.templates.keys())
    new_device = create_empty_device_payload(template_ids[0])
    st.session_state.device_editor_items.append(new_device)
    _prime_device_editor_widget_state(new_device)
    st.session_state.settings_dialog_open = True
    st.rerun()


def _remove_device_row(instance_id: str) -> None:
    if len(st.session_state.device_editor_items) == 1:
        st.warning("至少保留一台设备。")
        return

    st.session_state.device_editor_items = [
        item for item in st.session_state.device_editor_items if item["instance_id"] != instance_id
    ]
    st.session_state.settings_dialog_open = True
    st.rerun()


def _handle_settings_dialog_dismiss() -> None:
    _save_settings_from_editor()
    st.session_state.settings_dialog_open = False


def _resolve_gateway_runtime_summary(settings: dict) -> dict:
    desired_config = normalize_gateway_config(settings.get("gateway"))
    status = load_gateway_manager_status()

    if status and status.get("gateway"):
        active_config = normalize_gateway_config(status.get("gateway"))
        client_target = status.get("client_target") or build_gateway_client_target(active_config)
        return {
            "running": bool(status.get("running")),
            "manager_pid": status.get("manager_pid"),
            "active_config": active_config,
            "desired_config": desired_config,
            "client_target": client_target,
            "last_error": status.get("last_error"),
            "updated_at": status.get("updated_at"),
            "health": status.get("health"),
            "manager_pid_alive": bool(status.get("manager_pid_alive")),
            "stale_status": bool(status.get("stale_status")),
        }

    return {
        "running": False,
        "manager_pid": None,
        "active_config": desired_config,
        "desired_config": desired_config,
        "client_target": build_gateway_client_target(desired_config),
        "last_error": None,
        "updated_at": None,
        "health": None,
        "manager_pid_alive": False,
        "stale_status": False,
    }


def _build_client_command(device_payload: dict, template, gateway_summary: dict) -> str:
    client_target = gateway_summary["client_target"]
    if template.template_id == "personal_pc_real":
        return (
            "python scripts/personal_pc_client_app.py "
            f"--instance-id {device_payload['instance_id']} "
            f"--gateway-host {client_target['host']} "
            f"--gateway-port {client_target['port']} "
            f"--gateway-path {client_target['path']}"
        )
    if template.template_id == "mobile_device_real":
        return (
            "python scripts/mobile_device_client.py "
            f"--instance-id {device_payload['instance_id']} "
            f"--gateway-host {client_target['host']} "
            f"--gateway-port {client_target['port']} "
            f"--gateway-path {client_target['path']}"
        )
    if template.template_id == "temp_humidity_real":
        return (
            "python scripts/temp_humidity_client.py "
            f"--instance-id {device_payload['instance_id']} "
            f"--gateway-host {client_target['host']} "
            f"--gateway-port {client_target['port']} "
            f"--gateway-path {client_target['path']}"
        )
    return ""


def _open_settings_dialog() -> None:
    _sync_editor_state_from_settings(st.session_state.applied_settings, reset_device_widgets=True)
    st.session_state.settings_dialog_open = True


def _render_header() -> None:
    title_col, action_col = st.columns([12, 1], vertical_alignment="top")
    with title_col:
        st.title("基于 MPC Skill 的电气设备状态监测 AI Agent 系统")
        st.caption("模板驱动版本：支持模拟设备、真实设备和可扩展配置文件自动加载")
    with action_col:
        st.markdown("<div style='height: 0.35rem;'></div>", unsafe_allow_html=True)
        if st.button("⚙", key="open_settings_dialog", help="打开设置", type="tertiary", use_container_width=True):
            _open_settings_dialog()


def _render_agent_chat_panel(agent_context: dict, backend_config) -> None:
    header_col1, header_col2 = st.columns([1, 0.18])
    with header_col1:
        st.subheader("AI Agent 对话")
    with header_col2:
        if st.button("清空对话", key="clear_agent_messages", use_container_width=True):
            st.session_state.agent_messages = []
            st.rerun()

    st.caption(build_agent_hint(agent_context))
    backend_label = {
        "local_rule": "本地规则",
        "real_llm": "真实模型",
        "local_ollama": "本地 Ollama",
    }.get(backend_config.mode, backend_config.mode)
    fallback_label = "开启" if backend_config.use_local_fallback else "关闭"
    st.caption(
        f"当前对话后端：{backend_label}"
        + (f"（模型：{backend_config.model}）" if backend_config.mode in {"real_llm", "local_ollama"} else "")
        + f"；失败回退：{fallback_label}。"
    )
    if backend_config.mode == "real_llm":
        st.caption("真实模型模式优先读取设置面板中的会话临时 Key，其次读取环境变量 `OPENAI_API_KEY`。")
    elif backend_config.mode == "local_ollama":
        st.caption("本地 Ollama 模式默认连接 `http://127.0.0.1:11434`，可在设置面板里临时改 Base URL。")

    if not st.session_state.agent_messages:
        with st.chat_message("assistant"):
            st.write(
                "我已经接入当前面板上下文，可以回答设备状态、异常设备、历史趋势和处置建议。"
            )

    for message in st.session_state.agent_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    prompt = st.chat_input("请输入你想询问的问题，例如：这台设备现在怎么样？")
    if prompt:
        st.session_state.agent_messages.append({"role": "user", "content": prompt})
        reply = generate_agent_reply(
            prompt,
            agent_context,
            backend_config=backend_config,
            conversation_history=st.session_state.agent_messages,
        )
        st.session_state.agent_messages.append({"role": "assistant", "content": reply})
        st.rerun()


@st.dialog("系统设置", width="large", dismissible=True, on_dismiss=_handle_settings_dialog_dismiss)
def _render_settings_dialog() -> None:
    st.subheader("系统设置")
    st.caption("分析时间窗口与刷新间隔属于正常系统设置，会在本地保存并在下次启动时自动恢复。")
    st.slider("分析时间窗口（Horizon）", min_value=20, max_value=180, step=10, key="editor_history_window")
    st.slider("刷新间隔（秒）", min_value=1, max_value=10, key="editor_refresh_interval")
    st.caption(f"每次自动刷新推进 {SIMULATION_STEP_MINUTES} 分钟模拟时间；真实设备按实际心跳更新。")
    st.caption("关闭设置面板后将自动保存并应用当前修改。")

    st.divider()
    st.subheader("共享网关设置")
    gateway_summary = _resolve_gateway_runtime_summary(st.session_state.applied_settings)
    st.caption("所有 HTTP 真实设备共用同一个遥测网关入口，设备卡片里不再单独维护 host / port / path。")
    gateway_col1, gateway_col2 = st.columns([1.2, 0.8])
    gateway_col1.text_input("网关监听地址", key="editor_gateway_listen_host")
    gateway_col2.number_input("网关监听端口", min_value=1, max_value=65535, step=1, key="editor_gateway_port")
    st.caption(f"固定路径：`{DEFAULT_GATEWAY_PATH}`。")
    st.caption("建议使用独立后端管理主程序托管网关：`python scripts/run_backend.py`。保存全局网关设置后，manager 会自动按新配置重载服务。")
    st.code("python scripts/run_backend.py", language="bash")

    active_gateway = gateway_summary["active_config"]
    client_target = gateway_summary["client_target"]
    health = gateway_summary.get("health") or {}
    if gateway_summary["running"]:
        st.success(
            "当前共享网关运行中："
            f" PID {gateway_summary['manager_pid']}，"
            f"监听 {active_gateway.listen_host}:{active_gateway.port}{active_gateway.path}，"
            f"客户端建议连接 {client_target['host']}:{client_target['port']}{client_target['path']}。"
        )
    else:
        st.warning("当前未检测到 backend manager 正在托管共享网关。页面仍可保存配置，但不会自动重启服务。")
    if gateway_summary["stale_status"]:
        st.warning("检测到遗留网关状态文件，但 backend manager 进程已经退出；建议重新启动 `python scripts/run_backend.py`。")
    elif gateway_summary["manager_pid"] and not gateway_summary["manager_pid_alive"]:
        st.warning("backend manager PID 已失效，当前状态可能不是最新结果。")
    if health:
        checked_at = health.get("checked_at") or "-"
        health_url = health.get("url") or "-"
        if health.get("ok"):
            st.caption(f"健康检查：正常，最近探测 {checked_at}，探针地址 `{health_url}`。")
        else:
            st.error(
                "健康检查失败："
                f"{health.get('error') or '未返回正常响应。'}"
                f"（最近探测 {checked_at}，地址 `{health_url}`）"
            )
    if gateway_summary["last_error"]:
        st.error(gateway_summary["last_error"])

    st.divider()
    st.subheader("Agent 设置")
    st.selectbox(
        "对话后端",
        options=["local_rule", "real_llm", "local_ollama"],
        key="editor_agent_mode",
        format_func=lambda mode: {
            "local_rule": "本地规则",
            "real_llm": "真实模型",
            "local_ollama": "本地 Ollama",
        }.get(mode, mode),
    )
    st.text_input("模型名称", key="editor_agent_model")
    st.toggle("真实模型失败时自动回退到本地规则", key="editor_agent_use_local_fallback")
    current_agent_mode = st.session_state.editor_agent_mode
    if current_agent_mode == "real_llm":
        st.text_input("OpenAI API Key（仅当前会话）", key="session_openai_api_key", type="password")
        st.text_input("OpenAI Base URL（可选，仅当前会话）", key="session_openai_base_url")
        st.caption("上面两个输入框仅保存在当前页面会话中，不会写入本地设置文件。")
        st.caption("如果留空，系统会继续读取环境变量 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。")
    elif current_agent_mode == "local_ollama":
        st.text_input("Ollama Base URL（可选，仅当前会话）", key="session_openai_base_url")
        st.caption(f"模型名称建议填写 `{DEFAULT_OLLAMA_MODEL}`；Base URL 留空时默认 `http://127.0.0.1:11434`。")
        st.caption("Base URL 仅保存在当前页面会话中，不会写入本地设置文件。")
    else:
        st.caption("本地规则模式不需要额外模型服务配置。")

    st.divider()
    developer_mode_enabled = st.toggle("开发者模式", key="editor_developer_mode")

    if developer_mode_enabled:
        st.caption("设备清单、模拟细分类型和结构化分析展示在开发者模式中维护。")
        st.toggle("显示结构化分析结果", key="editor_show_structured_analysis")

        if st.button("+ 添加设备", use_container_width=True):
            _add_device_row()

        st.caption("设备模板来自项目根目录 `device_templates/` 中的 JSON 文件。")

        for item in st.session_state.device_editor_items:
            _prime_device_editor_widget_state(item)
            container = st.container(border=True)
            instance_id = item["instance_id"]

            with container:
                row_col1, row_col2, row_col3, row_col4 = st.columns([1.4, 1.2, 1.2, 0.4])
                row_col1.text_input("设备名称", key=f"editor_name_{instance_id}")
                row_col2.text_input("设备实例 ID", key=f"editor_id_{instance_id}")
                row_col3.selectbox(
                    "设备模板",
                    options=list(st.session_state.templates.keys()),
                    key=f"editor_template_{instance_id}",
                    format_func=lambda template_id: st.session_state.templates[template_id].display_name,
                )
                with row_col4:
                    st.markdown("<div style='height: 1.8rem;'></div>", unsafe_allow_html=True)
                    if st.button("删除", key=f"remove_{instance_id}", use_container_width=True, type="primary"):
                        _remove_device_row(instance_id)

                selected_template = st.session_state.templates[st.session_state[f"editor_template_{instance_id}"]]
                meta_col1, meta_col2 = st.columns([1, 1])
                meta_col1.caption(f"设备类别：{selected_template.category_name}")
                meta_col2.caption(f"数据来源：{SOURCE_TYPE_LABELS.get(selected_template.source_type, selected_template.source_type)}")

                if selected_template.source_type == "simulated":
                    profile_options = _get_profile_options(selected_template)
                    if profile_options:
                        st.selectbox(
                            "模拟细分类型",
                            options=[item["id"] for item in profile_options],
                            key=f"editor_profile_{instance_id}",
                            format_func=lambda profile_id: next(
                                option["label"] for option in profile_options if option["id"] == profile_id
                            ),
                        )
                else:
                    st.caption("这类真实设备共用上方“共享网关设置”里的同一个 HTTP 入口，只通过 `instance_id` 区分设备。")
                    client_preview = _build_client_command(
                        _build_device_payload_from_widgets(item),
                        selected_template,
                        gateway_summary,
                    )
                    if client_preview:
                        st.caption("客户端示例命令")
                        st.code(client_preview, language="bash")
                        if selected_template.template_id == "personal_pc_real":
                            st.caption("个人 PC 客户端默认会打开图形界面；如果需要后台无人值守运行，可在命令末尾追加 `--headless`。")
                        if selected_template.template_id == "mobile_device_real":
                            st.caption("安卓 / Termux 实机上报可直接运行；如果先在桌面演示手机设备，可在命令末尾追加 `--simulate`。")
    else:
        st.info("当前为正式展示模式。设备清单和开发者级网关配置已隐藏，保留基础系统设置。")


def _ensure_runtime() -> None:
    settings = st.session_state.applied_settings
    signature = _settings_signature(settings)
    if (
        "runtime" not in st.session_state
        or st.session_state.runtime_signature != signature
        or st.session_state.request_runtime_reload
    ):
        st.session_state.runtime = create_dashboard_runtime(
            templates=st.session_state.templates,
            device_payloads=settings["devices"],
            history_limit=MAX_HISTORY_POINTS,
        )
        st.session_state.runtime_signature = signature
        st.session_state.request_runtime_reload = False


def _build_overview_dataframe(rows: list[dict], runtime) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame

    frame["source_type"] = frame["source_type"].map(lambda value: SOURCE_TYPE_LABELS.get(value, value))
    frame["device_status"] = frame["device_status"].map(lambda value: DEVICE_STATUS_LABELS.get(value, value))
    frame["status"] = frame["status"].map(lambda value: STATUS_LABELS.get(value, value))
    frame["risk_level"] = frame["risk_level"].map(lambda value: RISK_LABELS.get(value, value))
    frame["last_heartbeat"] = frame.apply(
        lambda row: _format_relative_time(row["last_heartbeat"], runtime.get_reference_time(row["instance_id"])),
        axis=1,
    )

    frame = frame.rename(
        columns={
            "device_name": "设备名称",
            "instance_id": "设备编号",
            "category_name": "设备类别",
            "source_type": "数据来源",
            "device_status": "在线状态",
            "last_heartbeat": "最后心跳",
            "metric_summary": "最新指标",
            "status": "诊断状态",
            "risk_level": "风险等级",
            "issue_count": "告警数",
        }
    )
    return frame[
        [
            "设备名称",
            "设备编号",
            "设备类别",
            "数据来源",
            "在线状态",
            "最后心跳",
            "最新指标",
            "诊断状态",
            "风险等级",
            "告警数",
        ]
    ]


def _build_history_dataframe(points: list, template) -> pd.DataFrame:
    rows = []
    for point in points:
        row = {"timestamp": point.timestamp}
        for metric in template.metrics:
            row[metric.label] = point.metrics.get(metric.metric_id)
        rows.append(row)

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return frame.set_index("timestamp")


def _series_has_data(frame: pd.DataFrame, column_name: str) -> bool:
    if frame.empty or column_name not in frame.columns:
        return False
    return not frame[column_name].dropna().empty


def _get_cached_report(device_id: str, latest_analysis: dict | None, template) -> str:
    cache = st.session_state.report_cache
    if device_id not in cache and latest_analysis is not None:
        cache[device_id] = generate_report(
            latest_analysis,
            metric_definitions=[metric.to_dict() for metric in template.metrics],
        )
    return cache.get(device_id, "当前暂无可展示的分析结果。")


def _refresh_cached_report(device_id: str, latest_analysis: dict | None, template) -> str:
    if latest_analysis is None:
        st.session_state.report_cache[device_id] = "当前暂无可展示的分析结果。"
    else:
        st.session_state.report_cache[device_id] = generate_report(
            latest_analysis,
            metric_definitions=[metric.to_dict() for metric in template.metrics],
        )
    return st.session_state.report_cache[device_id]


def _render_knowledge_panel(latest_analysis: dict | None) -> None:
    references = [] if latest_analysis is None else latest_analysis.get("knowledge_references", [])
    actions = [] if latest_analysis is None else latest_analysis.get("recommended_actions", [])

    st.subheader("知识依据与处置建议")
    if not references and not actions:
        st.info("当前没有匹配到额外的电力运维知识条目。")
        return

    if actions:
        st.caption("优先动作")
        for index, action in enumerate(actions[:4], start=1):
            st.markdown(f"{index}. {action}")

    if references:
        st.caption("知识条目")
        for reference in references[:3]:
            source_title = reference.get("source_title") or "公开资料"
            source_url = reference.get("source_url")
            title = reference.get("title") or "未命名知识"
            summary = reference.get("summary") or reference.get("scenario") or ""
            if source_url:
                st.markdown(f"**{title}**  \n{summary}  \n来源：[{source_title}]({source_url})")
            else:
                st.markdown(f"**{title}**  \n{summary}  \n来源：{source_title}")


st.set_page_config(page_title="电气设备状态监测 AI Agent", layout="wide", initial_sidebar_state="collapsed")
_initialize_state()

st.markdown(
    """
    <style>
    button[kind="primary"] {
        background: #dc2626 !important;
        border-color: #dc2626 !important;
        color: #ffffff !important;
    }
    button[kind="primary"]:hover {
        background: #b91c1c !important;
        border-color: #b91c1c !important;
    }
    .summary-card {
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        background: #ffffff;
        line-height: 1.85;
        white-space: pre-wrap;
    }
    .detail-card-label {
        color: rgba(15, 23, 42, 0.68);
        font-size: 0.95rem;
        margin-bottom: 0.35rem;
    }
    .detail-card-value {
        font-size: 1.9rem;
        font-weight: 600;
        color: rgb(30, 41, 59);
        line-height: 1.2;
    }
    .detail-card-caption {
        color: rgba(15, 23, 42, 0.56);
        font-size: 0.9rem;
        margin-top: 0.35rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

_render_header()
if st.session_state.settings_dialog_open:
    _render_settings_dialog()

if st.session_state.settings_feedback is not None:
    feedback_type, feedback_message = st.session_state.settings_feedback
    if feedback_type == "success":
        st.success(feedback_message)
    else:
        st.error(feedback_message)
    st.session_state.settings_feedback = None

_ensure_runtime()
runtime = st.session_state.runtime
settings = st.session_state.applied_settings
refresh_interval_seconds = int(settings["system"]["refresh_interval_seconds"])
history_window = int(settings["system"]["history_window"])
developer_mode = bool(settings["system"].get("developer_mode", False))
show_structured_analysis = bool(settings["system"].get("show_structured_analysis", False))
persisted_agent_backend_config = build_agent_backend_config(settings)
agent_backend_config = AgentBackendConfig(
    mode=persisted_agent_backend_config.mode,
    model=persisted_agent_backend_config.model,
    use_local_fallback=persisted_agent_backend_config.use_local_fallback,
    api_key_override=(st.session_state.get("session_openai_api_key") or "").strip() or None,
    base_url_override=(st.session_state.get("session_openai_base_url") or "").strip() or None,
)


@st.fragment(run_every=f"{refresh_interval_seconds}s" if st.session_state.running else None)
def render_dashboard() -> None:
    if st.session_state.running or not runtime.has_history():
        runtime.step()

    overview_rows = runtime.get_overview_rows()
    overview_frame = _build_overview_dataframe(overview_rows, runtime)

    total_devices = len(overview_rows)
    offline_devices = sum(1 for row in overview_rows if row["device_status"] == "offline")
    abnormal_devices = sum(1 for row in overview_rows if row["status"] in ("warning", "critical", "offline"))
    high_risk_devices = sum(1 for row in overview_rows if row["risk_level"] == "high")

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("设备总数", total_devices)
    metric_col2.metric("在线设备", total_devices - offline_devices)
    metric_col3.metric("异常设备", abnormal_devices)
    metric_col4.metric("高风险设备", high_risk_devices)

    st.subheader("设备状态总览")
    st.dataframe(overview_frame, use_container_width=True, hide_index=True)

    device_options = {
        device["instance_id"]: f"{device['name']} ({device['instance_id']})"
        for device in settings["devices"]
    }
    selected_device_id = st.selectbox(
        "查看设备详情",
        options=list(device_options.keys()),
        key="selected_device_id",
        format_func=lambda device_id: device_options[device_id],
    )

    snapshot = runtime.get_device_snapshot(selected_device_id)
    template = snapshot["template"]
    latest_point = snapshot["point"]
    latest_analysis = snapshot["analysis"]
    reference_time = runtime.get_reference_time(selected_device_id)
    relative_heartbeat = _format_relative_time(snapshot["last_heartbeat"], reference_time)
    absolute_heartbeat = "从未上报" if snapshot["last_heartbeat"] is None else snapshot["last_heartbeat"].replace("T", " ")

    st.subheader(f"{snapshot['config'].name} 单设备详情")
    detail_col1, detail_col2, detail_col3, detail_col4 = st.columns(4)
    detail_col1.metric(
        "在线状态",
        DEVICE_STATUS_LABELS.get("offline" if latest_point and latest_point.device_status == "offline" else "online", "在线"),
    )
    detail_col2.metric("设备类别", template.category_name)
    detail_col3.metric("诊断状态", STATUS_LABELS.get(latest_analysis["status"], "-") if latest_analysis else "-")
    with detail_col4:
        st.markdown("<div class='detail-card-label'>最后心跳</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='detail-card-value'>{html.escape(relative_heartbeat)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='detail-card-caption'>{html.escape(absolute_heartbeat)}</div>", unsafe_allow_html=True)

    history_points = runtime.get_device_history(selected_device_id, limit=history_window)
    history_frame = _build_history_dataframe(history_points, template)
    metric_chunks = _chunked(template.metrics, 3)

    for chunk in metric_chunks:
        chart_columns = st.columns(3)
        for column, metric in zip(chart_columns, chunk):
            with column:
                st.caption(f"{metric.label}曲线")
                if not _series_has_data(history_frame, metric.label):
                    st.info("暂无数据")
                else:
                    st.line_chart(history_frame[[metric.label]], height=220, use_container_width=True)

    report = _refresh_cached_report(selected_device_id, latest_analysis, template)
    analysis_col, knowledge_col = st.columns([1.25, 1.0])
    with analysis_col:
        st.subheader("AI 运维分析卡")
        st.markdown(f"<div class='summary-card'>{html.escape(report)}</div>", unsafe_allow_html=True)
    with knowledge_col:
        _render_knowledge_panel(latest_analysis)

    agent_context = build_agent_context(
        runtime=runtime,
        settings=settings,
        selected_device_id=selected_device_id,
        history_window=history_window,
    )
    st.session_state.agent_context = agent_context
    _render_agent_chat_panel(agent_context, agent_backend_config)

    if developer_mode and show_structured_analysis:
        with st.expander("结构化分析结果（开发者模式）", expanded=False):
            if latest_analysis is None:
                st.info("暂无分析结果")
            else:
                st.json(latest_analysis)


render_dashboard()

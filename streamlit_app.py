"""Streamlit dashboard for the template-driven mixed device monitoring demo."""

from __future__ import annotations

import copy
import html
import json
from datetime import datetime

import pandas as pd
import streamlit as st

from app.agent.chat_agent import build_agent_context, build_agent_hint, generate_agent_reply
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
    "editor_protocol_",
    "editor_host_",
    "editor_port_",
    "editor_path_",
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

    if "device_editor_items" not in st.session_state:
        _sync_editor_state_from_settings(st.session_state.applied_settings, reset_device_widgets=True)


def _settings_signature(settings: dict) -> str:
    return json.dumps(settings, ensure_ascii=False, sort_keys=True)


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

    if reset_device_widgets:
        _clear_device_editor_widget_state()

    for device in st.session_state.device_editor_items:
        _prime_device_editor_widget_state(device)


def _prime_device_editor_widget_state(device: dict) -> None:
    instance_id = device["instance_id"]
    template = st.session_state.templates[device["template_id"]]
    protocol_defaults = _get_protocol_defaults(template)

    defaults = {
        f"editor_name_{instance_id}": device["name"],
        f"editor_id_{instance_id}": device["instance_id"],
        f"editor_template_{instance_id}": device["template_id"],
        f"editor_profile_{instance_id}": device.get("simulation_profile") or _get_default_profile(template),
        f"editor_protocol_{instance_id}": device.get("communication", {}).get("protocol", protocol_defaults.get("id", "")),
        f"editor_host_{instance_id}": device.get("communication", {}).get("host", protocol_defaults.get("default_host", "127.0.0.1")),
        f"editor_port_{instance_id}": int(device.get("communication", {}).get("port", protocol_defaults.get("default_port", 10570))),
        f"editor_path_{instance_id}": device.get("communication", {}).get("path", protocol_defaults.get("default_path", "/telemetry")),
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


def _get_protocol_defaults(template) -> dict:
    protocols = template.communication.get("protocols", [])
    if not protocols:
        return {}
    return protocols[0]


def _build_device_payload_from_widgets(device: dict) -> dict:
    instance_id = device["instance_id"]
    template_id = st.session_state[f"editor_template_{instance_id}"]
    template = st.session_state.templates[template_id]

    payload = {
        "instance_id": st.session_state[f"editor_id_{instance_id}"].strip(),
        "name": st.session_state[f"editor_name_{instance_id}"].strip(),
        "template_id": template_id,
        "simulation_profile": None,
        "communication": {},
    }

    if template.source_type == "simulated":
        payload["simulation_profile"] = st.session_state.get(f"editor_profile_{instance_id}") or _get_default_profile(template)
    else:
        payload["communication"] = {
            "protocol": st.session_state.get(f"editor_protocol_{instance_id}", "http_json"),
            "host": st.session_state.get(f"editor_host_{instance_id}", "127.0.0.1").strip(),
            "port": int(st.session_state.get(f"editor_port_{instance_id}", 10570)),
            "path": st.session_state.get(f"editor_path_{instance_id}", "/telemetry").strip(),
        }

    return payload


def _save_settings_from_editor() -> None:
    settings = {
        "system": {
            "history_window": int(st.session_state.editor_history_window),
            "refresh_interval_seconds": int(st.session_state.editor_refresh_interval),
            "developer_mode": bool(st.session_state.editor_developer_mode),
            "show_structured_analysis": bool(st.session_state.editor_show_structured_analysis),
        },
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
    st.session_state.request_runtime_reload = True
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


def _build_client_command(device_payload: dict, template) -> str:
    if template.template_id == "personal_pc_real":
        return (
            "python scripts/personal_pc_client.py "
            f"--instance-id {device_payload['instance_id']} "
            f"--host {device_payload['communication'].get('host', '127.0.0.1')} "
            f"--port {device_payload['communication'].get('port', 10570)} "
            f"--path {device_payload['communication'].get('path', '/telemetry')}"
        )
    if template.template_id == "temp_humidity_real":
        return (
            "python scripts/temp_humidity_client.py "
            f"--instance-id {device_payload['instance_id']} "
            f"--host {device_payload['communication'].get('host', '127.0.0.1')} "
            f"--port {device_payload['communication'].get('port', 10570)} "
            f"--path {device_payload['communication'].get('path', '/telemetry')}"
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


def _render_agent_chat_panel(agent_context: dict) -> None:
    header_col1, header_col2 = st.columns([1, 0.18])
    with header_col1:
        st.subheader("AI Agent 对话")
    with header_col2:
        if st.button("清空对话", key="clear_agent_messages", use_container_width=True):
            st.session_state.agent_messages = []
            st.rerun()

    st.caption(build_agent_hint(agent_context))

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
        reply = generate_agent_reply(prompt, agent_context)
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
    developer_mode_enabled = st.toggle("开发者模式", key="editor_developer_mode")

    if developer_mode_enabled:
        st.caption("设备清单、模拟细分类型、结构化分析展示和真实设备通讯方式在开发者模式中维护。")
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
                    protocol_options = selected_template.communication.get("protocols", [])
                    protocol_ids = [protocol["id"] for protocol in protocol_options]
                    st.selectbox(
                        "通讯协议",
                        options=protocol_ids,
                        key=f"editor_protocol_{instance_id}",
                        format_func=lambda protocol_id: next(
                            protocol["label"] for protocol in protocol_options if protocol["id"] == protocol_id
                        ),
                    )
                    comm_col1, comm_col2, comm_col3 = st.columns([1.2, 0.8, 1.2])
                    comm_col1.text_input("主机地址", key=f"editor_host_{instance_id}")
                    comm_col2.number_input("端口", min_value=1, max_value=65535, step=1, key=f"editor_port_{instance_id}")
                    comm_col3.text_input("路径", key=f"editor_path_{instance_id}")

                    client_preview = _build_client_command(_build_device_payload_from_widgets(item), selected_template)
                    if client_preview:
                        st.caption("客户端示例命令")
                        st.code(client_preview, language="bash")
    else:
        st.info("当前为正式展示模式。设备清单与通讯配置已隐藏，保留基础系统设置。")


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

    agent_context = build_agent_context(
        runtime=runtime,
        settings=settings,
        selected_device_id=selected_device_id,
        history_window=history_window,
    )
    st.session_state.agent_context = agent_context
    _render_agent_chat_panel(agent_context)

    if developer_mode and show_structured_analysis:
        with st.expander("结构化分析结果（开发者模式）", expanded=False):
            if latest_analysis is None:
                st.info("暂无分析结果")
            else:
                st.json(latest_analysis)


render_dashboard()

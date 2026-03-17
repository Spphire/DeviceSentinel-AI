from app.agent.chat_agent import (
    AgentBackendConfig,
    DEFAULT_OLLAMA_MODEL,
    _build_llm_input_messages,
    build_agent_backend_config,
    build_agent_hint,
    generate_agent_reply,
)


def _build_context() -> dict:
    return {
        "selected_device_id": "pc-001",
        "history_window": 60,
        "counts": {
            "total_devices": 2,
            "online_devices": 1,
            "offline_devices": 1,
            "abnormal_devices": 1,
            "high_risk_devices": 1,
        },
        "overview_rows": [
            {
                "instance_id": "pc-001",
                "device_name": "办公室电脑",
                "category_name": "个人电脑",
                "source_type": "real",
                "device_status": "online",
                "last_heartbeat": "2026-03-16T22:10:00",
                "status": "warning",
                "risk_level": "high",
                "issue_count": 1,
                "metric_summary": "CPU 使用率:66.0 | GPU 使用率:32.0",
            },
            {
                "instance_id": "sgcc-001",
                "device_name": "配电箱 1",
                "category_name": "配电设备",
                "source_type": "simulated",
                "device_status": "offline",
                "last_heartbeat": "2026-03-16T21:40:00",
                "status": "offline",
                "risk_level": "high",
                "issue_count": 1,
                "metric_summary": "-",
            },
        ],
        "devices": {
            "pc-001": {
                "instance_id": "pc-001",
                "device_name": "办公室电脑",
                "category_name": "个人电脑",
                "template_id": "personal_pc_real",
                "template_display_name": "个人 PC 真实设备",
                "source_type": "real",
                "metrics": [
                    {"metric_id": "cpu_usage", "label": "CPU 使用率", "unit": "%"},
                    {"metric_id": "gpu_usage", "label": "GPU 使用率", "unit": "%"},
                    {"metric_id": "gpu_memory_usage", "label": "GPU 显存占用率", "unit": "%"},
                ],
                "latest_point": {
                    "device_status": "online",
                    "metrics": {"cpu_usage": 66.0, "gpu_usage": 32.0, "gpu_memory_usage": 58.0},
                },
                "latest_analysis": {
                    "device_status": "online",
                    "status": "warning",
                    "risk_level": "high",
                    "summary": "检测到设备负载偏高，建议继续关注资源变化。",
                    "issues": [
                        {
                            "message": "GPU 使用率达到 32.0%，超过示例阈值。",
                            "suggestion": "建议检查图形或 AI 任务负载。",
                        }
                    ],
                },
                "history": [
                    {"metrics": {"cpu_usage": 40.0, "gpu_usage": 10.0, "gpu_memory_usage": 28.0}},
                    {"metrics": {"cpu_usage": 52.0, "gpu_usage": 12.0, "gpu_memory_usage": 34.0}},
                    {"metrics": {"cpu_usage": 58.0, "gpu_usage": 18.0, "gpu_memory_usage": 41.0}},
                    {"metrics": {"cpu_usage": 66.0, "gpu_usage": 32.0, "gpu_memory_usage": 58.0}},
                ],
                "last_heartbeat": "2026-03-16T22:10:00",
                "report": "示例报告",
            },
            "sgcc-001": {
                "instance_id": "sgcc-001",
                "device_name": "配电箱 1",
                "category_name": "配电设备",
                "template_id": "sgcc_simulated",
                "template_display_name": "SGCC 模拟设备",
                "source_type": "simulated",
                "metrics": [{"metric_id": "temperature", "label": "温度", "unit": "℃"}],
                "latest_point": {"device_status": "offline", "metrics": {"temperature": None}},
                "latest_analysis": {
                    "device_status": "offline",
                    "status": "offline",
                    "risk_level": "high",
                    "summary": "设备离线。",
                    "issues": [{"message": "设备离线。", "suggestion": "检查通信链路。"}],
                },
                "history": [],
                "last_heartbeat": "2026-03-16T21:40:00",
                "report": "离线报告",
            },
        },
    }


def test_build_agent_hint_mentions_selected_device():
    hint = build_agent_hint(_build_context())

    assert "办公室电脑" in hint
    assert "默认上下文设备" in hint


def test_generate_agent_reply_for_fleet_overview_mentions_abnormal_devices():
    reply = generate_agent_reply("当前有哪些异常设备？", _build_context())

    assert "当前共监测 2 台设备" in reply
    assert "办公室电脑" in reply


def test_generate_agent_reply_for_selected_device_metric_trend_mentions_metric():
    reply = generate_agent_reply("这台设备的GPU趋势怎么样？", _build_context())

    assert "办公室电脑" in reply
    assert "GPU 使用率" in reply
    assert "趋势判断" in reply


def test_generate_agent_reply_for_vram_trend_mentions_gpu_memory_usage():
    reply = generate_agent_reply("这台设备的显存趋势怎么样？", _build_context())

    assert "办公室电脑" in reply
    assert "GPU 显存占用率" in reply
    assert "趋势判断" in reply


def test_generate_agent_reply_for_device_action_mentions_suggestions():
    reply = generate_agent_reply("办公室电脑为什么告警，建议怎么处理？", _build_context())

    assert "办公室电脑" in reply
    assert "建议" in reply


def test_generate_agent_reply_real_llm_falls_back_to_local_rule_when_unavailable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    reply = generate_agent_reply(
        "这台设备的GPU趋势怎么样？",
        _build_context(),
        backend_config=AgentBackendConfig(mode="real_llm", model="gpt-5.4", use_local_fallback=True),
        conversation_history=[{"role": "user", "content": "这台设备的GPU趋势怎么样？"}],
    )

    assert "真实模型当前不可用" in reply
    assert "GPU 使用率" in reply


def test_build_agent_backend_config_uses_ollama_default_model_when_mode_is_local_ollama():
    config = build_agent_backend_config(
        {
            "system": {
                "agent_mode": "local_ollama",
                "agent_model": "gpt-5.4",
            }
        }
    )

    assert config.mode == "local_ollama"
    assert config.model == DEFAULT_OLLAMA_MODEL


def test_build_llm_input_messages_appends_current_user_message_when_history_exists():
    messages = _build_llm_input_messages(
        user_message="这台设备现在怎么样？",
        context=_build_context(),
        conversation_history=[{"role": "assistant", "content": "上一轮回答"}],
    )

    assert messages[-1] == {"role": "user", "content": "这台设备现在怎么样？"}


def test_generate_agent_reply_real_llm_uses_dashboard_skill_adapter(monkeypatch):
    class FakeFunctionCall:
        type = "function_call"
        name = "get_dashboard_overview"
        arguments = '{"focus":"abnormal"}'
        call_id = "call_1"

    class FakeMessageContent:
        type = "output_text"

        def __init__(self, text: str) -> None:
            self.text = text

    class FakeMessage:
        type = "message"

        def __init__(self, text: str) -> None:
            self.content = [FakeMessageContent(text)]

    class FakeResponse:
        def __init__(self, output, output_text: str = "") -> None:
            self.output = output
            self.output_text = output_text

    class FakeClient:
        def __init__(self) -> None:
            self.calls = []
            self.responses = self

        def create(self, *, model, input, tools):
            self.calls.append({"model": model, "input": list(input), "tools": list(tools)})
            if len(self.calls) == 1:
                return FakeResponse([FakeFunctionCall()])
            return FakeResponse([FakeMessage("工具调用完成")], output_text="工具调用完成")

    fake_client = FakeClient()
    captured = {}

    monkeypatch.setattr("app.agent.chat_agent._create_openai_client", lambda **_: fake_client)
    monkeypatch.setattr(
        "app.agent.chat_agent.get_dashboard_skill_definitions",
        lambda: [{"type": "function", "name": "get_dashboard_overview"}],
    )

    def _fake_invoke(name, arguments, context):
        captured["name"] = name
        captured["arguments"] = arguments
        captured["context"] = context
        return {"ok": True, "devices": []}

    monkeypatch.setattr("app.agent.chat_agent.invoke_dashboard_skill", _fake_invoke)

    reply = generate_agent_reply(
        "当前有哪些异常设备？",
        _build_context(),
        backend_config=AgentBackendConfig(mode="real_llm", model="gpt-5.4", use_local_fallback=False),
        conversation_history=[{"role": "assistant", "content": "上一轮回答"}],
    )

    assert reply == "工具调用完成"
    assert captured["name"] == "get_dashboard_overview"
    assert captured["arguments"] == {"focus": "abnormal"}
    assert fake_client.calls[0]["tools"][0]["name"] == "get_dashboard_overview"
    assert {"role": "user", "content": "当前有哪些异常设备？"} in fake_client.calls[0]["input"]

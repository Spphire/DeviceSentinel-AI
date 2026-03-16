from app.agent.chat_agent import build_agent_hint, generate_agent_reply


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
                "metrics": [
                    {"metric_id": "cpu_usage", "label": "CPU 使用率", "unit": "%"},
                    {"metric_id": "gpu_usage", "label": "GPU 使用率", "unit": "%"},
                ],
                "latest_point": {
                    "device_status": "online",
                    "metrics": {"cpu_usage": 66.0, "gpu_usage": 32.0},
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
                    {"metrics": {"cpu_usage": 40.0, "gpu_usage": 10.0}},
                    {"metrics": {"cpu_usage": 52.0, "gpu_usage": 12.0}},
                    {"metrics": {"cpu_usage": 58.0, "gpu_usage": 18.0}},
                    {"metrics": {"cpu_usage": 66.0, "gpu_usage": 32.0}},
                ],
                "report": "示例报告",
            },
            "sgcc-001": {
                "instance_id": "sgcc-001",
                "device_name": "配电箱 1",
                "category_name": "配电设备",
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


def test_generate_agent_reply_for_device_action_mentions_suggestions():
    reply = generate_agent_reply("办公室电脑为什么告警，建议怎么处理？", _build_context())

    assert "办公室电脑" in reply
    assert "建议" in reply

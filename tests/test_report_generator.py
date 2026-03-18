from app.agent.report_generator import generate_report
from app.analysis.analyzer import analyze_device_status, analyze_simulation_point
from app.models import DeviceReading, SimulationPoint


def test_report_for_normal_device_contains_normal_summary():
    reading = DeviceReading(
        device_id="SGCC-LV-001",
        temperature=42.0,
        voltage=221.0,
        current=50.0,
        timestamp="2026-03-16T10:00:00",
    )

    result = analyze_device_status(reading).to_dict()
    report = generate_report(result)

    assert "运行状态：正常" in report
    assert "当前设备运行总体平稳" in report


def test_report_for_fault_device_contains_warning_content():
    reading = DeviceReading(
        device_id="SGCC-LV-002",
        temperature=73.0,
        voltage=188.0,
        current=122.0,
        timestamp="2026-03-16T10:10:00",
    )

    result = analyze_device_status(reading).to_dict()
    report = generate_report(result)

    assert "运行状态：严重异常" in report
    assert "系统识别到以下异常情况" in report


def test_report_for_offline_device_contains_offline_guidance():
    point = SimulationPoint(
        device_id="SGCC-LV-003",
        timestamp="2026-03-16T10:20:00",
        device_status="offline",
        template_name="offline",
        temperature=None,
        voltage=None,
        current=None,
        fault_label="offline",
    )

    result = analyze_simulation_point(point=point, last_heartbeat="2026-03-16T10:10:00").to_dict()
    report = generate_report(result)

    assert "运行状态：离线" in report
    assert "最后上报时间：2026-03-16T10:10:00" in report
    assert "通信链路" in report


def test_report_includes_knowledge_section_when_references_exist():
    analysis_result = {
        "device_id": "switchgear-demo-001",
        "device_name": "10kV 开关柜 A",
        "category_name": "开关柜设备",
        "status": "warning",
        "risk_level": "high",
        "device_status": "online",
        "metrics": {
            "contact_temperature": 84.0,
            "cabinet_temperature": 35.0,
            "load_current": 318.0,
        },
        "metric_labels": {
            "contact_temperature": "触头温度",
            "cabinet_temperature": "柜内温度",
            "load_current": "负荷电流",
        },
        "summary": "检测到开关柜存在明显温升异常。",
        "issues": [
            {
                "category": "contact_temperature",
                "severity": "high",
                "message": "触头温度达到 84.0℃，超过 70℃ 阈值。",
                "suggestion": "建议立即开展红外测温与接点紧固复核。",
                "standard_reference": "GB/T 12345",
            }
        ],
        "recommended_actions": [
            "立即安排红外测温复核发热点位置，并记录温升趋势",
            "检查母排、触头和电缆接点紧固状态，排查接触电阻增大隐患",
        ],
        "knowledge_references": [
            {
                "title": "开关柜接头过热与红外测温复核",
                "summary": "当开关柜触头、母排或电缆连接点出现明显温升时，应结合红外测温和专项巡视复核。",
                "source_title": "文登区供电公司：红外测温+特巡 筑牢迎峰度冬安全防线",
                "source_url": "https://www.weihai.gov.cn/art/2025/1/3/art_79726_5154529.html",
            }
        ],
    }

    report = generate_report(
        analysis_result,
        metric_definitions=[
            {"metric_id": "contact_temperature", "label": "触头温度", "unit": "℃"},
            {"metric_id": "cabinet_temperature", "label": "柜内温度", "unit": "℃"},
            {"metric_id": "load_current", "label": "负荷电流", "unit": "A"},
        ],
    )

    assert "知识增强处置建议" in report
    assert "知识依据" in report
    assert "开关柜接头过热与红外测温复核" in report
    assert "weihai.gov.cn" in report

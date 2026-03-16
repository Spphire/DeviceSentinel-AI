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

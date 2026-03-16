from app.analysis.analyzer import analyze_device_status
from app.models import DeviceReading


def test_temperature_anomaly_detected():
    reading = DeviceReading(
        device_id="SGCC-LV-001",
        temperature=75.0,
        voltage=220.0,
        current=45.0,
        timestamp="2026-03-16T10:00:00",
    )

    result = analyze_device_status(reading)

    assert result.status == "warning"
    assert len(result.issues) == 1
    assert result.issues[0].category == "temperature"


def test_compound_anomaly_detected():
    reading = DeviceReading(
        device_id="SGCC-LV-002",
        temperature=72.0,
        voltage=185.0,
        current=120.0,
        timestamp="2026-03-16T10:00:00",
    )

    result = analyze_device_status(reading)

    assert result.status == "critical"
    assert result.risk_level == "high"
    assert len(result.issues) == 3


def test_normal_reading_detected():
    reading = DeviceReading(
        device_id="SGCC-LV-003",
        temperature=45.0,
        voltage=220.0,
        current=58.0,
        timestamp="2026-03-16T10:00:00",
    )

    result = analyze_device_status(reading)

    assert result.status == "normal"
    assert result.risk_level == "low"
    assert result.issues == []

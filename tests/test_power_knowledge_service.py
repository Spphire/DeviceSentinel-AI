from app.analysis.template_analyzer import analyze_device_point
from app.models import DeviceTelemetryPoint
from app.services.template_service import load_device_templates


def test_switchgear_analysis_enriches_result_with_contact_overheat_knowledge():
    templates = load_device_templates()
    template = templates["switchgear_simulated"]
    point = DeviceTelemetryPoint(
        instance_id="switchgear-demo-001",
        device_name="10kV 开关柜 A",
        template_id=template.template_id,
        category_name=template.category_name,
        source_type=template.source_type,
        timestamp="2026-03-19T10:00:00",
        device_status="online",
        metrics={
            "contact_temperature": 84.0,
            "cabinet_temperature": 35.0,
            "load_current": 318.0,
        },
        metric_labels={metric.metric_id: metric.label for metric in template.metrics},
        fault_label="contact_overheating",
    )

    result = analyze_device_point(template=template, point=point)

    assert result.status == "critical"
    assert result.knowledge_references
    assert result.knowledge_references[0]["knowledge_id"] == "switchgear_contact_overheat"
    assert result.recommended_actions
    assert "知识库匹配到" in result.summary


def test_distribution_transformer_analysis_matches_low_voltage_unbalance_knowledge():
    templates = load_device_templates()
    template = templates["distribution_transformer_simulated"]
    point = DeviceTelemetryPoint(
        instance_id="transformer-demo-001",
        device_name="台区配变终端 A",
        template_id=template.template_id,
        category_name=template.category_name,
        source_type=template.source_type,
        timestamp="2026-03-19T10:00:00",
        device_status="online",
        metrics={
            "voltage": 198.0,
            "current": 81.0,
            "load_rate": 78.0,
            "imbalance_ratio": 23.0,
        },
        metric_labels={metric.metric_id: metric.label for metric in template.metrics},
        fault_label="low_voltage_unbalance",
    )

    result = analyze_device_point(template=template, point=point)

    assert result.status == "critical"
    assert len(result.issues) >= 2
    assert result.knowledge_references
    assert result.knowledge_references[0]["knowledge_id"] == "distribution_low_voltage_unbalance"

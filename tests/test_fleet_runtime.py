from app.services.fleet_runtime import DeviceFleetRuntime
from app.services.template_service import load_device_templates
from app.services.settings_store import build_device_config


def test_fleet_runtime_supports_mixed_simulated_templates():
    templates = load_device_templates()
    configs = [
        build_device_config(
            {
                "instance_id": "switchgear-001",
                "name": "开关柜 1",
                "template_id": "switchgear_simulated",
                "simulation_profile": "contact_overheating",
            }
        ),
        build_device_config(
            {
                "instance_id": "transformer-001",
                "name": "配变终端 1",
                "template_id": "distribution_transformer_simulated",
                "simulation_profile": "low_voltage_unbalance",
            }
        ),
    ]

    runtime = DeviceFleetRuntime(templates=templates, device_configs=configs, seed=11)
    runtime.step()

    switchgear_snapshot = runtime.get_device_snapshot("switchgear-001")
    transformer_snapshot = runtime.get_device_snapshot("transformer-001")

    assert switchgear_snapshot["point"] is not None
    assert transformer_snapshot["point"] is not None
    assert "contact_temperature" in switchgear_snapshot["point"].metrics
    assert "imbalance_ratio" in transformer_snapshot["point"].metrics
    assert switchgear_snapshot["analysis"]["knowledge_references"]
    assert transformer_snapshot["analysis"]["knowledge_references"]


def test_real_template_without_events_starts_offline():
    templates = load_device_templates()
    configs = [
        build_device_config(
            {
                "instance_id": "pc-test-noevents-001",
                "name": "我的电脑测试机",
                "template_id": "personal_pc_real",
                "simulation_profile": None,
            }
        )
    ]

    runtime = DeviceFleetRuntime(templates=templates, device_configs=configs, seed=11)
    runtime.step()
    snapshot = runtime.get_device_snapshot("pc-test-noevents-001")

    assert snapshot["analysis"]["status"] == "offline"
    assert snapshot["point"].device_status == "offline"

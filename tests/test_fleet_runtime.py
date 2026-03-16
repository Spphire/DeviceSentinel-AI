from app.services.fleet_runtime import DeviceFleetRuntime
from app.services.template_service import load_device_templates
from app.services.settings_store import build_device_config


def test_fleet_runtime_supports_mixed_simulated_templates():
    templates = load_device_templates()
    configs = [
        build_device_config(
            {
                "instance_id": "sgcc-001",
                "name": "SGCC 设备 1",
                "template_id": "sgcc_simulated",
                "simulation_profile": "stable",
            }
        ),
        build_device_config(
            {
                "instance_id": "temp-001",
                "name": "温湿度设备 1",
                "template_id": "temp_humidity_simulated",
                "simulation_profile": "intermittent_fault",
            }
        ),
    ]

    runtime = DeviceFleetRuntime(templates=templates, device_configs=configs, seed=11)
    runtime.step()

    sgcc_snapshot = runtime.get_device_snapshot("sgcc-001")
    sensor_snapshot = runtime.get_device_snapshot("temp-001")

    assert sgcc_snapshot["point"] is not None
    assert sensor_snapshot["point"] is not None
    assert "temperature" in sgcc_snapshot["point"].metrics
    assert "humidity" in sensor_snapshot["point"].metrics


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

"""Service layer connecting simulator, analyzer, MPC wrapper, and report generator."""

from __future__ import annotations

from app.agent.report_generator import generate_report
from app.analysis.analyzer import analyze_device_status
from app.models import DashboardDeviceConfig
from app.data.simulator import (
    DEFAULT_TEMPLATE_SEQUENCE,
    SimulationEngine,
    create_default_configs,
    generate_batch,
    generate_device_reading,
    get_device_ids,
)
from app.mpc.skill_adapter import invoke_local_skill
from app.models import DeviceReading
from app.services.fleet_runtime import DeviceFleetRuntime
from app.services.settings_store import (
    build_device_config,
    create_new_device_payload,
    load_dashboard_settings,
    save_dashboard_settings,
)
from app.services.template_service import load_device_templates

DEFAULT_DEVICE_COUNT = 4
DEFAULT_HISTORY_WINDOW = 60
DEFAULT_REFRESH_INTERVAL_SECONDS = 2
SIMULATION_STEP_MINUTES = 10
MAX_HISTORY_POINTS = 240


def get_default_template_assignments(
    device_count: int,
    existing_assignments: dict[str, str] | None = None,
) -> dict[str, str]:
    existing_assignments = existing_assignments or {}
    assignments: dict[str, str] = {}

    for index, device_id in enumerate(get_device_ids(device_count)):
        assignments[device_id] = existing_assignments.get(
            device_id,
            DEFAULT_TEMPLATE_SEQUENCE[index % len(DEFAULT_TEMPLATE_SEQUENCE)],
        )

    return assignments


def create_simulation_engine(
    device_count: int,
    template_assignments: dict[str, str] | None = None,
    history_limit: int = MAX_HISTORY_POINTS,
    step_minutes: int = SIMULATION_STEP_MINUTES,
    seed: int | None = None,
) -> SimulationEngine:
    configs = create_default_configs(device_count=device_count, template_assignments=template_assignments)
    return SimulationEngine(
        configs=configs,
        history_limit=history_limit,
        step_minutes=step_minutes,
        seed=seed,
    )


def sync_engine_templates(engine: SimulationEngine, template_assignments: dict[str, str]) -> None:
    for device_id, template_name in template_assignments.items():
        if device_id in engine.states:
            engine.set_template(device_id=device_id, template_name=template_name)


def load_runtime_templates():
    return load_device_templates()


def load_persisted_dashboard_settings():
    return load_dashboard_settings()


def save_persisted_dashboard_settings(payload: dict) -> None:
    save_dashboard_settings(payload)


def build_dashboard_device_configs(payloads: list[dict]) -> list[DashboardDeviceConfig]:
    return [build_device_config(item) for item in payloads]


def create_dashboard_runtime(
    templates: dict,
    device_payloads: list[dict],
    history_limit: int = MAX_HISTORY_POINTS,
    step_minutes: int = SIMULATION_STEP_MINUTES,
    seed: int | None = None,
) -> DeviceFleetRuntime:
    configs = build_dashboard_device_configs(device_payloads)
    return DeviceFleetRuntime(
        templates=templates,
        device_configs=configs,
        history_limit=history_limit,
        step_minutes=step_minutes,
        seed=seed,
    )


def create_empty_device_payload(template_id: str) -> dict:
    return create_new_device_payload(template_id)


def run_local_demo(device_id: str = "SGCC-LV-001", anomaly: str | None = "compound") -> dict:
    reading = generate_device_reading(device_id=device_id, anomaly=anomaly)
    analysis_result = analyze_device_status(reading).to_dict()
    report = generate_report(analysis_result)
    return {"reading": reading.to_dict(), "analysis": analysis_result, "report": report}


def run_mpc_demo(reading: DeviceReading) -> dict:
    analysis_result = invoke_local_skill(reading.to_dict())
    report = generate_report(analysis_result)
    return {"reading": reading.to_dict(), "analysis": analysis_result, "report": report}


def run_dashboard_batch(device_count: int = 6) -> list[dict]:
    """Compatibility helper for the original batch table demo."""
    results: list[dict] = []
    for reading in generate_batch(device_count=device_count):
        analysis_result = analyze_device_status(reading).to_dict()
        results.append(
            {
                "reading": reading.to_dict(),
                "analysis": analysis_result,
                "report": generate_report(analysis_result),
            }
        )
    return results

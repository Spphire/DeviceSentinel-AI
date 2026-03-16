"""Simulated device data generation for low-voltage electrical equipment."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from app.models import DeviceReading, DeviceSimulationConfig, DeviceSimulationState, SimulationPoint


SIMULATION_TEMPLATES = ["stable", "intermittent_fault", "frequent_fault", "offline"]
DEFAULT_TEMPLATE_SEQUENCE = ["stable", "intermittent_fault", "frequent_fault", "offline"]
TEMPLATE_DISPLAY_NAMES = {
    "stable": "稳定型",
    "intermittent_fault": "偶发故障型",
    "frequent_fault": "频发故障型",
    "offline": "离线型",
}
FAULT_LABELS = ["over_temperature", "voltage_low", "voltage_high", "over_current", "compound"]
FAULT_DISPLAY_NAMES = {
    "over_temperature": "过温",
    "voltage_low": "欠压",
    "voltage_high": "过压",
    "over_current": "过流",
    "compound": "复合故障",
}

_NORMAL_PROFILE = {
    "stable": {
        "temp_amp": 2.8,
        "temp_noise": 0.5,
        "voltage_amp": 2.5,
        "voltage_noise": 0.6,
        "current_amp": 5.5,
        "current_noise": 1.2,
        "temp_bounds": (32.0, 55.0),
        "voltage_bounds": (210.0, 230.0),
        "current_bounds": (20.0, 82.0),
    },
    "intermittent_fault": {
        "temp_amp": 3.8,
        "temp_noise": 0.9,
        "voltage_amp": 4.5,
        "voltage_noise": 1.0,
        "current_amp": 8.0,
        "current_noise": 1.8,
        "temp_bounds": (34.0, 57.0),
        "voltage_bounds": (204.0, 236.0),
        "current_bounds": (24.0, 88.0),
    },
    "frequent_fault": {
        "temp_amp": 4.5,
        "temp_noise": 1.2,
        "voltage_amp": 6.0,
        "voltage_noise": 1.6,
        "current_amp": 10.0,
        "current_noise": 2.4,
        "temp_bounds": (36.0, 58.5),
        "voltage_bounds": (202.0, 238.0),
        "current_bounds": (28.0, 95.0),
    },
    "offline": {
        "temp_amp": 3.2,
        "temp_noise": 0.8,
        "voltage_amp": 3.2,
        "voltage_noise": 0.8,
        "current_amp": 6.0,
        "current_noise": 1.4,
        "temp_bounds": (33.0, 56.0),
        "voltage_bounds": (208.0, 232.0),
        "current_bounds": (22.0, 84.0),
    },
}


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def get_device_ids(device_count: int) -> list[str]:
    return [f"SGCC-LV-{index + 1:03d}" for index in range(device_count)]


def get_template_display_name(template_name: str) -> str:
    return TEMPLATE_DISPLAY_NAMES.get(template_name, template_name)


def get_fault_display_name(fault_label: str | None) -> str:
    if fault_label is None:
        return "-"
    return FAULT_DISPLAY_NAMES.get(fault_label, fault_label)


def _device_index_from_id(device_id: str) -> int:
    return max(0, int(device_id.rsplit("-", maxsplit=1)[-1]) - 1)


def build_device_config(device_id: str, template_name: str, device_index: int | None = None) -> DeviceSimulationConfig:
    if device_index is None:
        device_index = _device_index_from_id(device_id)

    if template_name == "stable":
        base_temperature = 40.0 + (device_index % 3) * 1.2
        base_voltage = 219.0 + ((device_index % 3) - 1) * 0.9
        base_current = 36.0 + (device_index % 4) * 4.0
    elif template_name == "intermittent_fault":
        base_temperature = 45.0 + (device_index % 3) * 1.5
        base_voltage = 218.0 + ((device_index % 4) - 1.5) * 1.2
        base_current = 48.0 + (device_index % 4) * 5.5
    elif template_name == "frequent_fault":
        base_temperature = 50.5 + (device_index % 3) * 1.6
        base_voltage = 217.0 + ((device_index % 4) - 1.5) * 1.6
        base_current = 70.0 + (device_index % 3) * 6.0
    else:
        base_temperature = 43.0 + (device_index % 3) * 1.4
        base_voltage = 219.0 + ((device_index % 3) - 1) * 1.0
        base_current = 40.0 + (device_index % 4) * 4.5

    return DeviceSimulationConfig(
        device_id=device_id,
        template_name=template_name,
        base_temperature=round(base_temperature, 1),
        base_voltage=round(base_voltage, 1),
        base_current=round(base_current, 1),
    )


def create_default_configs(
    device_count: int,
    template_assignments: dict[str, str] | None = None,
) -> list[DeviceSimulationConfig]:
    template_assignments = template_assignments or {}
    configs: list[DeviceSimulationConfig] = []

    for index, device_id in enumerate(get_device_ids(device_count)):
        template_name = template_assignments.get(device_id, DEFAULT_TEMPLATE_SEQUENCE[index % len(DEFAULT_TEMPLATE_SEQUENCE)])
        configs.append(build_device_config(device_id=device_id, template_name=template_name, device_index=index))

    return configs


class SimulationEngine:
    """Stateful simulation engine for real-time device monitoring demos."""

    def __init__(
        self,
        configs: list[DeviceSimulationConfig],
        history_limit: int = 240,
        step_minutes: int = 10,
        seed: int | None = None,
        start_time: datetime | None = None,
    ) -> None:
        self.history_limit = history_limit
        self.step_minutes = step_minutes
        self.rng = random.Random(seed)
        self.current_time = (start_time or datetime.now()).replace(second=0, microsecond=0)
        self.states: dict[str, DeviceSimulationState] = {}
        self.history: dict[str, list[SimulationPoint]] = {}

        for config in configs:
            phase = self.rng.uniform(0, math.tau)
            self.states[config.device_id] = DeviceSimulationState(config=config, phase=phase)
            self.history[config.device_id] = []

    @property
    def device_ids(self) -> list[str]:
        return list(self.states.keys())

    def has_history(self) -> bool:
        return any(self.history.values())

    def set_template(self, device_id: str, template_name: str) -> None:
        state = self.states[device_id]
        if state.config.template_name == template_name:
            return

        device_index = _device_index_from_id(device_id)
        state.config = build_device_config(device_id=device_id, template_name=template_name, device_index=device_index)
        state.active_fault_label = None
        state.fault_remaining_steps = 0
        state.offline_remaining_steps = 0

    def step(self) -> list[SimulationPoint]:
        from app.analysis.analyzer import analyze_simulation_point

        self.current_time += timedelta(minutes=self.step_minutes)
        timestamp = self.current_time.isoformat(timespec="seconds")
        points: list[SimulationPoint] = []

        for device_id in self.device_ids:
            state = self.states[device_id]
            point = self._generate_point(state=state, timestamp=timestamp)
            analysis = analyze_simulation_point(point=point, last_heartbeat=state.last_heartbeat).to_dict()

            state.latest_point = point
            state.latest_analysis = analysis
            state.step_index += 1

            self.history[device_id].append(point)
            if len(self.history[device_id]) > self.history_limit:
                self.history[device_id].pop(0)

            points.append(point)

        return points

    def get_device_history(self, device_id: str, limit: int | None = None) -> list[SimulationPoint]:
        points = self.history.get(device_id, [])
        if limit is None:
            return list(points)
        return list(points[-limit:])

    def get_device_snapshot(self, device_id: str) -> dict:
        state = self.states[device_id]
        return {
            "point": state.latest_point,
            "analysis": state.latest_analysis,
            "last_heartbeat": state.last_heartbeat,
            "template_name": state.config.template_name,
        }

    def get_overview_rows(self) -> list[dict]:
        rows: list[dict] = []
        for device_id in self.device_ids:
            state = self.states[device_id]
            point = state.latest_point
            analysis = state.latest_analysis or {
                "status": "unknown",
                "risk_level": "-",
                "issues": [],
                "device_status": "offline",
                "last_heartbeat": state.last_heartbeat,
            }
            rows.append(
                {
                    "device_id": device_id,
                    "template_name": state.config.template_name,
                    "device_status": analysis.get("device_status", "online"),
                    "last_heartbeat": analysis.get("last_heartbeat") or state.last_heartbeat or "-",
                    "temperature": None if point is None else point.temperature,
                    "voltage": None if point is None else point.voltage,
                    "current": None if point is None else point.current,
                    "fault_label": None if point is None else point.fault_label,
                    "status": analysis.get("status", "unknown"),
                    "risk_level": analysis.get("risk_level", "-"),
                    "issue_count": len(analysis.get("issues", [])),
                }
            )
        return rows

    def _generate_point(self, state: DeviceSimulationState, timestamp: str) -> SimulationPoint:
        state.phase += 0.42 + self.rng.uniform(-0.05, 0.05)
        template_name = state.config.template_name

        if template_name == "offline" and state.offline_remaining_steps == 0 and self.rng.random() < 0.15:
            state.offline_remaining_steps = self.rng.randint(4, 10)

        if state.offline_remaining_steps > 0:
            state.offline_remaining_steps -= 1
            return SimulationPoint(
                device_id=state.config.device_id,
                timestamp=timestamp,
                device_status="offline",
                template_name=template_name,
                temperature=None,
                voltage=None,
                current=None,
                fault_label="offline",
            )

        fault_label = self._resolve_fault_label(state)
        temperature, voltage, current = self._generate_online_values(state=state, fault_label=fault_label)
        state.last_heartbeat = timestamp

        return SimulationPoint(
            device_id=state.config.device_id,
            timestamp=timestamp,
            device_status="online",
            template_name=template_name,
            temperature=temperature,
            voltage=voltage,
            current=current,
            fault_label=fault_label,
        )

    def _resolve_fault_label(self, state: DeviceSimulationState) -> str | None:
        template_name = state.config.template_name
        if template_name not in ("intermittent_fault", "frequent_fault"):
            state.active_fault_label = None
            state.fault_remaining_steps = 0
            return None

        if state.fault_remaining_steps == 0:
            start_probability = 0.08 if template_name == "intermittent_fault" else 0.20
            if self.rng.random() < start_probability:
                state.active_fault_label = self._select_fault_label(template_name)
                duration = self.rng.randint(2, 4) if template_name == "intermittent_fault" else self.rng.randint(3, 6)
                state.fault_remaining_steps = duration

        if state.fault_remaining_steps > 0:
            fault_label = state.active_fault_label
            state.fault_remaining_steps -= 1
            if state.fault_remaining_steps == 0:
                state.active_fault_label = None
            return fault_label

        return None

    def _select_fault_label(self, template_name: str) -> str:
        if template_name == "frequent_fault":
            weighted_faults = [
                "compound",
                "compound",
                "over_temperature",
                "over_current",
                "voltage_low",
                "voltage_high",
            ]
            return self.rng.choice(weighted_faults)
        return self.rng.choice(FAULT_LABELS)

    def _generate_online_values(self, state: DeviceSimulationState, fault_label: str | None) -> tuple[float, float, float]:
        template_name = state.config.template_name
        profile = _NORMAL_PROFILE[template_name]
        load_wave = math.sin(state.phase)
        voltage_wave = math.sin(state.phase / 1.7 + 0.8)
        current_wave = math.sin(state.phase * 1.2 - 0.5)

        temperature = (
            state.config.base_temperature
            + profile["temp_amp"] * load_wave
            + self.rng.uniform(-profile["temp_noise"], profile["temp_noise"])
        )
        voltage = (
            state.config.base_voltage
            + profile["voltage_amp"] * voltage_wave
            + self.rng.uniform(-profile["voltage_noise"], profile["voltage_noise"])
        )
        current = (
            state.config.base_current
            + profile["current_amp"] * current_wave
            + self.rng.uniform(-profile["current_noise"], profile["current_noise"])
        )

        temp_lower, temp_upper = profile["temp_bounds"]
        voltage_lower, voltage_upper = profile["voltage_bounds"]
        current_lower, current_upper = profile["current_bounds"]

        temperature = _clamp(temperature, temp_lower, temp_upper)
        voltage = _clamp(voltage, voltage_lower, voltage_upper)
        current = _clamp(current, current_lower, current_upper)

        if fault_label == "over_temperature":
            temperature = self.rng.uniform(63.0, 84.0)
        elif fault_label == "voltage_low":
            voltage = self.rng.uniform(180.0, 197.0)
        elif fault_label == "voltage_high":
            voltage = self.rng.uniform(243.0, 258.0)
        elif fault_label == "over_current":
            current = self.rng.uniform(102.0, 136.0)
        elif fault_label == "compound":
            temperature = self.rng.uniform(66.0, 86.0)
            voltage = self.rng.uniform(180.0, 195.0) if self.rng.random() < 0.65 else self.rng.uniform(244.0, 259.0)
            current = self.rng.uniform(108.0, 142.0)

        return round(temperature, 1), round(voltage, 1), round(current, 1)


def generate_device_reading(device_id: str, anomaly: str | None = None) -> DeviceReading:
    """Generate one simulated reading with optional anomaly injection."""
    temperature = round(random.uniform(32.0, 56.0), 1)
    voltage = round(random.uniform(214.0, 226.0), 1)
    current = round(random.uniform(25.0, 78.0), 1)

    if anomaly == "over_temperature":
        temperature = round(random.uniform(61.0, 85.0), 1)
    elif anomaly == "voltage_high":
        voltage = round(random.uniform(243.0, 260.0), 1)
    elif anomaly == "voltage_low":
        voltage = round(random.uniform(180.0, 197.0), 1)
    elif anomaly == "over_current":
        current = round(random.uniform(101.0, 135.0), 1)
    elif anomaly == "compound":
        temperature = round(random.uniform(65.0, 88.0), 1)
        voltage = round(random.uniform(178.0, 194.0), 1)
        current = round(random.uniform(105.0, 140.0), 1)

    return DeviceReading(
        device_id=device_id,
        temperature=temperature,
        voltage=voltage,
        current=current,
    )


def generate_batch(device_count: int = 5, abnormal_ratio: float = 0.4) -> list[DeviceReading]:
    """Generate a batch of readings for MQTT demo scripts and basic tests."""
    readings: list[DeviceReading] = []

    for index, device_id in enumerate(get_device_ids(device_count)):
        anomaly = None
        if random.random() < abnormal_ratio:
            anomaly = random.choice(FAULT_LABELS)
        readings.append(generate_device_reading(device_id=device_id, anomaly=anomaly))

    return readings

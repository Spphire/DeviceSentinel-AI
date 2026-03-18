"""Runtime for template-driven mixed device dashboards."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from app.analysis.template_analyzer import analyze_device_point
from app.models import (
    DashboardDeviceConfig,
    DeviceTelemetryPoint,
    DeviceTemplateDefinition,
    ManagedDeviceState,
)
from app.services.real_device_store import load_real_device_history


SGCC_FAULTS = ["over_temperature", "voltage_low", "voltage_high", "over_current", "compound"]
TEMP_HUMIDITY_FAULTS = ["temperature_high", "temperature_low", "humidity_high", "humidity_low", "compound"]
DISTRIBUTION_TRANSFORMER_FAULTS = ["low_voltage_unbalance", "heavy_overload", "compound"]
SWITCHGEAR_FAULTS = ["contact_overheating", "load_transfer_stress", "compound"]


class DeviceFleetRuntime:
    """Mixed runtime for simulated devices and externally reported real devices."""

    def __init__(
        self,
        templates: dict[str, DeviceTemplateDefinition],
        device_configs: list[DashboardDeviceConfig],
        history_limit: int = 240,
        step_minutes: int = 10,
        seed: int | None = None,
        start_time: datetime | None = None,
    ) -> None:
        self.templates = templates
        self.history_limit = history_limit
        self.step_minutes = step_minutes
        self.rng = random.Random(seed)
        self.current_simulation_time = (start_time or datetime.now()).replace(second=0, microsecond=0)
        self.states: dict[str, ManagedDeviceState] = {}
        self.history: dict[str, list[DeviceTelemetryPoint]] = {}

        for index, config in enumerate(device_configs):
            state = ManagedDeviceState(
                config=config,
                template_id=config.template_id,
                phase=self.rng.uniform(0, math.tau),
                context=self._build_state_context(config=config, index=index),
            )
            self.states[config.instance_id] = state
            self.history[config.instance_id] = []

    @property
    def device_ids(self) -> list[str]:
        return list(self.states.keys())

    def has_history(self) -> bool:
        return any(self.history.values()) or any(state.latest_point is not None for state in self.states.values())

    def get_template(self, instance_id: str) -> DeviceTemplateDefinition:
        return self.templates[self.states[instance_id].config.template_id]

    def get_reference_time(self, instance_id: str) -> datetime:
        template = self.get_template(instance_id)
        if template.source_type == "real":
            return datetime.now().replace(microsecond=0)
        return self.current_simulation_time

    def step(self) -> None:
        self.current_simulation_time += timedelta(minutes=self.step_minutes)

        for instance_id, state in self.states.items():
            template = self.templates[state.config.template_id]
            if template.source_type == "simulated":
                point = self._generate_simulated_point(state=state, template=template)
                self.history[instance_id].append(point)
                if len(self.history[instance_id]) > self.history_limit:
                    self.history[instance_id].pop(0)
            else:
                point = self._refresh_real_device_state(state=state, template=template)

            analysis = analyze_device_point(template=template, point=point, last_heartbeat=state.last_heartbeat).to_dict()
            if point.device_status == "online":
                state.last_heartbeat = point.timestamp

            state.latest_point = point
            state.latest_analysis = analysis
            state.step_index += 1

    def get_overview_rows(self) -> list[dict]:
        rows: list[dict] = []
        for instance_id, state in self.states.items():
            template = self.templates[state.config.template_id]
            analysis = state.latest_analysis or {
                "status": "unknown",
                "risk_level": "-",
                "issues": [],
                "device_status": "offline" if template.source_type == "real" else "unknown",
                "last_heartbeat": state.last_heartbeat,
            }
            point = state.latest_point
            rows.append(
                {
                    "instance_id": instance_id,
                    "device_name": state.config.name,
                    "category_name": template.category_name,
                    "source_type": template.source_type,
                    "device_status": analysis.get("device_status", "unknown"),
                    "last_heartbeat": analysis.get("last_heartbeat") or state.last_heartbeat,
                    "status": analysis.get("status", "unknown"),
                    "risk_level": analysis.get("risk_level", "-"),
                    "issue_count": len(analysis.get("issues", [])),
                    "metric_summary": self._build_metric_summary(point),
                }
            )
        return rows

    def get_device_snapshot(self, instance_id: str) -> dict:
        state = self.states[instance_id]
        template = self.templates[state.config.template_id]
        return {
            "point": state.latest_point,
            "analysis": state.latest_analysis,
            "last_heartbeat": state.last_heartbeat,
            "template": template,
            "config": state.config,
        }

    def get_device_history(self, instance_id: str, limit: int | None = None) -> list[DeviceTelemetryPoint]:
        points = self.history.get(instance_id, [])
        if limit is None:
            return list(points)
        return list(points[-limit:])

    def _build_state_context(self, config: DashboardDeviceConfig, index: int) -> dict:
        template = self.templates[config.template_id]
        kind = template.simulation.get("kind")

        if kind == "sgcc":
            return {
                "base_temperature": round(40.0 + (index % 3) * 1.3, 1),
                "base_voltage": round(219.0 + ((index % 3) - 1) * 1.0, 1),
                "base_current": round(38.0 + (index % 4) * 5.0, 1),
            }

        if kind == "temperature_humidity":
            return {
                "base_temperature": round(23.0 + (index % 3) * 1.4, 1),
                "base_humidity": round(52.0 + (index % 4) * 3.0, 1),
            }

        if kind == "distribution_transformer":
            return {
                "base_voltage": round(219.0 + ((index % 3) - 1) * 1.8, 1),
                "base_current": round(72.0 + (index % 4) * 6.5, 1),
                "base_load_rate": round(52.0 + (index % 3) * 4.5, 1),
                "base_imbalance_ratio": round(5.0 + (index % 3) * 1.8, 1),
            }

        if kind == "switchgear":
            return {
                "base_contact_temperature": round(46.0 + (index % 3) * 2.5, 1),
                "base_cabinet_temperature": round(27.0 + (index % 3) * 1.2, 1),
                "base_load_current": round(248.0 + (index % 4) * 18.0, 1),
            }

        return {}

    def _get_metric_labels(self, template: DeviceTemplateDefinition) -> dict[str, str]:
        return {metric.metric_id: metric.label for metric in template.metrics}

    def _generate_simulated_point(
        self,
        state: ManagedDeviceState,
        template: DeviceTemplateDefinition,
    ) -> DeviceTelemetryPoint:
        state.phase += 0.42 + self.rng.uniform(-0.05, 0.05)
        timestamp = self.current_simulation_time.isoformat(timespec="seconds")
        profile = state.config.simulation_profile or self._get_default_profile(template)
        metric_labels = self._get_metric_labels(template)

        if profile == "offline" and state.offline_remaining_steps == 0 and self.rng.random() < 0.15:
            state.offline_remaining_steps = self.rng.randint(4, 10)

        if state.offline_remaining_steps > 0:
            state.offline_remaining_steps -= 1
            return DeviceTelemetryPoint(
                instance_id=state.config.instance_id,
                device_name=state.config.name,
                template_id=template.template_id,
                category_name=template.category_name,
                source_type=template.source_type,
                timestamp=timestamp,
                device_status="offline",
                metrics={metric.metric_id: None for metric in template.metrics},
                metric_labels=metric_labels,
                fault_label="offline",
            )

        fault_label = self._resolve_fault_label(state=state, template=template, profile=profile)
        metrics = self._generate_simulated_metrics(state=state, template=template, profile=profile, fault_label=fault_label)

        return DeviceTelemetryPoint(
            instance_id=state.config.instance_id,
            device_name=state.config.name,
            template_id=template.template_id,
            category_name=template.category_name,
            source_type=template.source_type,
            timestamp=timestamp,
            device_status="online",
            metrics=metrics,
            metric_labels=metric_labels,
            fault_label=fault_label,
        )

    def _resolve_fault_label(
        self,
        state: ManagedDeviceState,
        template: DeviceTemplateDefinition,
        profile: str,
    ) -> str | None:
        simulation_kind = template.simulation.get("kind")
        if simulation_kind in {"distribution_transformer", "switchgear"}:
            state.active_fault_label = None
            state.fault_remaining_steps = 0
            if profile in {"stable", "offline"}:
                return None
            return profile

        if profile not in ("intermittent_fault", "frequent_fault"):
            state.active_fault_label = None
            state.fault_remaining_steps = 0
            return None

        if state.fault_remaining_steps == 0:
            start_probability = 0.08 if profile == "intermittent_fault" else 0.20
            if self.rng.random() < start_probability:
                state.active_fault_label = self._select_fault_label(template=template, profile=profile)
                duration = self.rng.randint(2, 4) if profile == "intermittent_fault" else self.rng.randint(3, 6)
                state.fault_remaining_steps = duration

        if state.fault_remaining_steps > 0:
            fault_label = state.active_fault_label
            state.fault_remaining_steps -= 1
            if state.fault_remaining_steps == 0:
                state.active_fault_label = None
            return fault_label

        return None

    def _select_fault_label(self, template: DeviceTemplateDefinition, profile: str) -> str:
        if template.simulation.get("kind") == "sgcc":
            if profile == "frequent_fault":
                return self.rng.choice(["compound", "compound", "over_temperature", "over_current", "voltage_low", "voltage_high"])
            return self.rng.choice(SGCC_FAULTS)

        if profile == "frequent_fault":
            return self.rng.choice(["compound", "compound", "temperature_high", "humidity_high", "temperature_low", "humidity_low"])
        return self.rng.choice(TEMP_HUMIDITY_FAULTS)

    def _generate_simulated_metrics(
        self,
        state: ManagedDeviceState,
        template: DeviceTemplateDefinition,
        profile: str,
        fault_label: str | None,
    ) -> dict[str, float | None]:
        kind = template.simulation.get("kind")
        if kind == "sgcc":
            return self._generate_sgcc_metrics(state=state, profile=profile, fault_label=fault_label)
        if kind == "distribution_transformer":
            return self._generate_distribution_transformer_metrics(state=state, profile=profile, fault_label=fault_label)
        if kind == "switchgear":
            return self._generate_switchgear_metrics(state=state, profile=profile, fault_label=fault_label)
        return self._generate_temp_humidity_metrics(state=state, profile=profile, fault_label=fault_label)

    def _generate_sgcc_metrics(
        self,
        state: ManagedDeviceState,
        profile: str,
        fault_label: str | None,
    ) -> dict[str, float]:
        profile_map = {
            "stable": (2.6, 0.5, 2.2, 0.5, 5.5, 1.2, (32.0, 55.0), (210.0, 230.0), (20.0, 82.0)),
            "intermittent_fault": (3.8, 0.9, 4.5, 1.0, 8.0, 1.8, (34.0, 57.0), (204.0, 236.0), (24.0, 88.0)),
            "frequent_fault": (4.5, 1.2, 6.0, 1.4, 10.0, 2.2, (36.0, 58.5), (202.0, 238.0), (28.0, 95.0)),
            "offline": (3.0, 0.6, 3.0, 0.6, 6.0, 1.3, (33.0, 56.0), (208.0, 232.0), (22.0, 84.0)),
        }
        temp_amp, temp_noise, voltage_amp, voltage_noise, current_amp, current_noise, temp_bounds, voltage_bounds, current_bounds = profile_map[profile]

        temperature = self._clamp(
            state.context["base_temperature"] + temp_amp * math.sin(state.phase) + self.rng.uniform(-temp_noise, temp_noise),
            *temp_bounds,
        )
        voltage = self._clamp(
            state.context["base_voltage"] + voltage_amp * math.sin(state.phase / 1.7 + 0.8) + self.rng.uniform(-voltage_noise, voltage_noise),
            *voltage_bounds,
        )
        current = self._clamp(
            state.context["base_current"] + current_amp * math.sin(state.phase * 1.2 - 0.5) + self.rng.uniform(-current_noise, current_noise),
            *current_bounds,
        )

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

        return {
            "temperature": round(temperature, 1),
            "voltage": round(voltage, 1),
            "current": round(current, 1),
        }

    def _generate_temp_humidity_metrics(
        self,
        state: ManagedDeviceState,
        profile: str,
        fault_label: str | None,
    ) -> dict[str, float]:
        profile_map = {
            "stable": (2.0, 0.4, 5.0, 1.2, (18.0, 28.0), (35.0, 70.0)),
            "intermittent_fault": (3.0, 0.8, 8.0, 1.8, (15.0, 29.0), (30.0, 76.0)),
            "frequent_fault": (3.6, 1.1, 10.0, 2.2, (12.0, 30.0), (28.0, 78.0)),
            "offline": (2.4, 0.6, 6.0, 1.4, (16.0, 28.5), (32.0, 72.0)),
        }
        temp_amp, temp_noise, humidity_amp, humidity_noise, temp_bounds, humidity_bounds = profile_map[profile]

        temperature = self._clamp(
            state.context["base_temperature"] + temp_amp * math.sin(state.phase) + self.rng.uniform(-temp_noise, temp_noise),
            *temp_bounds,
        )
        humidity = self._clamp(
            state.context["base_humidity"] + humidity_amp * math.sin(state.phase / 1.4 + 0.5) + self.rng.uniform(-humidity_noise, humidity_noise),
            *humidity_bounds,
        )

        if fault_label == "temperature_high":
            temperature = self.rng.uniform(31.0, 36.0)
        elif fault_label == "temperature_low":
            temperature = self.rng.uniform(-2.0, 4.0)
        elif fault_label == "humidity_high":
            humidity = self.rng.uniform(82.0, 92.0)
        elif fault_label == "humidity_low":
            humidity = self.rng.uniform(10.0, 18.0)
        elif fault_label == "compound":
            temperature = self.rng.uniform(31.0, 36.0)
            humidity = self.rng.uniform(82.0, 92.0)

        return {
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
        }

    def _generate_distribution_transformer_metrics(
        self,
        state: ManagedDeviceState,
        profile: str,
        fault_label: str | None,
    ) -> dict[str, float]:
        profile_map = {
            "stable": (3.2, 0.9, 8.0, 2.0, 6.0, 1.5, 2.8, 0.8),
            "low_voltage_unbalance": (4.0, 1.1, 10.0, 2.2, 7.0, 1.8, 3.0, 0.9),
            "heavy_overload": (4.2, 1.2, 12.0, 2.6, 8.5, 2.0, 3.0, 0.9),
            "compound": (4.5, 1.3, 13.0, 2.8, 9.0, 2.2, 3.2, 1.0),
            "offline": (3.2, 0.9, 8.0, 2.0, 6.0, 1.5, 2.8, 0.8),
        }
        voltage_amp, voltage_noise, current_amp, current_noise, load_amp, load_noise, imbalance_amp, imbalance_noise = profile_map[
            profile
        ]

        voltage = self._clamp(
            state.context["base_voltage"] + voltage_amp * math.sin(state.phase / 1.5 + 0.2) + self.rng.uniform(-voltage_noise, voltage_noise),
            198.0,
            232.0,
        )
        current = self._clamp(
            state.context["base_current"] + current_amp * math.sin(state.phase * 1.1 - 0.5) + self.rng.uniform(-current_noise, current_noise),
            38.0,
            145.0,
        )
        load_rate = self._clamp(
            state.context["base_load_rate"] + load_amp * math.sin(state.phase / 1.8 + 0.7) + self.rng.uniform(-load_noise, load_noise),
            28.0,
            120.0,
        )
        imbalance_ratio = self._clamp(
            state.context["base_imbalance_ratio"] + imbalance_amp * math.sin(state.phase / 1.3 - 0.2) + self.rng.uniform(-imbalance_noise, imbalance_noise),
            2.0,
            36.0,
        )

        if fault_label == "low_voltage_unbalance":
            voltage = self.rng.uniform(193.0, 204.0)
            current = self.rng.uniform(70.0, 92.0)
            load_rate = self.rng.uniform(68.0, 84.0)
            imbalance_ratio = self.rng.uniform(18.0, 32.0)
        elif fault_label == "heavy_overload":
            voltage = self.rng.uniform(198.0, 210.0)
            current = self.rng.uniform(108.0, 138.0)
            load_rate = self.rng.uniform(88.0, 112.0)
            imbalance_ratio = self.rng.uniform(8.0, 16.0)
        elif fault_label == "compound":
            voltage = self.rng.uniform(189.0, 202.0)
            current = self.rng.uniform(112.0, 142.0)
            load_rate = self.rng.uniform(92.0, 118.0)
            imbalance_ratio = self.rng.uniform(18.0, 34.0)

        return {
            "voltage": round(voltage, 1),
            "current": round(current, 1),
            "load_rate": round(load_rate, 1),
            "imbalance_ratio": round(imbalance_ratio, 1),
        }

    def _generate_switchgear_metrics(
        self,
        state: ManagedDeviceState,
        profile: str,
        fault_label: str | None,
    ) -> dict[str, float]:
        profile_map = {
            "stable": (4.5, 0.9, 2.0, 0.6, 24.0, 7.0),
            "contact_overheating": (5.4, 1.2, 2.6, 0.8, 28.0, 8.0),
            "load_transfer_stress": (5.2, 1.0, 2.4, 0.7, 32.0, 9.0),
            "compound": (5.8, 1.4, 2.8, 0.9, 34.0, 10.0),
            "offline": (4.5, 0.9, 2.0, 0.6, 24.0, 7.0),
        }
        contact_amp, contact_noise, cabinet_amp, cabinet_noise, load_amp, load_noise = profile_map[profile]

        contact_temperature = self._clamp(
            state.context["base_contact_temperature"] + contact_amp * math.sin(state.phase / 1.4 + 0.4) + self.rng.uniform(-contact_noise, contact_noise),
            38.0,
            96.0,
        )
        cabinet_temperature = self._clamp(
            state.context["base_cabinet_temperature"] + cabinet_amp * math.sin(state.phase / 1.6 - 0.3) + self.rng.uniform(-cabinet_noise, cabinet_noise),
            22.0,
            48.0,
        )
        load_current = self._clamp(
            state.context["base_load_current"] + load_amp * math.sin(state.phase * 1.2 - 0.6) + self.rng.uniform(-load_noise, load_noise),
            150.0,
            430.0,
        )

        if fault_label == "contact_overheating":
            contact_temperature = self.rng.uniform(72.0, 92.0)
            cabinet_temperature = self.rng.uniform(31.0, 38.0)
            load_current = self.rng.uniform(240.0, 320.0)
        elif fault_label == "load_transfer_stress":
            contact_temperature = self.rng.uniform(63.0, 79.0)
            cabinet_temperature = self.rng.uniform(30.0, 37.0)
            load_current = self.rng.uniform(320.0, 410.0)
        elif fault_label == "compound":
            contact_temperature = self.rng.uniform(76.0, 96.0)
            cabinet_temperature = self.rng.uniform(37.0, 47.0)
            load_current = self.rng.uniform(330.0, 425.0)

        return {
            "contact_temperature": round(contact_temperature, 1),
            "cabinet_temperature": round(cabinet_temperature, 1),
            "load_current": round(load_current, 1),
        }

    def _refresh_real_device_state(
        self,
        state: ManagedDeviceState,
        template: DeviceTemplateDefinition,
    ) -> DeviceTelemetryPoint:
        events = load_real_device_history(state.config.instance_id, limit=self.history_limit)
        metric_labels = self._get_metric_labels(template)
        history_points = [
            DeviceTelemetryPoint(
                instance_id=state.config.instance_id,
                device_name=state.config.name,
                template_id=template.template_id,
                category_name=template.category_name,
                source_type=template.source_type,
                timestamp=event["timestamp"],
                device_status="online",
                metrics=event.get("metrics", {}),
                metric_labels=metric_labels,
                raw_payload=event.get("meta", {}),
            )
            for event in events
        ]
        self.history[state.config.instance_id] = history_points[-self.history_limit :]

        now = datetime.now().replace(microsecond=0)
        if not history_points:
            return DeviceTelemetryPoint(
                instance_id=state.config.instance_id,
                device_name=state.config.name,
                template_id=template.template_id,
                category_name=template.category_name,
                source_type=template.source_type,
                timestamp=now.isoformat(timespec="seconds"),
                device_status="offline",
                metrics={metric.metric_id: None for metric in template.metrics},
                metric_labels=metric_labels,
                fault_label="offline",
            )

        latest = history_points[-1]
        state.last_heartbeat = latest.timestamp
        timeout_seconds = int(template.communication.get("offline_timeout_seconds", 20))
        latest_timestamp = datetime.fromisoformat(latest.timestamp)
        if (now - latest_timestamp).total_seconds() > timeout_seconds:
            return DeviceTelemetryPoint(
                instance_id=state.config.instance_id,
                device_name=state.config.name,
                template_id=template.template_id,
                category_name=template.category_name,
                source_type=template.source_type,
                timestamp=now.isoformat(timespec="seconds"),
                device_status="offline",
                metrics={metric.metric_id: None for metric in template.metrics},
                metric_labels=metric_labels,
                fault_label="offline",
            )

        return latest

    def _build_metric_summary(self, point: DeviceTelemetryPoint | None) -> str:
        if point is None or point.device_status != "online":
            return "-"

        parts = []
        for metric_id, value in point.metrics.items():
            label = point.metric_labels.get(metric_id, metric_id)
            metric_value = "-" if value is None else value
            parts.append(f"{label}:{metric_value}")
        return " | ".join(parts)

    @staticmethod
    def _get_default_profile(template: DeviceTemplateDefinition) -> str:
        profile_options = template.simulation.get("profile_options", [])
        if profile_options:
            return profile_options[0]["id"]
        return "stable"

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

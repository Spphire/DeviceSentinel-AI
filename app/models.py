"""Core data models used across the application."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DeviceReading:
    device_id: str
    temperature: float
    voltage: float
    current: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceSimulationConfig:
    device_id: str
    template_name: str
    base_temperature: float
    base_voltage: float
    base_current: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceTemplateMetric:
    metric_id: str
    label: str
    unit: str = ""
    precision: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceTemplateDefinition:
    template_id: str
    display_name: str
    category_name: str
    source_type: str
    metrics: list[DeviceTemplateMetric]
    simulation: dict[str, Any] = field(default_factory=dict)
    communication: dict[str, Any] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)

    def get_metric(self, metric_id: str) -> DeviceTemplateMetric | None:
        return next((metric for metric in self.metrics if metric.metric_id == metric_id), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "display_name": self.display_name,
            "category_name": self.category_name,
            "source_type": self.source_type,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "simulation": self.simulation,
            "communication": self.communication,
            "analysis": self.analysis,
        }


@dataclass
class DashboardDeviceConfig:
    instance_id: str
    name: str
    template_id: str
    simulation_profile: str | None = None
    communication: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceTelemetryPoint:
    instance_id: str
    device_name: str
    template_id: str
    category_name: str
    source_type: str
    timestamp: str
    device_status: str
    metrics: dict[str, float | None]
    metric_labels: dict[str, str] = field(default_factory=dict)
    fault_label: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SimulationPoint:
    device_id: str
    timestamp: str
    device_status: str
    template_name: str
    temperature: float | None
    voltage: float | None
    current: float | None
    fault_label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_reading(self) -> DeviceReading:
        if self.device_status != "online":
            raise ValueError("Offline simulation points cannot be converted to DeviceReading.")
        if self.temperature is None or self.voltage is None or self.current is None:
            raise ValueError("Online simulation points must contain temperature, voltage, and current.")
        return DeviceReading(
            device_id=self.device_id,
            temperature=self.temperature,
            voltage=self.voltage,
            current=self.current,
            timestamp=self.timestamp,
        )


@dataclass
class DeviceSimulationState:
    config: DeviceSimulationConfig
    step_index: int = 0
    phase: float = 0.0
    fault_remaining_steps: int = 0
    offline_remaining_steps: int = 0
    active_fault_label: str | None = None
    last_heartbeat: str | None = None
    latest_analysis: dict[str, Any] | None = None
    latest_point: SimulationPoint | None = None


@dataclass
class ManagedDeviceState:
    config: DashboardDeviceConfig
    template_id: str
    phase: float = 0.0
    step_index: int = 0
    fault_remaining_steps: int = 0
    offline_remaining_steps: int = 0
    active_fault_label: str | None = None
    last_heartbeat: str | None = None
    latest_analysis: dict[str, Any] | None = None
    latest_point: DeviceTelemetryPoint | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisIssue:
    category: str
    severity: str
    message: str
    suggestion: str
    standard_reference: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisResult:
    device_id: str
    status: str
    risk_level: str
    issues: list[AnalysisIssue]
    metrics: dict[str, float | None]
    summary: str
    device_status: str = "online"
    template_name: str | None = None
    last_heartbeat: str | None = None
    device_name: str | None = None
    template_id: str | None = None
    template_display_name: str | None = None
    category_name: str | None = None
    metric_labels: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "status": self.status,
            "risk_level": self.risk_level,
            "issues": [issue.to_dict() for issue in self.issues],
            "metrics": self.metrics,
            "summary": self.summary,
            "device_status": self.device_status,
            "template_name": self.template_name,
            "last_heartbeat": self.last_heartbeat,
            "device_name": self.device_name,
            "template_id": self.template_id,
            "template_display_name": self.template_display_name,
            "category_name": self.category_name,
            "metric_labels": self.metric_labels,
        }

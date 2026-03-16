"""Thresholds and standard references for SGCC low-voltage device monitoring."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceThresholds:
    nominal_voltage: float = 220.0
    voltage_tolerance_ratio: float = 0.10
    over_temperature_celsius: float = 60.0
    over_current_ampere: float = 100.0

    @property
    def voltage_upper_limit(self) -> float:
        return self.nominal_voltage * (1 + self.voltage_tolerance_ratio)

    @property
    def voltage_lower_limit(self) -> float:
        return self.nominal_voltage * (1 - self.voltage_tolerance_ratio)


STANDARD_REFERENCE = {
    "code": "DL/T 448-2016",
    "name": "电能计量装置技术管理规程",
    "summary": "用于运维分析中的规范化表述参考，可扩展到设备巡视、异常处置建议等场景。",
}

DEFAULT_THRESHOLDS = DeviceThresholds()

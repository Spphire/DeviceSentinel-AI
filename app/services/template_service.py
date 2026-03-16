"""Load device templates from JSON config files."""

from __future__ import annotations

import json
from pathlib import Path

from app.models import DeviceTemplateDefinition, DeviceTemplateMetric


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEVICE_TEMPLATE_DIR = PROJECT_ROOT / "device_templates"


def _build_template_definition(payload: dict) -> DeviceTemplateDefinition:
    metrics = [
        DeviceTemplateMetric(
            metric_id=item["metric_id"],
            label=item["label"],
            unit=item.get("unit", ""),
            precision=int(item.get("precision", 1)),
        )
        for item in payload.get("metrics", [])
    ]
    return DeviceTemplateDefinition(
        template_id=payload["template_id"],
        display_name=payload["display_name"],
        category_name=payload["category_name"],
        source_type=payload["source_type"],
        metrics=metrics,
        simulation=payload.get("simulation", {}),
        communication=payload.get("communication", {}),
        analysis=payload.get("analysis", {}),
    )


def load_device_templates(template_dir: Path | None = None) -> dict[str, DeviceTemplateDefinition]:
    directory = template_dir or DEVICE_TEMPLATE_DIR
    templates: dict[str, DeviceTemplateDefinition] = {}

    for template_path in sorted(directory.glob("*.json")):
        payload = json.loads(template_path.read_text(encoding="utf-8"))
        template = _build_template_definition(payload)
        templates[template.template_id] = template

    return templates


def get_template_options(templates: dict[str, DeviceTemplateDefinition]) -> list[str]:
    return list(templates.keys())

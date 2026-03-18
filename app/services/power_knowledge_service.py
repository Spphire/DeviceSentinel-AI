"""Structured power-operation knowledge retrieval for analysis enrichment."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models import AnalysisResult, DeviceTelemetryPoint, DeviceTemplateDefinition


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE_PATH = PROJECT_ROOT / "knowledge_base" / "power_operation_knowledge.json"


@lru_cache(maxsize=1)
def _load_cached_entries() -> tuple[dict[str, Any], ...]:
    payload = json.loads(KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8"))
    return tuple(payload)


def load_power_knowledge_entries(knowledge_path: Path | None = None) -> list[dict[str, Any]]:
    if knowledge_path is None:
        return copy.deepcopy(list(_load_cached_entries()))
    payload = json.loads(knowledge_path.read_text(encoding="utf-8"))
    return copy.deepcopy(payload)


def retrieve_power_knowledge(
    template: DeviceTemplateDefinition,
    point: DeviceTelemetryPoint,
    analysis_result: AnalysisResult | dict[str, Any],
    limit: int = 3,
) -> list[dict[str, Any]]:
    analysis = analysis_result.to_dict() if isinstance(analysis_result, AnalysisResult) else analysis_result
    issue_categories = {
        issue.get("category")
        for issue in analysis.get("issues", [])
        if isinstance(issue, dict) and issue.get("category")
    }
    metrics = point.metrics or {}
    references: list[dict[str, Any]] = []

    for entry in load_power_knowledge_entries():
        score, matched_signals = _score_knowledge_entry(
            entry=entry,
            template=template,
            point=point,
            analysis=analysis,
            metrics=metrics,
            issue_categories=issue_categories,
        )
        if score <= 0:
            continue

        references.append(
            {
                "knowledge_id": entry["knowledge_id"],
                "title": entry["title"],
                "scenario": entry.get("scenario", ""),
                "summary": entry.get("summary", ""),
                "evidence_points": list(entry.get("evidence_points", [])),
                "recommended_actions": list(entry.get("recommended_actions", [])),
                "source_authority": entry.get("source_authority", ""),
                "source_title": entry.get("source_title", ""),
                "source_url": entry.get("source_url", ""),
                "matched_signals": matched_signals,
                "score": score,
            }
        )

    references.sort(key=lambda item: (-item["score"], item["knowledge_id"]))
    return references[:limit]


def collect_recommended_actions(
    references: list[dict[str, Any]],
    limit: int = 4,
) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for reference in references:
        for action in reference.get("recommended_actions", []):
            normalized = action.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            actions.append(normalized)
            if len(actions) >= limit:
                return actions
    return actions


def _score_knowledge_entry(
    entry: dict[str, Any],
    template: DeviceTemplateDefinition,
    point: DeviceTelemetryPoint,
    analysis: dict[str, Any],
    metrics: dict[str, float | None],
    issue_categories: set[str],
) -> tuple[int, list[str]]:
    applicable_templates = entry.get("applicable_templates") or []
    if applicable_templates and template.template_id not in applicable_templates:
        return 0, []

    applicable_kinds = entry.get("applicable_simulation_kinds") or []
    simulation_kind = template.simulation.get("kind")
    if applicable_kinds and simulation_kind not in applicable_kinds:
        return 0, []

    match = entry.get("match", {})
    score = 0
    matched_signals: list[str] = []
    point_fault_label = point.fault_label
    status = analysis.get("status")
    risk_level = analysis.get("risk_level")
    device_status = analysis.get("device_status") or point.device_status

    if point_fault_label and point_fault_label in match.get("fault_labels", []):
        score += 5
        matched_signals.append(f"fault:{point_fault_label}")

    if status and status in match.get("statuses", []):
        score += 2
        matched_signals.append(f"status:{status}")

    if risk_level and risk_level in match.get("risk_levels", []):
        score += 1
        matched_signals.append(f"risk:{risk_level}")

    if device_status and device_status in match.get("device_statuses", []):
        score += 4
        matched_signals.append(f"device_status:{device_status}")

    matched_categories = sorted(issue_categories.intersection(match.get("issue_categories", [])))
    if matched_categories:
        score += len(matched_categories) * 2
        matched_signals.extend(f"issue:{category}" for category in matched_categories)

    for condition in match.get("metric_conditions", []):
        metric_score = _score_metric_condition(condition=condition, metrics=metrics)
        if metric_score <= 0:
            continue
        score += metric_score
        metric_id = condition["metric_id"]
        matched_signals.append(f"metric:{metric_id}")

    return score, matched_signals


def _score_metric_condition(
    condition: dict[str, Any],
    metrics: dict[str, float | None],
) -> int:
    metric_id = condition.get("metric_id")
    value = metrics.get(metric_id)
    if value is None:
        return 0

    minimum = condition.get("min")
    maximum = condition.get("max")
    if minimum is not None and float(value) < float(minimum):
        return 0
    if maximum is not None and float(value) > float(maximum):
        return 0
    return int(condition.get("score", 1))

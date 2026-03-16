"""MPC-style adapter for the dashboard tool registry."""

from __future__ import annotations

from app.agent.dashboard_tools import get_dashboard_tool_definitions, invoke_dashboard_tool


def get_dashboard_skill_definitions() -> list[dict]:
    return get_dashboard_tool_definitions()


def invoke_dashboard_skill(name: str, arguments: dict, context: dict) -> dict:
    return invoke_dashboard_tool(name=name, arguments=arguments, context=context)

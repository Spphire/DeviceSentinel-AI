"""Smoke-test local_rule / real_llm / local_ollama against the current dashboard context."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.chat_agent import (
    AgentBackendConfig,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_REAL_LLM_MODEL,
    build_agent_context,
    generate_agent_reply,
)
from app.services.demo_service import MAX_HISTORY_POINTS, create_dashboard_runtime, load_runtime_templates
from app.services.settings_store import load_dashboard_settings
def build_smoke_context(
    *,
    settings_path: Path | None = None,
    selected_device_id: str | None = None,
    history_window: int | None = None,
    seed: int = 11,
) -> tuple[dict, dict]:
    settings = load_dashboard_settings(settings_path=settings_path)
    templates = load_runtime_templates()
    runtime = create_dashboard_runtime(
        templates=templates,
        device_payloads=settings["devices"],
        history_limit=MAX_HISTORY_POINTS,
        seed=seed,
    )
    runtime.step()

    device_ids = [device["instance_id"] for device in settings["devices"]]
    active_device_id = selected_device_id or (device_ids[0] if device_ids else None)
    context = build_agent_context(
        runtime=runtime,
        settings=settings,
        selected_device_id=active_device_id or "",
        history_window=history_window or int(settings["system"].get("history_window", 60)),
    )
    return settings, context


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test chat backends with the current dashboard context.")
    parser.add_argument("--backend", choices=["local_rule", "real_llm", "local_ollama"], default="local_rule")
    parser.add_argument("--message", default="这台设备现在怎么样？")
    parser.add_argument("--model")
    parser.add_argument("--settings-path")
    parser.add_argument("--selected-device-id")
    parser.add_argument("--history-window", type=int)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--api-key")
    parser.add_argument("--base-url")
    parser.add_argument("--no-fallback", action="store_true")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    settings_path = None if not args.settings_path else Path(args.settings_path)
    settings, context = build_smoke_context(
        settings_path=settings_path,
        selected_device_id=args.selected_device_id,
        history_window=args.history_window,
        seed=args.seed,
    )
    default_model = DEFAULT_OLLAMA_MODEL if args.backend == "local_ollama" else DEFAULT_REAL_LLM_MODEL
    persisted_mode = str(settings["system"].get("agent_mode", "")).strip()
    persisted_model = str(settings["system"].get("agent_model", "")).strip()
    preferred_model = persisted_model if persisted_mode == args.backend and persisted_model else default_model
    backend_config = AgentBackendConfig(
        mode=args.backend,
        model=(args.model or preferred_model).strip() or default_model,
        use_local_fallback=not args.no_fallback,
        api_key_override=(args.api_key or "").strip() or None,
        base_url_override=(args.base_url or "").strip() or None,
    )

    reply = generate_agent_reply(
        args.message,
        context,
        backend_config=backend_config,
        conversation_history=[{"role": "user", "content": args.message}],
    )

    print(f"[backend] {backend_config.mode} / model={backend_config.model}")
    print(f"[selected_device] {context.get('selected_device_id')}")
    print("--- reply ---")
    print(reply)


if __name__ == "__main__":
    main()

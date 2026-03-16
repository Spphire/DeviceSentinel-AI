"""Push the current monitoring snapshot to GitHub via repository_dispatch."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.status_publisher import build_status_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish the current monitoring snapshot to GitHub.")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--token")
    parser.add_argument("--token-env", default="GITHUB_STATUS_TOKEN")
    parser.add_argument("--api-base-url", default="https://api.github.com")
    parser.add_argument("--event-type", default="publish-status")
    parser.add_argument("--history-window", type=int)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--save-snapshot")
    args = parser.parse_args()

    snapshot = build_status_snapshot(history_window=args.history_window, seed=args.seed)

    if args.save_snapshot:
        Path(args.save_snapshot).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.dry_run:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return

    token = (args.token or os.getenv(args.token_env) or "").strip()
    if not token:
        raise SystemExit(
            f"未检测到 GitHub Token。请传入 --token，或设置环境变量 {args.token_env}。"
        )

    response = requests.post(
        f"{args.api_base_url.rstrip('/')}/repos/{args.owner}/{args.repo}/dispatches",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
        },
        json={
            "event_type": args.event_type,
            "client_payload": {
                "snapshot": snapshot,
            },
        },
        timeout=30,
    )
    if response.status_code != 204:
        raise SystemExit(
            f"GitHub dispatch 调用失败：HTTP {response.status_code} {response.text}"
        )

    print(
        f"已向 {args.owner}/{args.repo} 发送 repository_dispatch 事件 {args.event_type}。"
    )


if __name__ == "__main__":
    main()

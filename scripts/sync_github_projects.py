"""Sync collaboration docs into a GitHub Projects v2 board."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.github_projects_sync import GitHubProjectsClient, build_project_sync_drafts


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync collaboration docs into a GitHub Projects v2 board.")
    parser.add_argument("--owner", required=True, help="GitHub 用户名或组织名。")
    parser.add_argument("--project-number", type=int, required=True, help="GitHub Project 的编号。")
    parser.add_argument(
        "--owner-type",
        choices=["user", "organization"],
        default="user",
        help="Project 归属类型，个人项目用 user，组织项目用 organization。",
    )
    parser.add_argument("--token", help="GitHub token。")
    parser.add_argument("--token-env", default="GITHUB_PROJECTS_TOKEN", help="读取 token 的环境变量名。")
    parser.add_argument("--api-url", default="https://api.github.com/graphql")
    parser.add_argument("--status-field-name", default="Status")
    parser.add_argument("--priority-field-name", default="Priority")
    parser.add_argument("--dry-run", action="store_true", help="只输出将要同步的草稿，不真正调用 GitHub。")
    args = parser.parse_args()

    drafts = build_project_sync_drafts(PROJECT_ROOT)

    if args.dry_run:
        print(
            json.dumps(
                [
                    {
                        "sync_key": draft.sync_key,
                        "title": draft.title,
                        "status_name": draft.status_name,
                        "priority_name": draft.priority_name,
                        "body": draft.body,
                    }
                    for draft in drafts
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    token = (args.token or os.getenv(args.token_env) or "").strip()
    if not token:
        raise SystemExit(
            f"未检测到 GitHub Token。请传入 --token，或设置环境变量 {args.token_env}。"
        )

    client = GitHubProjectsClient(
        token=token,
        owner=args.owner,
        project_number=args.project_number,
        owner_type=args.owner_type,
        api_url=args.api_url,
        status_field_name=args.status_field_name,
        priority_field_name=args.priority_field_name,
    )
    summary = client.sync_drafts(drafts)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

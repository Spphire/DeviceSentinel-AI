"""Sync collaboration docs into GitHub Projects v2 draft issues."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import requests


SYNC_MARKER_PREFIX = "device-sentinel-sync"


@dataclass(frozen=True)
class PlanEntry:
    section: str
    priority: str
    title: str
    status: str
    detail: str


@dataclass(frozen=True)
class SyncDraft:
    sync_key: str
    title: str
    body: str
    status_name: str | None = None
    priority_name: str | None = None


@dataclass(frozen=True)
class MilestoneEntry:
    date_label: str
    phase_label: str
    bullets: list[str]


@dataclass(frozen=True)
class ProjectFieldOption:
    field_id: str
    option_id: str
    field_name: str
    option_name: str


@dataclass(frozen=True)
class ExistingDraft:
    item_id: str
    draft_issue_id: str
    title: str
    body: str
    sync_key: str | None


@dataclass(frozen=True)
class ProjectMetadata:
    project_id: str
    title: str
    fields: dict[tuple[str, str], ProjectFieldOption]
    drafts: dict[str, ExistingDraft]


def load_collaboration_docs(project_root: str | Path) -> dict[str, str]:
    root = Path(project_root)
    return {
        "current_status": (root / "doc" / "current-status.md").read_text(encoding="utf-8"),
        "active_plan": (root / "doc" / "active-plan.md").read_text(encoding="utf-8"),
        "dev_log": (root / "doc" / "dev-log.md").read_text(encoding="utf-8"),
        "development_history": (root / "DEVELOPMENT_HISTORY.md").read_text(encoding="utf-8"),
    }


def build_project_sync_drafts(
    project_root: str | Path,
    *,
    include_milestones: bool = False,
) -> list[SyncDraft]:
    docs = load_collaboration_docs(project_root)
    plan_entries = parse_active_plan(docs["active_plan"])
    drafts = [build_context_draft(docs["current_status"], docs["dev_log"])]
    drafts.extend(build_plan_drafts(plan_entries))
    if include_milestones:
        milestone_entries = parse_development_history_milestones(docs["development_history"])
        drafts.extend(build_milestone_drafts(milestone_entries))
    return drafts


def parse_active_plan(markdown: str) -> list[PlanEntry]:
    entries: list[PlanEntry] = []
    for section_name in ["正在推进", "下一步候选", "中后期", "最近已完成"]:
        section_text = _extract_named_section(markdown, section_name)
        if not section_text:
            continue
        rows = _parse_first_markdown_table(section_text)
        for row in rows:
            if section_name == "正在推进":
                entries.append(
                    PlanEntry(
                        section=section_name,
                        priority=row.get("优先级", "").strip(),
                        title=row.get("事项", "").strip(),
                        status=row.get("当前状态", "").strip(),
                        detail=row.get("说明", "").strip(),
                    )
                )
            elif section_name == "下一步候选":
                entries.append(
                    PlanEntry(
                        section=section_name,
                        priority=row.get("优先级", "").strip(),
                        title=row.get("事项", "").strip(),
                        status="Backlog",
                        detail=row.get("价值", "").strip(),
                    )
                )
            elif section_name == "中后期":
                entries.append(
                    PlanEntry(
                        section=section_name,
                        priority=row.get("优先级", "").strip(),
                        title=row.get("事项", "").strip(),
                        status="Backlog",
                        detail=row.get("说明", "").strip(),
                    )
                )
            elif section_name == "最近已完成":
                time_label = row.get("时间", "").strip()
                entries.append(
                    PlanEntry(
                        section=section_name,
                        priority="",
                        title=row.get("项目", "").strip(),
                        status=time_label or "Done",
                        detail=row.get("结果", "").strip(),
                    )
                )
    return [entry for entry in entries if entry.title]


def build_plan_drafts(entries: list[PlanEntry]) -> list[SyncDraft]:
    drafts: list[SyncDraft] = []
    for entry in entries:
        sync_key = f"plan:{_slugify(entry.section)}:{_slugify(entry.title)}"
        status_name = _map_project_status(entry.section, entry.status)
        priority_name = entry.priority or None

        lines = [
            "自动从 `doc/active-plan.md` 同步。",
            "",
            f"- 来源章节：{entry.section}",
        ]
        if entry.priority:
            lines.append(f"- 优先级：{entry.priority}")
        if entry.status:
            lines.append(f"- 原始状态：{entry.status}")
        if entry.detail:
            lines.append(f"- 说明：{entry.detail}")
        body = "\n".join(lines)

        drafts.append(
            SyncDraft(
                sync_key=sync_key,
                title=entry.title,
                body=body,
                status_name=status_name,
                priority_name=priority_name,
            )
        )
    return drafts


def parse_development_history_milestones(markdown: str) -> list[MilestoneEntry]:
    entries: list[MilestoneEntry] = []
    pattern = re.compile(r"^###\s+([0-9]{4}-[0-9]{2}-[0-9]{2})\s+(.+?阶段)\s*$", flags=re.MULTILINE)
    matches = list(pattern.finditer(markdown))
    for index, match in enumerate(matches):
        start = match.end()
        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            next_heading = re.search(r"^###\s+.+$", markdown[start:], flags=re.MULTILINE)
            end = start + next_heading.start() if next_heading else len(markdown)
        block = markdown[start:end]
        bullets = _extract_stage_bullets(block)
        if bullets:
            entries.append(
                MilestoneEntry(
                    date_label=match.group(1),
                    phase_label=match.group(2),
                    bullets=bullets,
                )
            )
    return entries


def build_milestone_drafts(entries: list[MilestoneEntry]) -> list[SyncDraft]:
    drafts: list[SyncDraft] = []
    for entry in entries:
        body_lines = [
            "自动从 `DEVELOPMENT_HISTORY.md` 同步。",
            "",
            f"- 时间：{entry.date_label}",
            f"- 阶段：{entry.phase_label}",
            "",
            "## 阶段成果",
        ]
        body_lines.extend(f"- {item}" for item in entry.bullets[:8])
        if len(entry.bullets) > 8:
            body_lines.append(f"- 其余 {len(entry.bullets) - 8} 条细节请查看 `DEVELOPMENT_HISTORY.md`。")

        drafts.append(
            SyncDraft(
                sync_key=f"milestone:{_slugify(entry.phase_label)}",
                title=f"Milestone · {entry.phase_label}",
                body="\n".join(body_lines),
                status_name="Done",
            )
        )
    return drafts


def build_context_draft(current_status_markdown: str, dev_log_markdown: str) -> SyncDraft:
    update_date = _extract_after_label(current_status_markdown, "最后更新：") or "未知"
    stage_items = _extract_bullets_from_named_section(current_status_markdown, "当前阶段")[:5]
    focus_items = _extract_numbered_lines_from_named_section(current_status_markdown, "当前协作重点")[:5]
    caution_items = _extract_bullets_from_named_section(current_status_markdown, "当前不建议优先动的部分")[:3]
    latest_log_header, latest_log_items = extract_latest_dev_log(dev_log_markdown)

    body_lines = [
        "自动从 `doc/current-status.md` 与 `doc/dev-log.md` 同步。",
        "",
        f"- 文档最后更新：{update_date}",
        "",
        "## 当前阶段",
    ]
    body_lines.extend(f"- {item}" for item in stage_items or ["暂无阶段摘要"])
    body_lines.append("")
    body_lines.append("## 当前协作重点")
    body_lines.extend(f"- {item}" for item in focus_items or ["暂无协作重点"])
    body_lines.append("")
    body_lines.append("## 当前注意事项")
    body_lines.extend(f"- {item}" for item in caution_items or ["暂无注意事项"])
    body_lines.append("")
    body_lines.append(f"## 最近开发日志（{latest_log_header or '暂无'}）")
    body_lines.extend(f"- {item}" for item in latest_log_items[:6] or ["暂无开发日志"])

    return SyncDraft(
        sync_key="docs:current-context",
        title="Current project context",
        body="\n".join(body_lines),
        status_name="Ready",
    )


def extract_latest_dev_log(markdown: str) -> tuple[str | None, list[str]]:
    match = re.search(r"^##\s+([0-9]{4}-[0-9]{2}-[0-9]{2})\s*$", markdown, flags=re.MULTILINE)
    if not match:
        return None, []
    start = match.end()
    next_match = re.search(r"^##\s+.+$", markdown[start:], flags=re.MULTILINE)
    end = start + next_match.start() if next_match else len(markdown)
    block = markdown[start:end]

    items: list[str] = []
    current_topic = ""
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("### "):
            current_topic = line[4:].strip()
            continue
        if line.startswith("- "):
            detail = line[2:].strip()
            items.append(f"{current_topic}：{detail}" if current_topic else detail)
    return match.group(1), items


def ensure_sync_marker(body: str, sync_key: str) -> str:
    marker = f"<!-- {SYNC_MARKER_PREFIX}:{sync_key} -->"
    body = body.strip()
    if marker in body:
        return body
    return f"{body}\n\n{marker}".strip()


def extract_sync_key(body: str | None) -> str | None:
    if not body:
        return None
    match = re.search(rf"<!--\s*{SYNC_MARKER_PREFIX}:(.+?)\s*-->", body)
    return match.group(1).strip() if match else None


class GitHubProjectsClient:
    def __init__(
        self,
        *,
        token: str,
        owner: str,
        project_number: int,
        owner_type: str = "user",
        api_url: str = "https://api.github.com/graphql",
        status_field_name: str = "Status",
        priority_field_name: str = "Priority",
        session: requests.Session | None = None,
    ) -> None:
        self.owner = owner
        self.project_number = project_number
        self.owner_type = owner_type
        self.api_url = api_url
        self.status_field_name = status_field_name
        self.priority_field_name = priority_field_name
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
            }
        )

    def load_project_metadata(self) -> ProjectMetadata:
        query = _build_project_query(self.owner_type)
        payload = {"query": query, "variables": {"owner": self.owner, "number": self.project_number}}
        response = self.session.post(self.api_url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        _raise_graphql_errors(data)

        owner_payload = data["data"][self.owner_type]
        if not owner_payload or not owner_payload.get("projectV2"):
            raise RuntimeError(
                f"未找到 {self.owner_type} {self.owner} 的 GitHub Project #{self.project_number}。"
            )

        project = owner_payload["projectV2"]
        fields = _parse_project_fields(
            project.get("fields", {}).get("nodes", []),
            self.status_field_name,
            self.priority_field_name,
        )
        drafts = _parse_existing_drafts(project.get("items", {}).get("nodes", []))
        return ProjectMetadata(
            project_id=project["id"],
            title=project["title"],
            fields=fields,
            drafts=drafts,
        )

    def create_draft_issue(self, project_id: str, draft: SyncDraft) -> ExistingDraft:
        query = """
mutation ($projectId: ID!, $title: String!, $body: String!) {
  addProjectV2DraftIssue(input: {
    projectId: $projectId,
    title: $title,
    body: $body
  }) {
    projectItem {
      id
      content {
        __typename
        ... on DraftIssue {
          id
          title
          body
        }
      }
    }
  }
}
"""
        body = ensure_sync_marker(draft.body, draft.sync_key)
        response = self.session.post(
            self.api_url,
            json={
                "query": query,
                "variables": {"projectId": project_id, "title": draft.title, "body": body},
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        _raise_graphql_errors(data)

        project_item = data["data"]["addProjectV2DraftIssue"]["projectItem"]
        content = project_item["content"]
        return ExistingDraft(
            item_id=project_item["id"],
            draft_issue_id=content["id"],
            title=content["title"],
            body=content["body"],
            sync_key=draft.sync_key,
        )

    def update_draft_issue(self, existing: ExistingDraft, draft: SyncDraft) -> ExistingDraft:
        query = """
mutation ($draftIssueId: ID!, $title: String!, $body: String!) {
  updateProjectV2DraftIssue(input: {
    draftIssueId: $draftIssueId,
    title: $title,
    body: $body
  }) {
    draftIssue {
      id
      title
      body
    }
  }
}
"""
        body = ensure_sync_marker(draft.body, draft.sync_key)
        response = self.session.post(
            self.api_url,
            json={
                "query": query,
                "variables": {"draftIssueId": existing.draft_issue_id, "title": draft.title, "body": body},
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        _raise_graphql_errors(data)

        issue = data["data"]["updateProjectV2DraftIssue"]["draftIssue"]
        return ExistingDraft(
            item_id=existing.item_id,
            draft_issue_id=issue["id"],
            title=issue["title"],
            body=issue["body"],
            sync_key=draft.sync_key,
        )

    def update_single_select_field(self, project_id: str, item_id: str, option: ProjectFieldOption) -> None:
        query = """
mutation ($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId,
    itemId: $itemId,
    fieldId: $fieldId,
    value: {
      singleSelectOptionId: $optionId
    }
  }) {
    projectV2Item {
      id
    }
  }
}
"""
        response = self.session.post(
            self.api_url,
            json={
                "query": query,
                "variables": {
                    "projectId": project_id,
                    "itemId": item_id,
                    "fieldId": option.field_id,
                    "optionId": option.option_id,
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        _raise_graphql_errors(data)

    def delete_project_item(self, project_id: str, item_id: str) -> None:
        query = """
mutation ($projectId: ID!, $itemId: ID!) {
  deleteProjectV2Item(input: {
    projectId: $projectId,
    itemId: $itemId
  }) {
    deletedItemId
  }
}
"""
        response = self.session.post(
            self.api_url,
            json={
                "query": query,
                "variables": {
                    "projectId": project_id,
                    "itemId": item_id,
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        _raise_graphql_errors(data)

    def sync_drafts(self, drafts: list[SyncDraft]) -> dict[str, Any]:
        metadata = self.load_project_metadata()
        summary = {
            "project_title": metadata.title,
            "created": [],
            "updated": [],
            "field_updates": [],
            "deleted": [],
            "warnings": [],
        }

        existing_drafts = dict(metadata.drafts)
        desired_sync_keys = {draft.sync_key for draft in drafts}
        retained_item_ids: set[str] = set()
        for draft in drafts:
            existing = _find_existing_draft_for_sync(
                existing_drafts=existing_drafts,
                sync_key=draft.sync_key,
                title=draft.title,
                retained_item_ids=retained_item_ids,
            )
            if existing is None:
                existing = self.create_draft_issue(metadata.project_id, draft)
                existing_drafts[draft.sync_key] = existing
                summary["created"].append(draft.title)
            else:
                target_body = ensure_sync_marker(draft.body, draft.sync_key)
                if existing.title != draft.title or existing.body.strip() != target_body.strip():
                    existing = self.update_draft_issue(existing, draft)
                    existing_drafts[draft.sync_key] = existing
                    summary["updated"].append(draft.title)
                existing_drafts[draft.sync_key] = existing
            retained_item_ids.add(existing.item_id)

            for field_name, desired_option_name in [
                (self.status_field_name, draft.status_name),
                (self.priority_field_name, draft.priority_name),
            ]:
                if not desired_option_name:
                    continue
                option = metadata.fields.get((field_name, desired_option_name))
                if not option:
                    summary["warnings"].append(
                        f"项目字段 {field_name} 中不存在选项 {desired_option_name}，已跳过 {draft.title}。"
                    )
                    continue
                self.update_single_select_field(metadata.project_id, existing.item_id, option)
                summary["field_updates"].append(f"{draft.title}: {field_name} -> {desired_option_name}")

        for sync_key, existing in metadata.drafts.items():
            if sync_key in desired_sync_keys:
                continue
            if existing.item_id in retained_item_ids:
                continue
            self.delete_project_item(metadata.project_id, existing.item_id)
            summary["deleted"].append(existing.title)
        return summary


def _build_project_query(owner_type: str) -> str:
    if owner_type not in {"user", "organization"}:
        raise ValueError("owner_type 只能是 user 或 organization。")
    return f"""
query ($owner: String!, $number: Int!) {{
  {owner_type}(login: $owner) {{
    projectV2(number: $number) {{
      id
      title
      fields(first: 50) {{
        nodes {{
          __typename
          ... on ProjectV2FieldCommon {{
            id
            name
            dataType
          }}
          ... on ProjectV2SingleSelectField {{
            options {{
              id
              name
            }}
          }}
        }}
      }}
      items(first: 100) {{
        nodes {{
          id
          content {{
            __typename
            ... on DraftIssue {{
              id
              title
              body
            }}
          }}
        }}
      }}
    }}
  }}
}}
"""


def _parse_project_fields(
    nodes: list[dict[str, Any]],
    status_field_name: str,
    priority_field_name: str,
) -> dict[tuple[str, str], ProjectFieldOption]:
    fields: dict[tuple[str, str], ProjectFieldOption] = {}
    tracked_names = {status_field_name, priority_field_name}
    for node in nodes:
        if node.get("name") not in tracked_names or node.get("dataType") != "SINGLE_SELECT":
            continue
        for option in node.get("options", []):
            fields[(node["name"], option["name"])] = ProjectFieldOption(
                field_id=node["id"],
                option_id=option["id"],
                field_name=node["name"],
                option_name=option["name"],
            )
    return fields


def _parse_existing_drafts(nodes: list[dict[str, Any]]) -> dict[str, ExistingDraft]:
    drafts: dict[str, ExistingDraft] = {}
    for node in nodes:
        content = node.get("content") or {}
        if content.get("__typename") != "DraftIssue":
            continue
        sync_key = extract_sync_key(content.get("body"))
        if not sync_key:
            continue
        drafts[sync_key] = ExistingDraft(
            item_id=node["id"],
            draft_issue_id=content["id"],
            title=content["title"],
            body=content.get("body") or "",
            sync_key=sync_key,
        )
    return drafts


def _find_existing_draft_for_sync(
    *,
    existing_drafts: dict[str, ExistingDraft],
    sync_key: str,
    title: str,
    retained_item_ids: set[str],
) -> ExistingDraft | None:
    by_key = existing_drafts.get(sync_key)
    if by_key is not None and by_key.item_id not in retained_item_ids:
        return by_key

    title_matches = [
        draft
        for draft in existing_drafts.values()
        if draft.title == title and draft.item_id not in retained_item_ids
    ]
    if len(title_matches) == 1:
        return title_matches[0]
    return None


def _extract_named_section(markdown: str, section_name: str) -> str:
    pattern = rf"^##\s+\d+\.\s+{re.escape(section_name)}\s*$"
    match = re.search(pattern, markdown, flags=re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+\d+\.\s+.+$", markdown[start:], flags=re.MULTILINE)
    end = start + next_match.start() if next_match else len(markdown)
    return markdown[start:end].strip()


def _extract_bullets_from_named_section(markdown: str, section_name: str) -> list[str]:
    section = _extract_named_section(markdown, section_name)
    return [line.strip()[2:].strip() for line in section.splitlines() if line.strip().startswith("- ")]


def _extract_numbered_lines_from_named_section(markdown: str, section_name: str) -> list[str]:
    section = _extract_named_section(markdown, section_name)
    items = []
    for line in section.splitlines():
        stripped = line.strip()
        match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if match:
            items.append(match.group(1).strip())
    return items


def _extract_after_label(markdown: str, label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}\s*(.+)", markdown)
    return match.group(1).strip() if match else None


def _parse_first_markdown_table(section_text: str) -> list[dict[str, str]]:
    table_lines = []
    for line in section_text.splitlines():
        if line.strip().startswith("|"):
            table_lines.append(line.rstrip())
        elif table_lines:
            break
    if len(table_lines) < 2:
        return []

    headers = [cell.strip() for cell in table_lines[0].strip().strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def _extract_stage_bullets(block: str) -> list[str]:
    bullets: list[str] = []
    for raw_line in block.splitlines():
        if raw_line.startswith("- "):
            bullets.append(raw_line[2:].strip())
            continue

        stripped = raw_line.strip()
        if not stripped or not bullets:
            continue

        nested_match = re.match(r"^[-*]\s+(.*)$", stripped)
        numbered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        nested_text = ""
        if nested_match:
            nested_text = nested_match.group(1).strip()
        elif numbered_match:
            nested_text = numbered_match.group(1).strip()

        if nested_text:
            bullets[-1] = f"{bullets[-1]}；{nested_text}"
    return bullets


def _map_project_status(section: str, raw_status: str) -> str:
    text = raw_status.lower()
    if section == "最近已完成":
        return "Done"
    if section in {"下一步候选", "中后期"}:
        return "Backlog"
    if any(token in text for token in ["待推进", "待开始", "待确认", "待排期"]):
        return "Ready"
    if any(token in text for token in ["推进", "进行", "联调", "处理中", "开发中"]):
        return "In Progress"
    if any(token in text for token in ["验证", "验收", "review", "审查"]):
        return "In Review"
    return "Ready"


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", lowered).strip("-")
    return slug or "item"


def _raise_graphql_errors(data: dict[str, Any]) -> None:
    errors = data.get("errors") or []
    if errors:
        message = "; ".join(error.get("message", "GraphQL error") for error in errors)
        raise RuntimeError(message)

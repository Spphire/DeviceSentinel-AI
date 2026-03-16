from app.services.github_projects_sync import (
    build_context_draft,
    build_plan_drafts,
    ensure_sync_marker,
    extract_latest_dev_log,
    extract_sync_key,
    parse_active_plan,
)


ACTIVE_PLAN = """# 当前计划

最后更新：2026-03-17

## 1. 正在推进

| 优先级 | 事项 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| P2 | 真实模型模式联通与稳定性验证 | 待推进 | 页面已具备 `real_llm` 后端适配，但当前仍未稳定完成真实账号验证 |
| P2 | backend manager 继续增强 | 联调中 | 当前已能托管共享网关并按配置重载，但缺少 PID 文件、显式健康检查等细节 |

## 2. 下一步候选

| 优先级 | 事项 | 价值 |
| --- | --- | --- |
| P2 | 评估 MQTT 作为共享 HTTP 网关的补充接入模式 | 便于多设备、弱网重连、跨机房场景扩展 |

## 3. 中后期

| 优先级 | 事项 | 说明 |
| --- | --- | --- |
| P3 | 数据持久化升级 | 从 JSON 文件逐步迁移到更稳定的数据存储 |

## 4. 最近已完成

| 时间 | 项目 | 结果 |
| --- | --- | --- |
| 2026-03-17 | GitHub 状态发布 | 已新增 repository dispatch + Actions + Pages 状态摘要链路 |
"""


CURRENT_STATUS = """# 当前状态

最后更新：2026-03-17

## 1. 当前阶段

- 模板驱动的混合设备监测面板已稳定可用
- 真实设备接入已收敛为“共享 HTTP 网关 + backend manager”

## 6. 当前协作重点

1. 真实模型模式真正联通可用账号并验证稳定性
2. 继续收敛 Tool / Skill 两套入口，让聊天主流程统一走 Skill adapter

## 7. 当前不建议优先动的部分

- 不建议再把真实设备接入改回“设备级 host / port / path”
"""


DEV_LOG = """# 开发日志

## 2026-03-17

### 共享网关与后端管理

- 将真实设备接入从“每台设备单独配置 `host / port / path`”重构为“全局共享网关配置”
- 新增 `scripts/run_backend.py`，由独立 backend manager 托管共享 HTTP 遥测网关

## 2026-03-16

### 本地模型接入

- 在本机完成 `Ollama + qwen2.5:7b` 部署
"""


def test_parse_active_plan_reads_all_sections():
    entries = parse_active_plan(ACTIVE_PLAN)

    assert [entry.title for entry in entries] == [
        "真实模型模式联通与稳定性验证",
        "backend manager 继续增强",
        "评估 MQTT 作为共享 HTTP 网关的补充接入模式",
        "数据持久化升级",
        "GitHub 状态发布",
    ]
    assert entries[0].priority == "P2"
    assert entries[-1].status == "2026-03-17"


def test_build_plan_drafts_maps_status_and_priority():
    drafts = build_plan_drafts(parse_active_plan(ACTIVE_PLAN))

    assert drafts[0].status_name == "Ready"
    assert drafts[0].priority_name == "P2"
    assert drafts[1].status_name == "In Progress"
    assert drafts[2].status_name == "Backlog"
    assert drafts[-1].status_name == "Done"
    assert "自动从 `doc/active-plan.md` 同步。" in drafts[0].body


def test_build_context_draft_includes_status_and_dev_log():
    draft = build_context_draft(CURRENT_STATUS, DEV_LOG)

    assert draft.sync_key == "docs:current-context"
    assert draft.status_name == "Ready"
    assert "## 当前阶段" in draft.body
    assert "共享网关与后端管理" in draft.body
    assert "真实模型模式真正联通可用账号并验证稳定性" in draft.body


def test_extract_latest_dev_log_prefers_latest_date_block():
    date_label, items = extract_latest_dev_log(DEV_LOG)

    assert date_label == "2026-03-17"
    assert items[0].startswith("共享网关与后端管理")


def test_sync_marker_round_trip():
    body = ensure_sync_marker("正文", "plan:demo")

    assert extract_sync_key(body) == "plan:demo"
    assert ensure_sync_marker(body, "plan:demo") == body

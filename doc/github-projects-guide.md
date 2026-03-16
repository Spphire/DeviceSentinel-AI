# GitHub Projects 同步指南

这份文档说明如何把仓库内的协作文档同步到 GitHub Projects v2 看板，方便合作 coder 直接在 GitHub 上查看当前状态。

## 1. 当前同步内容

脚本入口：

```bash
python scripts/sync_github_projects.py --owner <GitHub用户名或组织名> --project-number <项目编号>
```

默认会同步两类内容：

- `doc/current-status.md` + `doc/dev-log.md`
  - 生成一张 `Current project context` 草稿卡片
- `doc/active-plan.md`
  - 生成或更新计划卡片
  - 自动写入 `Status`
  - 自动写入 `Priority`

## 2. 推荐的看板字段

建议在 GitHub Projects 中先准备这两个单选字段：

### Status

建议选项：

- `Backlog`
- `Ready`
- `In Progress`
- `In Review`
- `Done`

### Priority

建议选项：

- `P0`
- `P1`
- `P2`
- `P3`

如果字段名不是 `Status` / `Priority`，可在脚本参数中覆盖：

```bash
python scripts/sync_github_projects.py --owner <owner> --project-number <number> --status-field-name Workflow --priority-field-name Level
```

## 3. 文档到看板的映射规则

### `doc/current-status.md`

- 生成一张固定的上下文卡：
  - 标题：`Current project context`
  - 内容包含：
    - 当前阶段
    - 当前协作重点
    - 当前注意事项
    - 最近开发日志摘录

### `doc/active-plan.md`

- `正在推进`
  - 默认同步为 `Ready`
  - 如果“当前状态”包含“联调中 / 进行中 / 开发中”等词，会映射到 `In Progress`
  - 如果包含“验证 / 审查”等词，会映射到 `In Review`
- `下一步候选`
  - 同步到 `Backlog`
- `中后期`
  - 同步到 `Backlog`
- `最近已完成`
  - 同步到 `Done`

## 4. 同步前先本地预览

先用 dry-run 看即将创建的卡片内容：

```bash
python scripts/sync_github_projects.py --owner <owner> --project-number <number> --dry-run
```

这不会调用 GitHub API，只会打印将要同步的草稿 JSON。

## 5. 实际同步

先准备一个有 Project 写权限的 GitHub token，并设置环境变量：

```bash
set GITHUB_PROJECTS_TOKEN=<你的 GitHub Token>
```

然后执行：

```bash
python scripts/sync_github_projects.py --owner <owner> --project-number <number>
```

如果项目属于组织，请加：

```bash
python scripts/sync_github_projects.py --owner <org> --owner-type organization --project-number <number>
```

## 6. 当前限制

- 当前脚本只同步 GitHub Projects v2 的 `Draft issue`
- 当前只会创建或更新带同步标记的卡片，不会自动删除其他人工维护的卡片
- 当前默认最多扫描项目中的前 100 个已有卡片
- 当前更适合“计划 / 状态 / 协作上下文”同步，不适合直接承载高频设备日志

## 7. 推荐协作流程

建议后续保持这套节奏：

1. 每轮实质性改动后更新：
   - `doc/current-status.md`
   - `doc/active-plan.md`
   - `doc/dev-log.md`
2. 本地执行一次：

```bash
python scripts/sync_github_projects.py --owner <owner> --project-number <number>
```

3. 合作 coder 在 GitHub Projects 看板查看：
   - 当前上下文卡
   - Ready / In Progress / Done 列中的任务变化

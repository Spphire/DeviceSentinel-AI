# GitHub 发布与展示指南

## 1. 仓库首页建议

将根目录 `README.md` 作为 GitHub 首页展示内容，它现在已经承担：

- 项目概述
- 当前状态
- 文档导航
- 架构图
- 快速开始
- GitHub 展示建议

## 2. About 区建议填写

### Description

建议填写：

```text
模板驱动的电气设备状态监测 AI Agent 演示系统，支持模拟设备与真实设备混合接入。
```

### Topics

建议添加：

```text
streamlit
iot
ai-agent
mpc-skill
python
graduation-project
state-monitoring
```

## 3. 仓库页面建议布局

### Code 页

- 首页看 `README.md`
- 重点阅读 `doc/README.md`
- 技术专项看 `docs/mpc_skill_guide.md`

### Issues 页

- 使用仓库内置的 Bug / Feature 模板
- 将需求、问题、优化都沉淀到 Issue

### Pull Requests 页

- 使用内置 PR 模板
- 每次改动记录验证方式和影响范围

### Projects 页

建议创建一个看板，至少包含这几列：

1. Backlog
2. In Progress
3. Review
4. Done

## 4. 建议置顶的文档入口

如果你希望 GitHub 页面“一眼看清”，建议按这个顺序引导：

1. `README.md`
2. `doc/project-architecture.md`
3. `doc/completed-features.md`
4. `doc/deployment-guide.md`
5. `doc/roadmap.md`

## 5. 建议后续补充的 GitHub 能力

- GitHub Actions：自动运行 `python -m pytest`
- GitHub Discussions：沉淀方案讨论与设计记录
- Releases：保存答辩版演示快照
- Wiki：如果后续文档继续膨胀，可以把长期文档迁移到 Wiki

## 6. 首次推送建议流程

1. 在 GitHub 网页端创建一个空仓库
2. 将本地仓库绑定为远程 `origin`
3. 推送 `main` 分支
4. 回到仓库网页配置 About 区和 Topics
5. 检查 README、`doc/` 和 `.github/` 模板展示是否正常

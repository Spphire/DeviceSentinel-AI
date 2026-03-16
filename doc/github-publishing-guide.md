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
- 协作开发先看 `doc/current-status.md`、`doc/active-plan.md`、`doc/dev-log.md`
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

## 6. 自动同步状态页与摘要看板

当前仓库已经补上了一套“本地状态 -> GitHub Actions -> GitHub Pages”的自动发布骨架：

- 工作流：`.github/workflows/publish-status.yml`
- 本地构建脚本：`scripts/build_status_site.py`
- 本地推送脚本：`scripts/publish_status_snapshot.py`

### 6.1 这套链路适合做什么

- 自动同步设备状态摘要
- 自动发布一个公开可访问的静态状态页
- 自动保存最近一次状态快照 artifact

### 6.2 这套链路不适合做什么

- 不适合长期存储高频原始日志
- 不适合秒级实时遥测看板

更适合放到 GitHub 的是“摘要、最近状态、异常列表、结构化快照”，而不是连续刷新的完整遥测流。

### 6.3 首次启用方式

1. 在 GitHub 仓库设置中启用 Pages，并将构建来源切到 GitHub Actions
2. 准备一个可触发仓库 `repository_dispatch` 的 Token
3. 在本机设置环境变量：

```bash
set GITHUB_STATUS_TOKEN=<你的 GitHub Token>
```

4. 本地触发一次状态发布：

```bash
python scripts/publish_status_snapshot.py --owner Spphire --repo DeviceSentinel-AI
```

5. 等待 Actions 跑完后，即可在 GitHub Pages 页面查看状态页

### 6.4 只在本地预览状态页

如果你只是想先看静态页长什么样，可以本地执行：

```bash
python scripts/build_status_site.py --output-dir site
```

生成结果：

- `site/index.html`
- `site/status.json`

### 6.5 如何持续自动同步

最推荐的方式不是让 GitHub 定时来“拉”你的本地状态，而是让你本地机器定时“推”：

- Windows：任务计划程序定时执行 `python scripts/publish_status_snapshot.py --owner Spphire --repo DeviceSentinel-AI`
- Linux / macOS：使用 `cron`

这样 GitHub Pages 展示的就是你本机当前真实状态，而不是远端仓库在无本地数据时生成的空快照。

### 6.6 如果要同步 GitHub Projects 看板

建议后续单独做一个自动化脚本：

- 当异常设备数 > 0 时自动创建 / 更新 Issue
- 或者调用 GitHub Projects v2 API 更新看板列和状态字段

状态页适合展示摘要，看板适合跟踪处理流转；两者最好分开。

## 7. 首次推送建议流程

1. 在 GitHub 网页端创建一个空仓库
2. 将本地仓库绑定为远程 `origin`
3. 推送 `main` 分支
4. 回到仓库网页配置 About 区和 Topics
5. 检查 README、`doc/` 和 `.github/` 模板展示是否正常

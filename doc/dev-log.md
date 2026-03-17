# 开发日志

这份文档面向 GitHub 协作阅读，记录最近一段时间的重要决策和里程碑。  
更完整的长历史仍以根目录 [`../DEVELOPMENT_HISTORY.md`](../DEVELOPMENT_HISTORY.md) 为准。

## 2026-03-17

### PC GUI 客户端与 Android APK 收口

- 个人 PC 客户端补成了真正面向 C 端的桌面程序：
  - 默认启动 GUI
  - 支持修改仪表盘 IP / 端口 / 路径 / 上报间隔
  - 支持本地缓存配置
  - 支持 `--headless` 无界面运行
- 修复了 GUI 端“改完上报间隔后重新开始仍沿用旧频率”的问题
- 修复了 Windows 上采样子进程导致黑色终端窗口频繁闪烁的问题
- 新增原生 Android 客户端工程 `android/mobile-client`
- 实测完成 `python scripts/build_mobile_android_apk.py`，已输出 debug APK

### 收工整理与明日计划

- 统一整理 `doc/current-status.md`、`doc/active-plan.md`、`doc/dev-log.md` 和根目录 `DEVELOPMENT_HISTORY.md`
- 清理 GitHub Projects 路线图中无意义的 milestone 卡片，并将当前阶段节点统一标记为 `Done`
- 将明日优先事项收敛为两条：
  - 个人 PC 客户端 release 形态完善，支持 Python 脚本和 EXE
  - 手机端客户端与 mobile device 模板

### 客户端 release 与手机端接入

- 为多个真实设备脚本抽出共享上报辅助层 `app/services/telemetry_client.py`
- 新增 `scripts/build_client_release.py` 和 `requirements-release.txt`
- 实测完成 `personal_pc_client.exe` 打包输出
- 新增 `mobile_device_real` 模板和 `scripts/mobile_device_client.py`
- 手机端客户端支持三种模式：
  - Android / Termux 实机采集
  - 手动指标覆写
  - `--simulate` 桌面演示模式

### GitHub Projects 协作文档同步

- 新增 `scripts/sync_github_projects.py`，可将 `current-status / active-plan / dev-log` 汇总后同步到 GitHub Projects v2
- 新增同步解析与 GraphQL 调用逻辑，当前以 Projects draft issue 作为同步目标
- 新增 `doc/github-projects-guide.md`，明确字段建议、映射规则与同步命令
- 新增 `--include-milestones` 模式，可将 `DEVELOPMENT_HISTORY.md` 中的阶段里程碑同步为 `Milestone · 第X阶段` 卡片

### 共享网关与后端管理

- 将真实设备接入从“每台设备单独配置 `host / port / path`”重构为“全局共享网关配置”
- 新增 `scripts/run_backend.py`，由独立 backend manager 托管共享 HTTP 遥测网关
- 设置面板移除设备级通讯参数，示例命令改为按当前共享网关配置自动生成
- 修复了设置修改后总是触发整个运行时重建的问题，避免仅改 Agent / 网关配置时清空模拟历史

### GitHub 状态发布

- 新增状态快照构建逻辑与静态页生成器
- 新增 `repository_dispatch -> GitHub Actions -> GitHub Pages` 的状态发布骨架
- 目标是发布“摘要和快照”，而不是把 GitHub 当成实时遥测仓库

## 2026-03-16

### 本地模型接入

- 在本机完成 `Ollama + qwen2.5:7b` 部署
- 页面新增 `local_ollama` 聊天后端
- 页面默认已切到本地 7B，可脱离外部 API 直接演示

### 聊天后端与 Tool / Skill 层

- 聊天后端收敛为统一适配层，支持 `local_rule / real_llm / local_ollama`
- 新增 Dashboard Tool 层，支持：
  - 总览统计查询
  - 单设备详情查询
  - 指标趋势查询
  - 异常原因与处置建议查询
- 新增 MPC 风格 Skill adapter，为后续真实 Skill 联调留出接口

### 个人 PC 指标增强

- 修复 Windows GPU 性能计数器低估本地大模型推理的问题
- 改为优先使用 `nvidia-smi` 获取 GPU 使用率
- 新增 `GPU 显存占用率` 指标

## 后续日志建议格式

后续每次更新建议尽量写清：

- 为什么改
- 改了哪一层
- 对协作开发者最重要的影响是什么

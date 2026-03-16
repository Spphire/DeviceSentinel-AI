# 开发历史记录

## 项目简述

项目名称：基于 MPC Skill 的电气设备状态监测 AI Agent 系统  
当前定位：学生级课程设计 / 毕业设计演示系统  
当前阶段：已完成模板驱动设备面板、模拟与真实设备混合接入、本地持久化配置、规则分析、本地聊天 Agent、真实模型适配层、本地 7B 模型部署与联调，以及 GitHub 协作文档与 Projects 看板整理

## 当前能力

- 支持模板驱动的设备类型加载，模板目录位于 [device_templates](device_templates)
- 支持的模板：
  - `sgcc_simulated`：SGCC 模拟设备
  - `personal_pc_real`：个人 PC 真实设备
  - `temp_humidity_simulated`：温湿度模拟设备
  - `temp_humidity_real`：温湿度真实设备
- Streamlit 主页面支持：
  - 设备总览
  - 单设备详情
  - 动态指标曲线
  - 聊天式 AI Agent
  - 设置弹窗
- 聊天区支持后端模式切换：
  - `local_rule`：本地规则式问答
  - `real_llm`：真实模型 + Tool 调用
  - `local_ollama`：本地 Ollama 模型回答
- 真实模型模式支持失败自动回退到本地规则
- 已整理模板感知的设备查询 Tool / Skill 接口，可供本地规则、真实模型和后续 MPC Skill 复用
- 已在本机成功部署 `Ollama + qwen2.5:7b`，可直接用于页面聊天区
- 设置支持本地保存，文件路径：
  - [storage/dashboard_settings.json](storage/dashboard_settings.json)
- 真实设备数据接入采用共享 HTTP 网关：
  - 默认接收地址 `http://127.0.0.1:10570/telemetry`
  - 多个真实设备共用同一个 `/telemetry` 入口，通过 `instance_id` 区分
- 已有真实设备客户端脚本：
  - [personal_pc_client.py](scripts/personal_pc_client.py)
  - [temp_humidity_client.py](scripts/temp_humidity_client.py)

## 当前架构

- 模板加载：`app/services/template_service.py`
- 设置存储：`app/services/settings_store.py`
- 混合设备运行时：`app/services/fleet_runtime.py`
- 规则分析：
  - SGCC 规则：`app/analysis/analyzer.py`
  - 模板感知分析：`app/analysis/template_analyzer.py`
- 报告生成：`app/agent/report_generator.py`
- 聊天后端适配：`app/agent/chat_agent.py`
- 设备查询 Tool：`app/agent/dashboard_tools.py`
- MPC Skill 适配：`app/mpc/dashboard_skill_adapter.py`
- 共享网关服务：`app/services/gateway_service.py`
- 后端管理主程序：`scripts/run_backend.py`
- 页面入口：`streamlit_app.py`

## 已完成开发历史

### 2026-03-16 第一阶段

- 从空目录搭建了项目基础结构
- 实现了 SGCC 模拟数据、阈值分析、MPC Skill 风格函数封装
- 实现了本地 AI 总结与 Streamlit 演示页面
- 补充了 MQTT 发布 / 订阅示例脚本

### 2026-03-16 第二阶段

- 将单次随机模拟升级为时序模拟引擎
- 支持 4 类 SGCC 画像：稳定型、偶发故障型、频发故障型、离线型
- 支持离线状态分析和离线报告文案

### 2026-03-16 第三阶段

- 调整主页面布局，隐藏画像与开发字段
- 设置入口改为顶部齿轮
- AI 总结改为缓存模式，默认不随页面自动刷新

### 2026-03-16 第四阶段

- 引入模板驱动设备体系，新增 `device_templates` 目录
- 支持模拟设备与真实设备混合配置
- 支持本地持久化设备清单和系统设置
- 支持动态指标数量与动态曲线面板
- 增加真实设备 HTTP 网关和客户端脚本骨架

### 2026-03-16 第五阶段

- 设置面板升级为弹窗模式，基础系统设置与开发者设置分层展示
- 设备列表支持通过 `+ 添加设备` 和红色 `删除` 按钮维护
- 移除手动“保存并应用设置”按钮，改为关闭设置面板后自动保存并应用
- 设备配置修改保持本地持久化，下次启动自动恢复
- 初始化本地 Git 仓库，便于后续提交版本历史和挂接远程仓库

### 2026-03-16 第六阶段

- 修正个人 PC 真实设备客户端的指标口径
- 将原“磁盘占用率”替换为更贴近任务管理器性能页的“磁盘活动率”
- 新增 `GPU 使用率` 指标采集与展示
- 个人 PC 模板更新为 `CPU / 内存 / 磁盘活动率 / GPU` 四项指标

### 2026-03-16 第七阶段

- 将分析时间窗口默认值统一调整为 `60`
- 修复设置弹窗中“开发者模式”开关与内容区偶发不同步的问题
- 强化设置弹窗状态同步，打开弹窗时会从当前已保存配置重新加载全部设置
- 个人 PC 四张指标曲线改为固定三列网格布局，避免最后一张图单独拉满整行

### 2026-03-16 第八阶段

- 新增 `doc/` 文档中心，统一整理项目正式文档
- 新增项目架构说明、已完成功能、部署说明、展示版开发历史、路线图
- 重写根目录 `README.md`，优化为更适合 GitHub 首页展示的入口页
- 新增 `.github/` Issue / PR 模板，便于后续利用 GitHub 网页端协作

### 2026-03-16 第九阶段

- 本地工作目录切换到 `DeviceSentinel-AI`，与 GitHub 仓库名保持一致
- 修正文档和页面提示中的旧项目目录引用
- 将新目录仓库远程 `origin` 指向 GitHub 仓库 `git@github.com:Spphire/DeviceSentinel-AI.git`

### 2026-03-16 第十阶段

- 将原“AI 智能总结”区域升级为聊天式 AI Agent 面板
- 新增本地 Agent 工具层，支持：
  - 全局设备总览问答
  - 异常 / 高风险 / 离线设备查询
  - 指定设备状态查询
  - 指标趋势说明
  - 告警原因与处置建议说明
- 新增聊天 Agent 单元测试，确保问答能力可回归验证

### 2026-03-16 第十一阶段

- 讨论并确认后续主线切换为“真实模型接入 + MPC Skill 工具化”
- 确认当前聊天式 Agent 只是第一版本地规则后端，后续将升级为：
  - `local_rule`：当前本地工具式回答
  - `real_llm`：真实大模型回答
  - `mpc_skill`：模型通过 Skill 查询设备状态
- 确认后续推荐开发顺序：
  1. 先做模型适配层
  2. 再做 MPC Skill 工具接口
  3. 最后接真实模型与页面聊天区联动
- 说明当前实际工作目录已切换到 `C:\Users\Apricity\Desktop\DeviceSentinel-AI`
- 说明旧目录 `C:\Users\Apricity\Desktop\SGCC_ElecDevice_Monitor_AI_MPC` 只是遗留副本，后续应以新目录为准

### 2026-03-16 第十二阶段

- 将聊天后端升级为统一适配层，支持 `local_rule / real_llm` 两种模式
- 新增模板感知设备查询 Tool 层，支持：
  - 总览统计查询
  - 单设备详情查询
  - 指标趋势查询
  - 异常原因与处置建议查询
- 新增 MPC 风格的 Dashboard Skill 适配器，便于后续继续挂接外部 Skill 调用链
- 设置面板新增 Agent 配置项，可直接切换对话后端、模型名和失败回退策略
- 真实模型模式改为从环境变量读取 `OPENAI_API_KEY`，避免将密钥写入本地设置文件
- 为新聊天后端、Tool 层和设置持久化补充测试，当前 `python -m pytest` 已通过

### 2026-03-16 第十三阶段

- 在 Windows 本机安装 `Ollama`
- 拉取并验证本地模型 `qwen2.5:7b`
- 将聊天后端新增为 `local_ollama` 模式，支持页面内直接切换到本地 7B
- 当前本地配置已默认切换为 `local_ollama + qwen2.5:7b`
- 本地 Ollama 默认服务地址为 `http://127.0.0.1:11434`

### 2026-03-17 第十四阶段

- 将真实设备接入从“设备级通讯配置”重构为“全局共享网关配置”
- 设置文件新增顶层 `gateway` 配置，并兼容迁移旧版设备级 `communication` 字段
- 设置面板移除每台真实设备单独填写 `host / port / path` 的方式
- 新增独立后端管理主程序 `scripts/run_backend.py`
- 后端 manager 负责托管共享 HTTP 遥测网关，并在全局网关配置变化后自动重载
- 页面里的真实设备客户端示例命令，改为基于当前共享网关配置和设备 `instance_id` 自动生成
- 修复设置保存后总是重建运行时的问题，避免仅修改 Agent / 网关配置时清空模拟历史
- 新增状态摘要导出器、repository_dispatch 推送脚本和 GitHub Pages 发布工作流

### 2026-03-17 第十五阶段

- 新增面向 GitHub 协作阅读的文档入口：
  - `doc/current-status.md`
  - `doc/active-plan.md`
  - `doc/dev-log.md`
- 调整 `README.md` 和 `doc/README.md`，让协作 coder 能快速定位“当前状态 / 当前计划 / 最近开发日志”
- 更新 GitHub 发布指南，明确 GitHub 更适合展示摘要、计划和协作上下文，而不是承载原始实时日志

### 2026-03-17 第十六阶段

- 新增 `scripts/sync_github_projects.py`，用于把协作文档同步到 GitHub Projects v2
- 新增 `app/services/github_projects_sync.py`，负责解析 `current-status / active-plan / dev-log` 并调用 GraphQL API 创建或更新 draft issue
- 新增 `doc/github-projects-guide.md`，说明字段建议、文档映射规则和同步命令
- 当前同步策略为：
  - `doc/current-status.md + doc/dev-log.md` -> `Current project context` 上下文卡
  - `doc/active-plan.md` -> Ready / Backlog / Done 等计划卡

### 2026-03-17 第十七阶段

- 为 `scripts/sync_github_projects.py` 新增 `--include-milestones` 模式
- 可将根目录 `DEVELOPMENT_HISTORY.md` 中的阶段历史同步成 `Milestone · 第X阶段` 卡片
- 里程碑卡默认映射到 Projects 的 `Done` 列，适合给面试官展示项目演进过程

### 2026-03-17 第十八阶段

- 收工前统一整理 `doc/current-status.md`、`doc/active-plan.md`、`doc/dev-log.md` 和根目录 `DEVELOPMENT_HISTORY.md`
- 清理 GitHub Projects 路线图中无意义的 milestone 卡片
- 将当前阶段节点统一标记为 `Done`
- 将下一轮优先事项收敛为：
  - 个人 PC 客户端 release 形态完善（Python / EXE）
  - 手机端客户端与 mobile device 模板

### 2026-03-16 当前待继续工作（含优先级）

- `P2` 完善个人 PC 客户端 release 形态，支持 Python 脚本与 EXE 两种交付方式
- `P2` 新增手机端真实设备模板与客户端，形成第二类移动端真实设备
- `P2` 真正联通可用的真实模型账号与 API Key，验证页面里的 `real_llm` 模式
- `P2` 让聊天主流程进一步统一走 `dashboard_skill_adapter`，收敛 Tool / Skill 两套入口，便于后续真正挂接外部 MPC Skill
- `P2` 进一步细化 backend manager，例如补充 PID 文件、健康检查和启动脚本，减少手动运维操作
- `P2` 评估是否为真实设备接入增加 `MQTT` 模式，与当前 `HTTP JSON push` 并存；重点比较单机演示复杂度、多设备扩展性、跨主机部署和断线重连体验
- `P2` 继续优化本地 Ollama / 真实模型提示词，减少无效调用
- `P2` 继续扩展 Dashboard Tool / MPC Skill，补充更多筛选和聚合查询能力
- `P3` 继续优化答辩版页面视觉与数据展示
- `P3` 视情况推进数据持久化升级

## 当前运行方式

启动页面：

```bash
streamlit run streamlit_app.py --server.port 7787
```

如需启用真实模型模式，请先设置环境变量：

```bash
set OPENAI_API_KEY=<你的 API Key>
```

启动共享后端管理主程序：

```bash
python scripts/run_backend.py
```

发送个人 PC 指标：

```bash
python scripts/personal_pc_client.py --instance-id <设备实例ID> --gateway-host <仪表盘IP> --gateway-port 10570 --gateway-path /telemetry
```

发送温湿度指标：

```bash
python scripts/temp_humidity_client.py --instance-id <设备实例ID> --gateway-host <仪表盘IP> --gateway-port 10570 --gateway-path /telemetry --simulate
```

运行测试：

```bash
python -m pytest
```

## 新开会话时推荐提供的背景

可将下面这段作为简版上下文发给新的 Codex 会话：

```text
项目现在的实际工作目录是 C:\Users\Apricity\Desktop\DeviceSentinel-AI，不再以旧目录 SGCC_ElecDevice_Monitor_AI_MPC 为准。
项目是“基于 MPC Skill 的电气设备状态监测 AI Agent 系统”，当前已经做成模板驱动版本，并且聊天区已经支持 local_rule / real_llm / local_ollama 三种后端。
根目录 DEVELOPMENT_HISTORY.md 记录了当前架构、开发历史和下一步计划。
页面入口是 streamlit_app.py，模板目录是 device_templates，设置持久化在 storage/dashboard_settings.json。
当前重点是继续完善个人 PC 客户端 release 交付形态，并新增手机端真实设备模板与客户端。
本机现已部署 Ollama 和 qwen2.5:7b，页面聊天区可切到 local_ollama 模式直接使用。
```

## 重开 Codex 时的提醒

- 请直接打开新目录：`C:\Users\Apricity\Desktop\DeviceSentinel-AI`
- 不要再以旧目录 `C:\Users\Apricity\Desktop\SGCC_ElecDevice_Monitor_AI_MPC` 作为工作区
- 当前 GitHub 仓库为：`git@github.com:Spphire/DeviceSentinel-AI.git`
- 当前最新已推送提交：
  - `b4e688a` `Add milestone sync for GitHub Projects`
  - `94453a3` `Add GitHub Projects sync for collaboration docs`
  - `39ebfb4` `Add collaboration status and planning docs`

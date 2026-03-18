# 开发日志

这份文档面向 GitHub 协作阅读，记录最近一段时间的重要决策和里程碑。  
更完整的长历史仍以根目录 [`../DEVELOPMENT_HISTORY.md`](../DEVELOPMENT_HISTORY.md) 为准。

## 2026-03-19

### 电力知识库增强 + 知识型模拟场景

- 新增 `knowledge_base/power_operation_knowledge.json`，沉淀第一版公开电力运维知识条目
- 新增 `app/services/power_knowledge_service.py`，按模板、故障标签、分析结果和指标条件匹配知识依据
- `template_analyzer.py` 现可在结构化分析结果中附带：
  - `knowledge_references`
  - `recommended_actions`
- `report_generator.py` 现会输出“知识增强处置建议”和“知识依据”
- 聊天本地规则 / Tool / Skill 输出现可引用知识条目标题和来源
- 页面单设备详情新增“AI 运维分析卡”和“知识依据与处置建议”面板

### 更贴近配电运维的模拟模板

- 新增 `switchgear_simulated`：
  - 触头温度
  - 柜内温度
  - 负荷电流
- 新增 `distribution_transformer_simulated`：
  - 末端电压
  - 运行电流
  - 负载率
  - 三相不平衡率
- 当前默认演示设备切成了：
  - `10kV 开关柜 A`
  - `台区配变终端 A`
  - `馈线终端 B`
  - `个人 PC`
  - `手机端`
- 重点是让模拟场景能和知识库直接对得上，而不是只靠泛化阈值告警

### 运行与验证

- 修复了 `storage/dashboard_settings.json` 的语法错误，并重启页面与 backend manager
- 当前 `python -m pytest` 全量通过，结果 `76 passed`
- 已验证：
  - 开关柜接头过热场景可命中知识条目
  - 配变低电压 / 三相不平衡场景可命中知识条目
  - 本地规则聊天会给出知识依据和优先处置步骤
  - 页面与共享网关均可正常启动

## 2026-03-17

### PC 客户端托盘 / 开机自启动 + backend manager 包装脚本

- 个人 PC GUI 客户端新增托盘最小化、`--start-minimized` 和“开机自启动”开关
- 开机自启动通过 Windows Startup 目录下的启动脚本实现，不依赖额外系统配置
- 当前环境已补装 `pystray`，本机托盘能力可直接使用
- 新增 `scripts/manage_backend.py`，支持一键 `start / stop / restart / status`
- 已重打个人 PC release，新的脚本包和 EXE 已包含托盘/自启动相关更新
- 为 autostart helper、backend wrapper 和 release 启动器补充测试后，相关测试通过

### 聊天主流程 Skill 收敛 + backend smoke test

- `local_rule` 原来还在直接读 `context` 做本地判断，这一轮已经统一改为通过 `dashboard_skill_adapter` 调技能再整形回答
- `real_llm` 模式的工具定义和工具执行也已经切到同一个 Skill adapter，减少 Tool / Skill 两套入口继续分叉
- 新增 `scripts/check_agent_backends.py`，可直接在命令行 smoke test `local_rule / real_llm / local_ollama`
- 当前本机 `openai` 依赖已安装，但没有可用 `OPENAI_API_KEY`，因此 `real_llm` 还只能验证到“配置缺失时的错误路径”

### PC 客户端自动重试与目标网关预览

- 个人 PC GUI 客户端新增“目标网关”显示，能直接看到当前要连的上报地址
- GUI 端发送失败后不再立刻停掉线程，而是进入自动重试状态并显示失败次数 / 重试延迟
- headless 模式也补上了自动重试，便于长时间后台运行
- 为这部分补充测试后，聊天 / adapter / PC client 相关测试已通过

### backend manager 健康检查收口

- 共享 HTTP 网关补上固定 `/health` 探针接口
- `scripts/run_backend.py` 现在会主动探测网关健康状态，并在失败时尝试自动重启
- `gateway_manager_status.json` 新增健康结果、PID 存活状态和遗留状态文件判定
- 设置面板与状态快照页都开始展示“运行中 / 健康 / 遗留状态”这类更工程化的信息
- 补充网关与状态页测试后，全量测试通过 `61 passed`

### 文档收口与优化路线补充

- 重新整理文档中心导航，补上 `optimization-qa.md`
- 新增一份“自问自答式优化清单”，把产品、架构、AI、客户端、答辩展示等方向的判断依据沉淀下来
- 目标是不让后续开发只靠即时讨论推进，而是把“为什么下一步做这些”也写进仓库

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

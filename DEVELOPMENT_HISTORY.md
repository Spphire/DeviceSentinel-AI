# 开发历史记录

## 项目简述

项目名称：基于 MPC Skill 的电气设备状态监测 AI Agent 系统  
当前定位：学生级课程设计 / 毕业设计演示系统  
当前阶段：已完成模板驱动设备面板、模拟与真实设备混合接入、本地持久化配置、规则分析与本地 AI 总结

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
  - 本地 AI 总结
  - 设置弹窗
- 设置支持本地保存，文件路径：
  - [storage/dashboard_settings.json](storage/dashboard_settings.json)
- 真实设备数据接入网关：
  - HTTP 接收地址默认 `http://127.0.0.1:10570/telemetry`
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

### 2026-03-16 当前待继续工作

- 设置弹窗继续细化体验
- 将本地聊天式 Agent 升级为真实大模型驱动
- 接入真实大模型和 MPC Skill
- 让模型从用户提问中提取设备关键词、查询当前设备上下文并回答

## 当前运行方式

启动页面：

```bash
streamlit run streamlit_app.py --server.port 7787
```

启动真实设备网关：

```bash
python scripts/run_device_gateway.py --host 127.0.0.1 --port 10570 --path /telemetry
```

发送个人 PC 指标：

```bash
python scripts/personal_pc_client.py --instance-id <设备实例ID> --host 127.0.0.1 --port 10570 --path /telemetry
```

发送温湿度指标：

```bash
python scripts/temp_humidity_client.py --instance-id <设备实例ID> --host 127.0.0.1 --port 10570 --path /telemetry --simulate
```

运行测试：

```bash
python -m pytest
```

## 新开会话时推荐提供的背景

可将下面这段作为简版上下文发给新的 Codex 会话：

```text
项目是“基于 MPC Skill 的电气设备状态监测 AI Agent 系统”，当前已经做成模板驱动版本。
根目录 DEVELOPMENT_HISTORY.md 记录了当前架构、开发历史和下一步计划。
页面入口是 streamlit_app.py，模板目录是 device_templates，设置持久化在 storage/dashboard_settings.json。
当前重点是继续细化设置弹窗体验，并准备把 AI 智能总结升级成聊天框，后续接真实大模型和 MPC Skill。
```

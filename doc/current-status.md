# 当前状态

最后更新：2026-03-17

## 1. 当前阶段

项目当前已经完成到“第二十四阶段”：

- 模板驱动的混合设备监测面板已稳定可用
- 聊天 Agent 已支持 `local_rule / real_llm / local_ollama`
- 本机已完成 `Ollama + qwen2.5:7b` 联调
- 真实设备接入已收敛为“共享 HTTP 网关 + backend manager”
- backend manager 已补上健康检查、PID 状态识别和遗留状态文件自检
- 聊天主流程已收敛到 `dashboard_skill_adapter`，本地规则与真实模型 Tool 调用共用同一套 Skill registry
- 个人 PC 客户端已支持 GUI / headless、Windows EXE、本地配置缓存、托盘与开机自启动
- 个人 PC 客户端已补上自动重试、目标网关预览和更稳定的连接状态提示
- 手机端真实设备模板与脚本客户端已接入当前链路，Android APK 客户端工程已落地并可本机构建
- GitHub 已补上状态摘要发布工作流，可自动发布静态状态页
- GitHub Projects 文档同步脚本已落地，可把当前计划、上下文和阶段里程碑同步到 Projects v2 看板
- GitHub Projects 当前已按收工状态整理，既有阶段节点已统一标记为 `Done`
- 已补充自问自答式优化文档，便于后续继续按产品 / 架构 / 展示价值排序推进
- backend manager 已补上一键 `start / stop / restart / status` 管理脚本

## 2. 当前默认运行方式

页面入口：

```bash
streamlit run streamlit_app.py --server.port 7787
```

共享后端管理主程序：

```bash
python scripts/manage_backend.py start
```

聊天后端 smoke test：

```bash
python scripts/check_agent_backends.py --backend local_rule --message "这台设备现在怎么样？"
```

个人 PC 客户端：

```bash
python scripts/personal_pc_client_app.py --instance-id personal_pc_real-b6553a2f --gateway-host 127.0.0.1 --gateway-port 10570 --gateway-path /telemetry
```

移动端 APK 构建入口：

```bash
python scripts/build_mobile_android_apk.py
```

## 3. 当前已验证链路

- 模拟设备总览、单设备详情、动态曲线
- 真实个人 PC 指标采集与上报
- 个人 PC GUI / headless 客户端配置缓存与重启生效
- 共享网关配置修改后由 backend manager 自动重载
- backend manager 健康探针、状态文件写入与页面可见性
- 聊天主流程 Skill adapter 收敛
- `check_agent_backends.py` 命令行 smoke test
- `manage_backend.py` 一键启动 / 停止 / 状态查看
- 聊天面板本地规则问答
- 聊天面板本地 `Ollama` 问答
- 手机端客户端模拟上报
- Android 手机客户端 debug APK 本机构建
- GitHub 状态摘要静态页本地构建
- GitHub Projects 文档同步与看板更新
- GitHub Projects 路线图清理与 `Done` 收口
- 个人 PC Windows EXE 打包与输出目录生成

## 4. 当前关键入口文件

| 类型 | 路径 | 说明 |
| --- | --- | --- |
| 页面入口 | `streamlit_app.py` | Streamlit 主页面与设置弹窗 |
| 运行时 | `app/services/fleet_runtime.py` | 混合设备运行逻辑 |
| 设置存储 | `app/services/settings_store.py` | 页面设置与网关配置持久化 |
| 共享网关 | `app/services/gateway_service.py` | 遥测网关与 manager 状态文件 |
| 后端 manager | `scripts/run_backend.py` | 托管共享网关并按配置重载 |
| manager 包装脚本 | `scripts/manage_backend.py` | 一键 `start / stop / restart / status` |
| 聊天后端 | `app/agent/chat_agent.py` | `local_rule / real_llm / local_ollama` |
| Tool 层 | `app/agent/dashboard_tools.py` | 设备查询与趋势分析工具 |
| MPC Skill 适配 | `app/mpc/dashboard_skill_adapter.py` | Dashboard Tool 的 Skill 风格包装 |
| 聊天 smoke test | `scripts/check_agent_backends.py` | 快速验证 `local_rule / real_llm / local_ollama` |
| 客户端共享层 | `app/services/telemetry_client.py` | 真实设备脚本共用的上报与参数解析 |
| PC GUI 客户端 | `scripts/personal_pc_client_app.py` | 桌面 GUI、曲线展示与 headless 入口 |
| Android 客户端工程 | `android/mobile-client` | 手机 APK 图形端与 Gradle wrapper |
| Android APK 构建 | `scripts/build_mobile_android_apk.py` | 生成并复制 debug APK 到 `dist/clients/` |
| 状态发布 | `scripts/publish_status_snapshot.py` | 向 GitHub 发送状态摘要 dispatch |
| Projects 同步 | `scripts/sync_github_projects.py` | 将协作文档同步到 GitHub Projects v2 |
| release 构建 | `scripts/build_client_release.py` | 输出脚本版与 Windows GUI EXE 客户端包 |

## 5. 当前默认配置

- 对话后端默认：`local_ollama`
- 本地模型默认：`qwen2.5:7b`
- 共享网关默认：`127.0.0.1:10570/telemetry`
- 真实设备区分方式：请求体中的 `instance_id`
- 个人 PC 指标：`CPU / 内存 / 磁盘活动率 / GPU / GPU 显存占用率`
- 手机端指标：`电量 / 电池温度 / 内存使用率 / 存储使用率`

## 6. 当前协作重点

当前更适合继续推进的是：

1. 真实模型模式真正联通可用账号并验证稳定性
2. 继续收敛 Android 真机联调与后台上报稳定性
3. 继续完善 PC 客户端，例如版本提示和本地日志入口
4. 在现有共享网关基础上评估 MQTT 补充接入

## 7. 当前不建议优先动的部分

- 不建议再把真实设备接入改回“设备级 host / port / path”
- 不建议让 `streamlit_app.py` 直接托管长期后台进程
- 不建议把 GitHub Pages 状态页当作实时监控主页面

## 8. 协作更新约定

后续 coder 每次完成一轮实质性改动后，建议同步更新：

- `doc/current-status.md`：只保留当前状态
- `doc/active-plan.md`：更新近期优先事项
- `doc/dev-log.md`：补一条简洁开发记录
- 根目录 `DEVELOPMENT_HISTORY.md`：补完整上下文历史

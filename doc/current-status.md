# 当前状态

最后更新：2026-03-17

## 1. 当前阶段

项目当前已经完成到“第十四阶段”：

- 模板驱动的混合设备监测面板已稳定可用
- 聊天 Agent 已支持 `local_rule / real_llm / local_ollama`
- 本机已完成 `Ollama + qwen2.5:7b` 联调
- 真实设备接入已收敛为“共享 HTTP 网关 + backend manager”
- GitHub 已补上状态摘要发布工作流，可自动发布静态状态页

## 2. 当前默认运行方式

页面入口：

```bash
streamlit run streamlit_app.py --server.port 7787
```

共享后端管理主程序：

```bash
python scripts/run_backend.py
```

个人 PC 客户端：

```bash
python scripts/personal_pc_client.py --instance-id personal_pc_real-b6553a2f --gateway-host 127.0.0.1 --gateway-port 10570 --gateway-path /telemetry
```

## 3. 当前已验证链路

- 模拟设备总览、单设备详情、动态曲线
- 真实个人 PC 指标采集与上报
- 共享网关配置修改后由 backend manager 自动重载
- 聊天面板本地规则问答
- 聊天面板本地 `Ollama` 问答
- GitHub 状态摘要静态页本地构建

## 4. 当前关键入口文件

| 类型 | 路径 | 说明 |
| --- | --- | --- |
| 页面入口 | `streamlit_app.py` | Streamlit 主页面与设置弹窗 |
| 运行时 | `app/services/fleet_runtime.py` | 混合设备运行逻辑 |
| 设置存储 | `app/services/settings_store.py` | 页面设置与网关配置持久化 |
| 共享网关 | `app/services/gateway_service.py` | 遥测网关与 manager 状态文件 |
| 后端 manager | `scripts/run_backend.py` | 托管共享网关并按配置重载 |
| 聊天后端 | `app/agent/chat_agent.py` | `local_rule / real_llm / local_ollama` |
| Tool 层 | `app/agent/dashboard_tools.py` | 设备查询与趋势分析工具 |
| MPC Skill 适配 | `app/mpc/dashboard_skill_adapter.py` | Dashboard Tool 的 Skill 风格包装 |
| 状态发布 | `scripts/publish_status_snapshot.py` | 向 GitHub 发送状态摘要 dispatch |

## 5. 当前默认配置

- 对话后端默认：`local_ollama`
- 本地模型默认：`qwen2.5:7b`
- 共享网关默认：`127.0.0.1:10570/telemetry`
- 真实设备区分方式：请求体中的 `instance_id`
- 个人 PC 指标：`CPU / 内存 / 磁盘活动率 / GPU / GPU 显存占用率`

## 6. 当前协作重点

当前更适合继续推进的是：

1. 真实模型模式真正联通可用账号并验证稳定性
2. 继续收敛 Tool / Skill 两套入口，让聊天主流程统一走 Skill adapter
3. 评估 MQTT 作为共享 HTTP 网关的补充方案
4. 继续完善 backend manager，例如 PID/健康检查/启动脚本

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

# 部署与使用说明

## 1. 环境要求

- Windows
- Python 3.11
- PowerShell 7 或系统自带 PowerShell

## 2. 安装依赖

```bash
pip install -r requirements.txt
```

## 3. 启动页面

```bash
streamlit run streamlit_app.py --server.port 7787
```

打开浏览器访问：

```text
http://localhost:7787
```

## 4. 启动共享后端管理主程序

```bash
python scripts/run_backend.py
```

默认共享接收地址：

```text
http://127.0.0.1:10570/telemetry
```

说明：

- 该 manager 会负责托管共享 HTTP 遥测网关
- 页面中的全局网关配置保存后，manager 会自动按新配置重载
- 所有 HTTP 真实设备共用同一个 `/telemetry` 入口，靠 `instance_id` 区分

## 5. 启动个人 PC 客户端

先在页面的开发者模式中添加一个“个人 PC（真实设备）”，记下它的 `设备实例 ID`，然后执行：

```bash
python scripts/personal_pc_client.py --instance-id <设备实例ID> --gateway-host <仪表盘IP> --gateway-port 10570 --gateway-path /telemetry
```

如果只发送一次数据用于测试：

```bash
python scripts/personal_pc_client.py --instance-id <设备实例ID> --gateway-host <仪表盘IP> --gateway-port 10570 --gateway-path /telemetry --once
```

## 6. 启动温湿度客户端

```bash
python scripts/temp_humidity_client.py --instance-id <设备实例ID> --gateway-host <仪表盘IP> --gateway-port 10570 --gateway-path /telemetry --simulate
```

## 7. 本地设置文件

页面配置会保存到：

```text
storage/dashboard_settings.json
```

真实设备事件会写入：

```text
storage/real_device_events.jsonl
```

## 8. 运行测试

```bash
python -m pytest
```

## 9. GitHub 展示建议

将项目推到 GitHub 后，建议这样配置仓库首页：

1. 使用根目录 `README.md` 作为首页说明。
2. 使用 `doc/` 目录作为正式文档导航。
3. 在仓库 About 区补充项目描述与 Topics。
4. 将 `docs/mpc_skill_guide.md` 保留为专项集成文档。
5. 使用 `.github/ISSUE_TEMPLATE` 和 `pull_request_template.md` 统一协作记录。

## 10. 常见问题

### 页面打不开

- 先确认 `7787` 端口没有被占用
- 再确认 Streamlit 进程已成功启动

### 真实设备没有数据

- 先确认 `python scripts/run_backend.py` 是否已运行
- 再确认客户端 `instance_id` 与页面配置一致
- 再检查客户端上报地址是否指向仪表盘所在机器的网关地址，例如 `192.168.1.10:10570/telemetry`

### 个人 PC 数值和任务管理器有差异

- 当前版本已经尽量贴近任务管理器性能页口径
- 仍可能因为采样时间窗不同而出现少量偏差
- 这是实时监控面板中正常的采样差异

# 部署与使用说明

## 1. 环境要求

- Windows
- Python 3.11
- PowerShell 7 或系统自带 PowerShell
- 如需构建 Android APK：Java 17+ 与 Android SDK

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

## 5. 启动个人 PC 客户端（GUI / headless）

先在页面的开发者模式中添加一个“个人 PC（真实设备）”，记下它的 `设备实例 ID`，然后执行：

```bash
python scripts/personal_pc_client_app.py --instance-id <设备实例ID> --gateway-host <仪表盘IP> --gateway-port 10570 --gateway-path /telemetry
```

说明：

- 默认会打开桌面 GUI，可直接填写仪表盘 IP / 端口 / 路径
- 当前值会自动缓存到 `%APPDATA%\DeviceSentinel\personal_pc_client_app.json`
- 再次点击“开始上报”会按最新参数重启后台线程

如果只发送一次数据用于测试，或希望后台无人值守运行：

```bash
python scripts/personal_pc_client_app.py --instance-id <设备实例ID> --gateway-host <仪表盘IP> --gateway-port 10570 --gateway-path /telemetry --headless --once
```

## 6. 启动温湿度客户端

```bash
python scripts/temp_humidity_client.py --instance-id <设备实例ID> --gateway-host <仪表盘IP> --gateway-port 10570 --gateway-path /telemetry --simulate
```

## 7. 启动手机端脚本客户端

如果是在 Android / Termux 上运行，可直接执行：

```bash
python scripts/mobile_device_client.py --instance-id <设备实例ID> --gateway-host <仪表盘IP> --gateway-port 10570 --gateway-path /telemetry
```

如果先在桌面环境演示手机设备，可使用模拟模式：

```bash
python scripts/mobile_device_client.py --instance-id <设备实例ID> --gateway-host <仪表盘IP> --gateway-port 10570 --gateway-path /telemetry --simulate
```

也支持手动覆写指标值：

```bash
python scripts/mobile_device_client.py --instance-id <设备实例ID> --battery-level 15 --battery-temperature 41 --memory-usage 82 --storage-usage 76 --gateway-host <仪表盘IP>
```

## 8. 构建客户端 release

安装打包依赖：

```bash
pip install -r requirements-release.txt
```

构建个人 PC 客户端脚本版 + Windows EXE：

```bash
python scripts/build_client_release.py --target personal_pc --format both
```

构建手机端客户端脚本版：

```bash
python scripts/build_client_release.py --target mobile_device --format script
```

构建手机端 Android APK：

```bash
python scripts/build_mobile_android_apk.py
```

如果手机已打开 USB 调试，也可以直接安装 debug APK：

```bash
adb install -r dist/clients/mobile_android/device_sentinel_mobile_client-debug.apk
```

默认输出目录：

```text
dist/clients/
```

## 9. 本地设置文件

页面配置会保存到：

```text
storage/dashboard_settings.json
```

真实设备事件会写入：

```text
storage/real_device_events.jsonl
```

个人 PC GUI 客户端缓存配置位于：

```text
%APPDATA%\DeviceSentinel\personal_pc_client_app.json
```

## 10. 运行测试

```bash
python -m pytest
```

## 11. GitHub 展示建议

将项目推到 GitHub 后，建议这样配置仓库首页：

1. 使用根目录 `README.md` 作为首页说明。
2. 使用 `doc/` 目录作为正式文档导航。
3. 在仓库 About 区补充项目描述与 Topics。
4. 将 `docs/mpc_skill_guide.md` 保留为专项集成文档。
5. 使用 `.github/ISSUE_TEMPLATE` 和 `pull_request_template.md` 统一协作记录。

## 12. 常见问题

### 页面打不开

- 先确认 `7787` 端口没有被占用
- 再确认 Streamlit 进程已成功启动

### 真实设备没有数据

- 先确认 `python scripts/run_backend.py` 是否已运行
- 再确认客户端 `instance_id` 与页面配置一致
- 再检查客户端上报地址是否指向仪表盘所在机器的网关地址，例如 `192.168.1.10:10570/telemetry`

### 手机端客户端无法读取真实指标

- Android 真机建议在 `Termux` 中运行
- 默认真实模式会尝试调用 `termux-battery-status`
- 如果当前环境不是安卓手机，可先追加 `--simulate` 进行演示

### EXE 没有生成

- 先确认已经执行 `pip install -r requirements-release.txt`
- 再确认 `PyInstaller` 已安装成功
- 也可以先使用 `--format script` 输出脚本版 release

### 手机 APK 没有生成

- 先确认本机已安装 Android SDK 和 Java
- 再确认 `python scripts/build_mobile_android_apk.py` 执行时没有被代理或网络问题拦住 Gradle 依赖下载
- 如果是第一次构建，Gradle 会自动下载依赖，耗时会明显更长

### 个人 PC 数值和任务管理器有差异

- 当前版本已经尽量贴近任务管理器性能页口径
- 仍可能因为采样时间窗不同而出现少量偏差
- 这是实时监控面板中正常的采样差异

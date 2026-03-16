# 百炼 MPC Skill 对接指引

本项目已将核心分析函数封装为 `analyze_electrical_device_status`，可直接作为百炼 MPC Skill 的函数模板。

## 1. 建议的 Skill 函数定义

函数名称：

```json
{
  "name": "analyze_electrical_device_status",
  "description": "分析低压电气设备运行状态，返回异常类型、风险等级和运维建议。",
  "parameters": {
    "type": "object",
    "properties": {
      "device_id": { "type": "string", "description": "设备编号" },
      "temperature": { "type": "number", "description": "设备温度，单位摄氏度" },
      "voltage": { "type": "number", "description": "设备电压，单位伏特" },
      "current": { "type": "number", "description": "设备电流，单位安培" },
      "timestamp": { "type": "string", "description": "采集时间，ISO 8601 格式" }
    },
    "required": ["device_id", "temperature", "voltage", "current"]
  }
}
```

## 2. 建议出参结构

```json
{
  "device_id": "SGCC-LV-001",
  "status": "critical",
  "risk_level": "high",
  "issues": [
    {
      "category": "temperature",
      "severity": "high",
      "message": "设备温度达到 75.0℃，超过 60.0℃ 阈值，判定为过温风险。",
      "suggestion": "建议立即安排现场测温复核，检查母排连接点、柜内散热和负荷情况。",
      "standard_reference": "DL/T 448-2016"
    }
  ],
  "metrics": {
    "temperature": 75.0,
    "voltage": 188.0,
    "current": 128.0
  },
  "summary": "检测到设备存在异常运行特征，建议结合现场巡视尽快复核。"
}
```

## 3. Python 侧绑定函数

项目中的本地绑定入口：

- `app.analysis.analyzer.analyze_device_status_for_mpc`
- `app.mpc.skill_adapter.invoke_local_skill`

如果后续改为 HTTP 服务形式，可将上述函数封装为接口：

- `POST /api/analyze`
- 请求体为设备数据 JSON
- 响应体为分析结果 JSON

## 4. Agent 提示词建议

建议模型在收到函数返回结果后，按以下要求生成总结：

1. 使用“运行状态、异常类型、风险等级、处理建议、规范依据”五段式输出
2. 语气保持运维分析风格，避免口语化
3. 明确指出是否需要现场复核
4. 引用 `DL/T 448-2016`

## 5. 当前实现边界

- 已实现本地 Skill 风格调用
- 已实现标准化入参 / 出参
- 未绑定真实百炼控制台配置
- 未接入真实阿里云 IoT 设备消息订阅

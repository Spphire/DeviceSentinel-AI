# DeviceSentinel Mobile Android Client

这个目录下是移动端 APK 客户端工程。

当前能力：

- 填写仪表盘 IP / 端口 / 路径
- 保存本机配置
- 采集手机电量、电池温度、内存使用率、存储使用率
- 在 App 内展示四条资源曲线
- 按设定间隔持续向 DeviceSentinel 共享网关上报

推荐构建方式：

```bash
python scripts/build_mobile_android_apk.py
```

如果要直接使用 Gradle：

```bash
cd android/mobile-client
gradlew.bat assembleDebug
```

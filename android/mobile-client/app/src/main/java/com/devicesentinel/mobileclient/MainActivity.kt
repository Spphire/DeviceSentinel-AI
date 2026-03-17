package com.devicesentinel.mobileclient

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.StatFs
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

private const val PREFS_NAME = "device_sentinel_mobile_client"
private const val PREF_INSTANCE_ID = "instance_id"
private const val PREF_GATEWAY_HOST = "gateway_host"
private const val PREF_GATEWAY_PORT = "gateway_port"
private const val PREF_GATEWAY_PATH = "gateway_path"
private const val PREF_INTERVAL_SECONDS = "interval_seconds"
private const val MAX_HISTORY_POINTS = 48

data class MobileClientConfig(
    val instanceId: String,
    val gatewayHost: String,
    val gatewayPort: Int,
    val gatewayPath: String,
    val intervalSeconds: Int,
)

data class MobileMetrics(
    val batteryLevel: Float,
    val batteryTemperature: Float,
    val memoryUsage: Float,
    val storageUsage: Float,
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = lightColorScheme(
                    primary = Color(0xFF0F766E),
                    secondary = Color(0xFFE07A1F),
                    tertiary = Color(0xFF1D4ED8),
                )
            ) {
                Surface(modifier = Modifier.fillMaxSize(), color = Color(0xFFF5F7FB)) {
                    MobileClientApp()
                }
            }
        }
    }
}

@Composable
private fun MobileClientApp() {
    val context = LocalContext.current
    val initialConfig = remember { loadConfig(context) }
    val batteryHistory = remember { mutableStateListOf<Float>() }
    val temperatureHistory = remember { mutableStateListOf<Float>() }
    val memoryHistory = remember { mutableStateListOf<Float>() }
    val storageHistory = remember { mutableStateListOf<Float>() }

    var instanceIdText by remember { mutableStateOf(initialConfig.instanceId) }
    var gatewayHostText by remember { mutableStateOf(initialConfig.gatewayHost) }
    var gatewayPortText by remember { mutableStateOf(initialConfig.gatewayPort.toString()) }
    var gatewayPathText by remember { mutableStateOf(initialConfig.gatewayPath) }
    var intervalText by remember { mutableStateOf(initialConfig.intervalSeconds.toString()) }
    var activeConfig by remember { mutableStateOf<MobileClientConfig?>(null) }
    var isRunning by remember { mutableStateOf(false) }
    var statusText by remember { mutableStateOf("待启动") }
    var lastPushText by remember { mutableStateOf("尚未发送") }
    var responseText by remember { mutableStateOf("等待首次上报") }
    var latestMetrics by remember {
        mutableStateOf(
            MobileMetrics(
                batteryLevel = 0f,
                batteryTemperature = 0f,
                memoryUsage = 0f,
                storageUsage = 0f,
            )
        )
    }

    LaunchedEffect(isRunning, activeConfig) {
        val config = activeConfig ?: return@LaunchedEffect
        if (!isRunning) {
            return@LaunchedEffect
        }

        while (isRunning) {
            try {
                statusText = "上报中"
                val metrics = collectMetrics(context)
                val response = sendPayload(config, metrics)
                latestMetrics = metrics
                appendHistory(batteryHistory, metrics.batteryLevel)
                appendHistory(temperatureHistory, metrics.batteryTemperature)
                appendHistory(memoryHistory, metrics.memoryUsage)
                appendHistory(storageHistory, metrics.storageUsage)
                lastPushText = formatTimestamp()
                responseText = response
            } catch (exc: Exception) {
                statusText = "上报失败"
                responseText = exc.message ?: "未知错误"
                isRunning = false
            }

            if (!isRunning) {
                break
            }
            delay(config.intervalSeconds * 1000L)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text(
            text = "DeviceSentinel 手机客户端",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
        )
        Text(
            text = "填写仪表盘地址后即可把手机电量、温度、内存和存储状态持续上报到共享网关。",
            style = MaterialTheme.typography.bodyMedium,
            color = Color(0xFF475569),
        )

        Card(
            colors = CardDefaults.cardColors(containerColor = Color.White),
            shape = RoundedCornerShape(20.dp),
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(text = "连接配置", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                OutlinedTextField(
                    value = instanceIdText,
                    onValueChange = { instanceIdText = it },
                    label = { Text("设备实例 ID") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = gatewayHostText,
                    onValueChange = { gatewayHostText = it },
                    label = { Text("仪表盘 IP") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                    OutlinedTextField(
                        value = gatewayPortText,
                        onValueChange = { gatewayPortText = it },
                        label = { Text("端口") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = intervalText,
                        onValueChange = { intervalText = it },
                        label = { Text("上报间隔（秒）") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.weight(1f),
                    )
                }
                OutlinedTextField(
                    value = gatewayPathText,
                    onValueChange = { gatewayPathText = it },
                    label = { Text("网关路径") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    text = "建议填写运行 DeviceSentinel 仪表盘那台机器的局域网 IP，例如 192.168.1.10。",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF64748B),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Button(
                        onClick = {
                            try {
                                val config = buildConfig(
                                    context = context,
                                    instanceIdText = instanceIdText,
                                    gatewayHostText = gatewayHostText,
                                    gatewayPortText = gatewayPortText,
                                    gatewayPathText = gatewayPathText,
                                    intervalText = intervalText,
                                )
                                saveConfig(context, config)
                                activeConfig = config
                                isRunning = true
                                statusText = "已启动"
                            } catch (exc: IllegalArgumentException) {
                                statusText = "配置错误"
                                responseText = exc.message ?: "请检查输入内容"
                            }
                        },
                    ) {
                        Text("开始上报")
                    }
                    TextButton(
                        onClick = {
                            isRunning = false
                            statusText = "已停止"
                        },
                    ) {
                        Text("停止")
                    }
                }
            }
        }

        StatusStrip(
            statusText = statusText,
            lastPushText = lastPushText,
            responseText = responseText,
        )

        MetricGrid(latestMetrics = latestMetrics)

        Text(text = "资源曲线", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        TrendCard(title = "电量", unit = "%", values = batteryHistory)
        TrendCard(title = "电池温度", unit = "°C", values = temperatureHistory)
        TrendCard(title = "内存使用率", unit = "%", values = memoryHistory)
        TrendCard(title = "存储使用率", unit = "%", values = storageHistory)
    }
}

@Composable
private fun StatusStrip(
    statusText: String,
    lastPushText: String,
    responseText: String,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color.White),
        shape = RoundedCornerShape(20.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            StatusRow(label = "连接状态", value = statusText)
            StatusRow(label = "最后上报", value = lastPushText)
            StatusRow(label = "网关响应", value = responseText)
        }
    }
}

@Composable
private fun StatusRow(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(text = label, style = MaterialTheme.typography.labelLarge, color = Color(0xFF64748B))
        Text(text = value, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun MetricGrid(latestMetrics: MobileMetrics) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
            MetricCard(
                title = "电量",
                value = formatMetric(latestMetrics.batteryLevel, "%"),
                modifier = Modifier.weight(1f),
                accent = Color(0xFF0F766E),
            )
            MetricCard(
                title = "电池温度",
                value = formatMetric(latestMetrics.batteryTemperature, "°C"),
                modifier = Modifier.weight(1f),
                accent = Color(0xFFE07A1F),
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
            MetricCard(
                title = "内存使用率",
                value = formatMetric(latestMetrics.memoryUsage, "%"),
                modifier = Modifier.weight(1f),
                accent = Color(0xFF1D4ED8),
            )
            MetricCard(
                title = "存储使用率",
                value = formatMetric(latestMetrics.storageUsage, "%"),
                modifier = Modifier.weight(1f),
                accent = Color(0xFF7C3AED),
            )
        }
    }
}

@Composable
private fun MetricCard(
    title: String,
    value: String,
    modifier: Modifier = Modifier,
    accent: Color,
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = Color.White),
        shape = RoundedCornerShape(20.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Box(
                modifier = Modifier
                    .width(36.dp)
                    .height(6.dp)
                    .background(accent, RoundedCornerShape(999.dp))
            )
            Text(text = title, style = MaterialTheme.typography.labelLarge, color = Color(0xFF64748B))
            Text(text = value, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun TrendCard(
    title: String,
    unit: String,
    values: List<Float>,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color.White),
        shape = RoundedCornerShape(20.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(text = title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(
                    text = if (values.isEmpty()) "--$unit" else formatMetric(values.last(), unit),
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color(0xFF475569),
                )
            }
            if (values.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(140.dp)
                        .background(Color(0xFFF8FAFC), RoundedCornerShape(16.dp)),
                ) {
                    Text(
                        text = "等待首次数据",
                        modifier = Modifier.padding(16.dp),
                        color = Color(0xFF94A3B8),
                    )
                }
            } else {
                Canvas(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(140.dp)
                        .background(Color(0xFFF8FAFC), RoundedCornerShape(16.dp)),
                ) {
                    val leftPadding = 28f
                    val topPadding = 18f
                    val rightPadding = 20f
                    val bottomPadding = 18f
                    val chartWidth = size.width - leftPadding - rightPadding
                    val chartHeight = size.height - topPadding - bottomPadding

                    listOf(0f, 50f, 100f).forEach { marker ->
                        val y = topPadding + chartHeight * (1f - marker / 100f)
                        drawLine(
                            color = Color(0xFFDCE3EC),
                            start = Offset(leftPadding, y),
                            end = Offset(size.width - rightPadding, y),
                            strokeWidth = 1.5f,
                        )
                    }

                    val path = Path()
                    values.forEachIndexed { index, rawValue ->
                        val x = leftPadding + chartWidth * index / (values.size - 1).coerceAtLeast(1)
                        val normalized = (rawValue.coerceIn(0f, 100f)) / 100f
                        val y = topPadding + chartHeight * (1f - normalized)
                        if (index == 0) {
                            path.moveTo(x, y)
                        } else {
                            path.lineTo(x, y)
                        }
                    }

                    drawPath(
                        path = path,
                        color = Color(0xFF2563EB),
                        style = Stroke(width = 5f, cap = StrokeCap.Round),
                    )
                }
            }
        }
    }
}

private fun loadConfig(context: Context): MobileClientConfig {
    val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    return MobileClientConfig(
        instanceId = prefs.getString(PREF_INSTANCE_ID, null) ?: buildDefaultInstanceId(context),
        gatewayHost = prefs.getString(PREF_GATEWAY_HOST, null) ?: "192.168.1.10",
        gatewayPort = prefs.getInt(PREF_GATEWAY_PORT, 10570),
        gatewayPath = prefs.getString(PREF_GATEWAY_PATH, null) ?: "/telemetry",
        intervalSeconds = prefs.getInt(PREF_INTERVAL_SECONDS, 5),
    )
}

private fun saveConfig(context: Context, config: MobileClientConfig) {
    context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        .edit()
        .putString(PREF_INSTANCE_ID, config.instanceId)
        .putString(PREF_GATEWAY_HOST, config.gatewayHost)
        .putInt(PREF_GATEWAY_PORT, config.gatewayPort)
        .putString(PREF_GATEWAY_PATH, config.gatewayPath)
        .putInt(PREF_INTERVAL_SECONDS, config.intervalSeconds)
        .apply()
}

private fun buildConfig(
    context: Context,
    instanceIdText: String,
    gatewayHostText: String,
    gatewayPortText: String,
    gatewayPathText: String,
    intervalText: String,
): MobileClientConfig {
    val instanceId = instanceIdText.ifBlank { buildDefaultInstanceId(context) }
    val gatewayHost = gatewayHostText.ifBlank { throw IllegalArgumentException("仪表盘 IP 不能为空。") }
    val gatewayPort = gatewayPortText.toIntOrNull()?.takeIf { it > 0 }
        ?: throw IllegalArgumentException("端口必须是大于 0 的整数。")
    val gatewayPath = gatewayPathText.ifBlank { "/telemetry" }
    val intervalSeconds = intervalText.toIntOrNull()?.takeIf { it > 0 }
        ?: throw IllegalArgumentException("上报间隔必须是大于 0 的整数。")

    return MobileClientConfig(
        instanceId = instanceId,
        gatewayHost = gatewayHost,
        gatewayPort = gatewayPort,
        gatewayPath = gatewayPath,
        intervalSeconds = intervalSeconds,
    )
}

private fun buildDefaultInstanceId(context: Context): String {
    val model = "${Build.MANUFACTURER}-${Build.MODEL}"
    val safeModel = model.lowercase(Locale.US).replace(Regex("[^a-z0-9]+"), "-").trim('-')
    val androidId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
        ?.takeLast(6)
        ?: "phone"
    return "mobile_device_real-${safeModel.take(18)}-$androidId"
}

private fun collectMetrics(context: Context): MobileMetrics {
    val batteryIntent = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
    val level = batteryIntent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: 0
    val scale = batteryIntent?.getIntExtra(BatteryManager.EXTRA_SCALE, 100) ?: 100
    val temperature = batteryIntent?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0)?.div(10f) ?: 0f

    val activityManager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
    val memoryInfo = ActivityManager.MemoryInfo()
    activityManager.getMemoryInfo(memoryInfo)
    val memoryUsage = if (memoryInfo.totalMem > 0L) {
        ((memoryInfo.totalMem - memoryInfo.availMem).toFloat() / memoryInfo.totalMem.toFloat()) * 100f
    } else {
        0f
    }

    val statFs = StatFs(Environment.getDataDirectory().absolutePath)
    val totalBytes = statFs.totalBytes.toFloat()
    val usedBytes = totalBytes - statFs.availableBytes.toFloat()
    val storageUsage = if (totalBytes > 0f) (usedBytes / totalBytes) * 100f else 0f

    return MobileMetrics(
        batteryLevel = if (scale > 0) level * 100f / scale else 0f,
        batteryTemperature = temperature,
        memoryUsage = memoryUsage,
        storageUsage = storageUsage,
    )
}

private suspend fun sendPayload(config: MobileClientConfig, metrics: MobileMetrics): String =
    withContext(Dispatchers.IO) {
        val payload = JSONObject().apply {
            put("instance_id", config.instanceId)
            put("timestamp", formatTimestamp())
            put(
                "metrics",
                JSONObject().apply {
                    put("battery_level", metrics.batteryLevel.roundToOneDecimal())
                    put("battery_temperature", metrics.batteryTemperature.roundToOneDecimal())
                    put("memory_usage", metrics.memoryUsage.roundToOneDecimal())
                    put("storage_usage", metrics.storageUsage.roundToOneDecimal())
                }
            )
            put(
                "meta",
                JSONObject().apply {
                    put("client", "mobile_android_client")
                    put("platform", "android")
                    put("mode", "app")
                }
            )
        }

        val url = URL("http://${config.gatewayHost}:${config.gatewayPort}${config.gatewayPath}")
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 5000
            readTimeout = 5000
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
        }

        connection.outputStream.use { output ->
            output.write(payload.toString().toByteArray(Charsets.UTF_8))
        }

        val stream = if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream
        val response = stream?.bufferedReader()?.use { it.readText() } ?: "HTTP ${connection.responseCode}"
        connection.disconnect()
        response
    }

private fun appendHistory(history: MutableList<Float>, value: Float) {
    if (history.size >= MAX_HISTORY_POINTS) {
        history.removeAt(0)
    }
    history.add(value.roundToOneDecimal())
}

private fun formatMetric(value: Float, unit: String): String = "${value.roundToOneDecimal()}$unit"

private fun formatTimestamp(): String =
    SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).format(Date())

private fun Float.roundToOneDecimal(): Float = (this * 10f).roundToInt() / 10f

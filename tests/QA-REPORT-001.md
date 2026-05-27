# KeepSafe KEEP-001 全链路 QA 测试报告

> **测试日期**: 2026-05-09
> **测试范围**: 后端(22个文件) + 固件(18个文件) + 结构(4个文件)
> **报告版本**: v1.0
> **测试类型**: 代码级验证（无真实硬件）

---

## 测试结果总览

| 测试项目 | 状态 | 🔴 Blocker | 🟡 Major | 🟢 Minor |
|----------|------|-----------|---------|---------|
| 1. 代码完整性测试 | ⚠️ 有异常 | 0 | 2 | 2 |
| 2. MQTT 数据通路验证 | 🔴 有严重问题 | 2 | 1 | 1 |
| 3. 安全测试 | ✅ 通过 | 0 | 0 | 1 |
| 4. 架构一致性测试 | ⚠️ 有异常 | 0 | 2 | 1 |
| 5. 结构模型尺寸验证 | ✅ 通过 | 0 | 0 | 0 |
| **总计** | | **2** | **5** | **5** |

---

## 1. 代码完整性测试

### 1.1 后端Python语法检查

测试方法: `python3 -m py_compile` 扫描全部 17 个 `.py` 文件

结果: **✅ 全部通过** — 所有 Python 文件语法正确

```
app/config.py           OK
app/main.py             OK
app/db.py               OK
app/mqtt_client.py      OK
app/lbs_resolver.py     OK
app/redis_cache.py      OK
app/api/auth.py         OK
app/api/devices.py      OK
app/push/fcm.py         OK
app/push/apns.py        OK
app/push/__init__.py    OK
app/models/device.py    OK
app/models/location.py  OK
app/models/sos.py       OK
app/models/alert.py     OK
app/models/__init__.py  OK
app/api/__init__.py     OK
app/__init__.py         OK
```

### 1.2 固件C文件检查

测试方法: 人工审查 13 个 `.c`/`.h` 文件语法结构、括号匹配、头文件引用

结果: **✅ 基本正确** — C 代码结构完整，所有头文件相互引用链完整

| 文件 | 状态 | 备注 |
|------|------|------|
| main.c (713行) | ✅ | 状态机循环完整，JSON builder 存在 |
| config.h (152行) | ✅ | 所有 GPIO/时序定义完整 |
| power.c/h (358+183行) | ✅ | 5态状态机实现完整 |
| mqtt.c/h (418+164行) | ✅ | AT命令接口完整 |
| gps.c/h (337+96行) | ✅ | NMEA GGA/RMC 解析器完整 |
| lbs.c/h (236+97行) | ✅ | AT+CSQ/+CREG/+CENG 解析完整 |
| sos.c/h (397+145行) | ✅ | 按键去抖、ADC、低电量检测完整 |
| accel.c/h (343+161行) | ✅ | LIS3DH I2C 驱动完整 |
| led.c/h (221+99行) | ✅ | PWM LED 驱动完整 |
| CMakeLists.txt (4行) | ✅ | ESP-IDF 构建配置 |

### 1.3 配置项一致性检查 — config.h vs config.py

| 配置项 | 后端 config.py | 固件 config.h | 一致性 |
|--------|---------------|--------------|--------|
| MQTT topic: location | `keepsafe/v1/{device_id}/location` | `"keepsafe/v1/" DEVICE_ID "/location"` | ✅ |
| MQTT topic: heartbeat | `keepsafe/v1/{device_id}/heartbeat` | `"keepsafe/v1/" DEVICE_ID "/heartbeat"` | ✅ |
| MQTT topic: sos | `keepsafe/v1/{device_id}/sos` | `"keepsafe/v1/" DEVICE_ID "/sos"` | ✅ |
| MQTT topic: low_battery | `keepsafe/v1/{device_id}/alert/low_battery` | `"keepsafe/v1/" DEVICE_ID "/alert/low_battery"` | ✅ |
| MQTT QoS: location | 后端 QOS=1 (订阅) | `MQTT_QOS_LOCATION=1` | ✅ |
| MQTT QoS: sos | 后端 QOS=1 (订阅) | `MQTT_QOS_SOS=1` | ✅ |
| MQTT QoS: low_battery | 后端 QOS=1 (订阅) | `MQTT_QOS_LOW_BATTERY=1` | ✅ |
| MQTT QoS: heartbeat | 后端 QOS=0 (订阅) | `MQTT_QOS_HEARTBEAT=0` | ✅ |
| MQTT QoS: version | 后端 QOS=0 (订阅) | 固件无 version 发布 | 🟡 Major |

> **🟡 Major-01**: 后端订阅了 `keepsafe/v1/{device_id}/version` (QoS 0) 但固件 `config.h` 和 `mqtt.c` 中没有定义 `MQTT_TOPIC_VERSION` 宏和 `mqtt_publish_version()` 函数。固件不发布 version 消息，导致后端 version handler 无法被触发。建议在固件启动连接后发布一次 firmware version。

| 配置项 | 后端 | 固件 | 一致性 |
|--------|------|------|--------|
| MQTT Broker Port | `emqx_port: int = 1883` | `MQTT_BROKER_PORT 1883` | ✅ |
| MQTT Keepalive | 客户端 `keepalive=60` (gmqtt) | `MQTT_KEEPALIVE_S 300` | 🟢 Minor |

> **🟢 Minor-01**: 后端 MQTT client keepalive=60s，固件配置 300s。虽然两端各自设定不影响连接（broker 端会协商），但建议统一以免 broker 因 keepalive 值不匹配提前断开一方。

### 1.4 JSON Payload 结构一致性

| 消息类型 | 后端子段 | 固件字段 | 一致性 |
|----------|---------|---------|--------|
| location | `lat`, `lng`, `alt`, `speed`, `heading`, `accuracy`, `satellites`, `fix_type`, `cell_id`, `battery`, `charging`, `rssi`, `fw_version` | `lat`, `lng`, `alt`, `speed`, `heading`, `hdop`, `sats`, `fix_type`, `bat`, `source`, `cell_id`, `rssi` | 🔴 Blocker |
| heartbeat | `battery`, `charging`, `rssi`, `uptime`, `last_seen` | `bat`, `bat_mv`, `state`, `loc_count`, `sos_count`, `firmware` | 🔴 Blocker |
| sos | `lat`, `lng`, `accuracy`, `battery`, `trigger_duration_ms` | `lat`, `lng`, `bat`, `firmware`, `type` | 🟡 Major |
| low_battery | `battery`, `ts` | `bat`, `bat_mv`, `type` | 🟢 Minor |

> **🔴 Blocker-01 (字段名不匹配 — location)**: 固件 `build_location_json()` 使用字段名 `sats`、`hdop`、`bat`，而后端 `mqtt_client.py` 期望 `satellites`、`accuracy`、`battery`。需至少对齐以下字段：
> - 固件 `sats` → 后端期望 `satellites` ❌ 不匹配
> - 固件 `hdop` → 后端期望 `accuracy` ❌ 不匹配
> - 固件 `bat` → 后端期望 `battery` ❌ 不匹配
>
> **解决方案**: 修改固件 JSON builder 使用后端期望的字段名，或修改后端解析逻辑。

> **🔴 Blocker-02 (字段名不匹配 — heartbeat)**: 固件 `build_heartbeat_json()` 使用 `bat`、`bat_mv`、`state`、`loc_count`、`sos_count`、`firmware`，而后端 `_handle_heartbeat()` 期望 `battery`、`charging`、`rssi`、`uptime`。字段名和内容两个方向都不匹配。
>
> **解决方案**: 
> 1. 后端 heartbeat handler 当前访问 `data.get("battery")` 和 `data.get("charging")`，但固件不发送这两字段。
> 2. 固件发送 `bat` 作为电量百分比，后端不会读取到。
> 3. 缺少 `type: "heartbeat"` 标识字段（后端按 type 路由）。

> **🟡 Major-02 (SOS JSON 缺少 accuracy 和 trigger_duration_ms)**: 固件 `build_sos_json()` 输出中缺少后端 `_handle_sos()` 期望的 `accuracy` 和 `trigger_duration_ms` 字段。后端 DB 写入时会使用 `data.get("trigger_duration_ms")` 得到 None，但该字段可为 NULL，所以严重性降为 Major 而非 Blocker。

> **🟢 Minor-02 (低电量字段名 bat vs battery)**: 固件低电量 JSON 使用 `bat`，后端期望 `battery`。同上命名不一致问题。

---

## 2. MQTT 数据通路验证

### 2.1 MQTT Topic 命名一致性

| Topic | 后端订阅模式 | 固件发布Topic | 匹配? |
|-------|------------|--------------|-------|
| location | `keepsafe/v1/+/location` | `keepsafe/v1/{device_id}/location` | ✅ |
| heartbeat | `keepsafe/v1/+/heartbeat` | `keepsafe/v1/{device_id}/heartbeat` | ✅ |
| sos | `keepsafe/v1/+/sos` | `keepsafe/v1/{device_id}/sos` | ✅ |
| low_battery | `keepsafe/v1/+/alert/low_battery` | `keepsafe/v1/{device_id}/alert/low_battery` | ✅ |
| version | `keepsafe/v1/+/version` | 固件未发布 (见 Major-01) | ❌ |

所有 4 个固件发布的 topic 与后端订阅模式完全匹配。Version topic 固件未实现。

### 2.2 消息类型字段 (type dispatch)

后端的 MQTT 消息分发依赖 `data.get("type")` 字段进行路由：

```
msg_type = data.get("type", "unknown")
```

| 固件消息 | 固件是否包含 type 字段 | 后端期望 type | 匹配? |
|---------|---------------------|--------------|-------|
| location JSON | ❌ 无 `type` 字段 | `"location"` | 🔴 不匹配 |
| heartbeat JSON | ❌ 无 `type` 字段 | `"heartbeat"` | 🔴 不匹配 |
| SOS JSON | ✅ `"type":"sos"` | `"sos"` | ✅ |
| low_battery JSON | ✅ `"type":"low_battery"` | `"low_battery"` | ✅ |

> **🔴 Blocker-03 (location 和 heartbeat 缺少 type 字段)**: 固件 `build_location_json()` 和 `build_heartbeat_json()` 均未添加 `type` 字段。后端 `_on_message()` 会收到 `data.get("type")` 返回 `"unknown"`，进入 `else` 分支打印警告。
>
> 虽然 location 的 `type` 缺失后，后续 handler 不会按 type 路由，但后端 handler 仅通过设备自己的逻辑直接调用 `_handle_location()` —— **等等**，重新检查后端代码：
>
> 后端 `_on_message()` 中：
> ```python
> msg_type = data.get("type", "unknown")
> ...
> if msg_type == "location":
>     self._handle_location(device_id, data)
> ```
> 
> 因为没有 `type` 字段，所有 location 和 heartbeat 消息都会被当成 `"unknown"` 类型处理，**从不调用** `_handle_location` 或 `_handle_heartbeat`。这是致命错误。
>
> **解决方案**: 固件所有 JSON payload 必须携带 `type` 字段。

### 2.3 MQTT 消息流数据通路验证

从固件到后端的数据流：

```
[LIS3DH 运动检测] → [ESP32-S3 状态机] → [GPS/LBS获取] → [JSON构建] → 
[AT+MQTTPUB to Air780E] → [4G网络] → [EMQX Broker] → 
[Backend MQTT Client订阅] → [gmqtt on_message] → [JSON解析] → 
[Redis Cache] + [TimescaleDB] + [Push Notification]
```

通路分段验证：

| 环节 | 状态 | 备注 |
|------|------|------|
| 固件 — GPS 获取 | ✅ | `acquire_gps_fix()` + `gps_parse_line()` NMEA 解析完整 |
| 固件 — JSON 构建 | ❌ | 字段名不匹配 (Blocker-01, Blocker-02) |
| 固件 — MQTT 发布 | ✅ | `at_mqtt_pub()` 使用 Air780E AT 命令 |
| 网络传输 (4G→EMQX) | ✅ | Topic 命名一致 |
| 后端 — MQTT 订阅 | ✅ | 通配符 `+` 订阅正确 |
| 后端 — JSON 解析 | ❌ | 缺少 type 字段导致路由失败 (Blocker-03) |
| 后端 — Redis 缓存 | ❌ | 由于路由失败，location/heartbeat 不会写入缓存 |
| 后端 — DB 写入 | ❌ | 同上，不会写入 TimescaleDB |
| 后端 — Push 通知 (SOS) | ⚠️ | SOS 消息 type 正确，但 push token 使用 `device_id` 作为占位符 (见安全测试) |

---

## 3. 安全合规测试

### 3.1 密钥和占位符 (Placeholder) 检查

测试方法: 搜索所有文件中硬编码的密钥、密码、API key

| 文件 | 密钥/密码 | 是否使用占位符 | 结论 |
|------|----------|--------------|------|
| `backend/app/config.py` | `db_password` | `{{PLACEHOLDER_DB_PASSWORD}}` | ✅ |
| `backend/app/config.py` | `redis_password` | `{{PLACEHOLDER_REDIS_PASSWORD}}` | ✅ |
| `backend/app/config.py` | `apns_key_id` | `{{PLACEHOLDER_APNS_KEY_ID}}` | ✅ |
| `backend/app/config.py` | `apns_team_id` | `{{PLACEHOLDER_APNS_TEAM_ID}}` | ✅ |
| `backend/app/config.py` | `opencellid_api_key` | `{{PLACEHOLDER_OPENCELLID_API_KEY}}` | ✅ |
| `backend/app/mqtt_client.py` | MQTT backend password | `{{PLACEHOLDER_EMQX_BACKEND_PASSWORD}}` | ✅ |
| `backend/docker-compose.yml` | DB password | `{{PLACEHOLDER_DB_PASSWORD}}` | ✅ |
| `backend/docker-compose.yml` | Redis password | `{{PLACEHOLDER_REDIS_PASSWORD}}` | ✅ |
| `backend/docker-compose.yml` | EMQX dashboard password | `{{PLACEHOLDER_EMQX_DASHBOARD_PASSWORD}}` | ✅ |
| `backend/.env.example` | 所有密钥 | `{{PLACEHOLDER_*}}` 格式 | ✅ |
| `firmware/main/config.h` | DEVICE_ID | `"KS-XXXXXXXX" // {{PLACEHOLDER_DEVICE_ID}}` | ✅ |
| `firmware/main/config.h` | APN_NAME | `{{PLACEHOLDER_APN_NAME}}` | ✅ |
| `firmware/main/config.h` | MQTT_BROKER_HOST | `{{PLACEHOLDER_MQTT_HOST}}` | ✅ |

结果: **✅ 全部使用占位符** — 无任何硬编码密钥。所有敏感信息都通过 `{{PLACEHOLDER_*}}` 模板标记。

### 3.2 CORS 配置检查

```python
# app/main.py:78-84
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

> **🟢 Minor-03**: `allow_origins=["*"]` 在生产环境中太宽松。对于当前版本 (KEEP-001 原型阶段) 可接受，但建议在发布前限制为已知的移动端应用源或前端域名。同时 `allow_credentials=True` 与 `allow_origins=["*"]` 同时使用时，浏览器会忽略 CORS 响应中的 `Access-Control-Allow-Credentials`，建议明确指定源列表。

### 3.3 日志敏感信息泄露检查

| 文件位置 | 日志内容 | 风险 |
|---------|---------|------|
| `mqtt_client.py:64` | `logger.debug("MQTT msg: type=%s device=%s topic=%s", ...)` | ✅ 安全 |
| `mqtt_client.py:82` | `logger.error("MQTT: error processing message on %s: %s", topic, exc, exc_info=True)` | ✅ 安全 |
| `mqtt_client.py:361` | MQTT auth with hardcoded placeholder | ✅ 占位符 |
| `auth.py:41` | `logger.info("Auth request: device=%s", req.device_id)` | ✅ 仅设备ID，无密钥 |
| `auth.py:55` | `logger.warning("Auth denied: token mismatch for %s", req.device_id)` | ✅ 无 token 泄露 |
| `push/fcm.py:71` | `logger.warning("FCM device token unregistered: %s", device_token)` | 🟡 Major |
| `push/apns.py:131` | `logger.info("APNs push sent successfully to %s", device_token[:16])` | 🟢 Minor |

> **🟡 Major-03 (FCM 日志泄露 push token)**: `fcm.py:71` 直接打印完整的 FCM device token 到日志。Push token 是敏感信息，泄露后可被用于向设备发送恶意推送。建议只记录 token 的前8个字符。

### 3.4 数据库密码环境变量分离

结果: **✅ 完全分离**
- `config.py` 使用 Pydantic Settings 从环境变量读取
- `.env.example` 提供模板
- `docker-compose.yml` 也使用占位符
- 数据库 URL 在运行时构建，不硬编码密码

---

## 4. 架构一致性测试

### 4.1 省电策略完整实现验证

5态状态机完整性：

| 状态 | 期望行为 | 实现 | 状态 |
|------|---------|------|------|
| STATIONARY | GPS OFF, LBS only, 30-min interval | `power.h:29` + `power.c:176-182` ✅ | ✅ |
| MOVING | GPS ON, 5-min interval | `power.h:30` + `power.c:184-189` ✅ | ✅ |
| JUST_STOPPED | GPS ON, one more fix, then STATIONARY | `power.h:31` + `power.c:191-196` ✅ | ✅ |
| SOS_ACTIVE | GPS ON, 30s SOS repeat | `power.h:32` + `power.c:197-201` ✅ | ✅ |
| DEEP_SLEEP | Enter deep sleep, all devices powered down | `power.h:33` + `power.c:325-352` ✅ | ✅ |

动态频率实现：

| 功能 | 实现 | 状态 |
|------|------|------|
| 运动检测切换 | `power_on_motion_detected()` → MOVING | ✅ |
| 静止超时切换 | `power_on_stationary_timeout()` → JUST_STOPPED | ✅ |
| 间隔动态计算 | `power_get_next_report_interval()` 基于状态 | ✅ |
| 深度睡眠时间计算 | `power_calculate_sleep_duration()` 基于下次事件 | ✅ |

PSM 实现：

| 功能 | 实现 | 状态 |
|------|------|------|
| PSM AT 命令 | `mqtt_configure_psm()` 调用 AT+CPSMS | ✅ |
| eDRX 配置 | 补充 AT+CEDRXS 命令 | ✅ |
| 备注说明 | `config.h:80-98` 详细注释了运营商兼容性 | ✅ |

> **🟡 Major-04 (状态机未在 main.c 主循环中完整调用)**: `power_on_stationary_timeout()` 函数在 `power.c` 中实现了，但 `main.c` 主循环中未调用该函数来检测长时间无运动。缺少定时检查 `last_motion_detected_ms` 的机制来触发 JUST_STOPPED 状态转换。这意味着设备进入 MOVING 状态后永远无法回到 STATIONARY。

### 4.2 SOS 端到端流程验证

```
[SOS按钮长按3s] → [sos_tick() 检测] → [SOS_TRIGGERED] → 
[sos_vibrate_feedback()] → [on_sos_triggered callback] → 
[power_on_sos_triggered() → SOS_ACTIVE state] → 
[report_sos() → acquire_gps_fix() → build_sos_json() → 
mqtt_publish_sos()] → [EMQX] → [Backend _handle_sos()] → 
[DB INSERT sos_events + alerts] → [Push notification]
```

| 环节 | 实现 | 状态 |
|------|------|------|
| 按钮硬件中断 | `sos_gpio_isr_handler()` IRAM_ATTR | ✅ |
| 去抖逻辑 | `SOS_MAX_DEBOUNCE_MS=50ms` | ✅ |
| 长按计时 | `SOS_LONG_PRESS_MS=3000ms` 3秒 | ✅ |
| 振动反馈 | `sos_vibrate_feedback(200ms)` | ✅ |
| GPS 获取 | SOS 触发时主动获取 | ✅ |
| JSON 发布 | `build_sos_json()` + `mqtt_publish_sos()` | ✅ |
| 后端接收 | `_handle_sos()` 路由 (type="sos") | ✅ |
| DB 记录 | `sos_events` + `alerts` 双表写入 | ✅ |
| Push 通知 | FCM/APNs 发送 | ✅ |

结果: **✅ SOS 端到端流程完整**

> **🟢 Minor-04 (SOS push token 使用 device_id 占位)**: `mqtt_client.py:276` 中 `device_token=device_id` 使用了设备ID作为推送占位符。这在没有完整的用户推送 token 管理时是一个已知简化，建议在下一版本中实现 `user_push_tokens` 表。

### 4.3 后端 API 设计一致性

| 端点 | 方法 | 路径 | 实现 | 状态 |
|------|------|------|------|------|
| 设备位置 | GET | `/api/v1/devices/{device_id}/location` | `devices.py:89` | ✅ |
| 设备状态 | GET | `/api/v1/devices/{device_id}/status` | `devices.py:119` | ✅ |
| 历史轨迹 | GET | `/api/v1/devices/{device_id}/history` | `devices.py:178` | ✅ |
| SOS 事件 | GET | `/api/v1/devices/{device_id}/sos/events` | `devices.py:213` | ✅ |
| 设备绑定 | POST | `/api/v1/devices/bind` | `devices.py:235` | ✅ |
| 设备解绑 | DELETE | `/api/v1/devices/{device_id}/bind` | `devices.py:296` | ✅ |
| 设备认证 | POST | `/api/v1/auth/device` | `auth.py:33` | ✅ |
| 设备 ACL | GET | `/api/v1/auth/device/acl` | `auth.py:67` | ✅ |
| 健康检查 | GET | `/health` | `main.py:89` | ✅ |

结果: **✅ 8个API端点 + 1个健康检查，全部实现**

### 4.4 Database Schema 一致性

| 表 | SQL定义 | SQLAlchemy模型 | 一致性 |
|----|---------|---------------|--------|
| devices | `init.sql:12-19` | `db.py:50-58` | ✅ |
| user_devices | `init.sql:24-32` | `db.py:106-114` | ✅ |
| locations (hypertable) | `init.sql:40-58` | `db.py:61-80` | ✅ |
| sos_events | `init.sql:65-74` | `db.py:83-93` | ✅ |
| alerts | `init.sql:81-87` | `db.py:96-103` | ✅ |

所有表结构、字段名、数据类型完全一致。

### 4.5 Docker Compose 基础设施

| 服务 | 镜像 | 端口映射 | 健康检查 | 状态 |
|------|------|---------|---------|------|
| TimescaleDB | `timescale/timescaledb:2-pg16` | 5432 | `pg_isready` | ✅ |
| Redis | `redis:7-alpine` | 6379 | `redis-cli incr ping` | ✅ |
| EMQX | `emqx/emqx:5.7.1` | 1883/8883/8083/8084/18083 | ❌ 无健康检查 | 🟡 Major |

> **🟡 Major-05 (EMQX 缺少健康检查)**: 与其他两个服务不同，EMQX 没有配置 `healthcheck` 块。建议添加 MQTT 协议层面的健康检查，例如使用 `mqttx` 或 EMQX 的 REST API `http://localhost:18083/api/v5/status`。

---

## 5. 结构模型尺寸验证

### 5.1 外形尺寸 — 与 HARDWARE_SPEC.md/方案文档一致性

| 维度 | SCAD 定义 | 期望值 (78×48×12mm) | 一致性 |
|------|----------|-------------------|--------|
| body_len (X) | 78 mm | 78 mm | ✅ |
| body_wid (Y) | 48 mm | 48 mm | ✅ |
| body_h (Z) | 12 mm | 12 mm | ✅ |
| corner_r | 8 mm | 8 mm (跑道圆角) | ✅ |
| wall_t | 1.5 mm | 1.5 mm | ✅ |

### 5.2 电池 703048 可装入性

| 维度 | 内腔尺寸 | 电池 703048 | 单侧间隙 | 结论 |
|------|---------|------------|---------|------|
| X (宽) | 45 mm | 30 mm | 7.5 mm | ✅ |
| Y (长) | 75 mm | 48 mm | 13.5 mm | ✅ |
| Z (厚) | 9 mm | 7 mm | **1.0 mm** | ✅ |

SCAD 内部布局中 `battery_703048()` 模块与 `BATTERY_CHECK.md` 尺寸完全一致。BATTERY_CHECK.md 报告已经给出了通过结论。

### 5.3 开孔位置验证

| 开孔 | 位置 | 尺寸 | 规范要求 | 一致性 |
|------|------|------|---------|--------|
| SOS 键 | 底部居中, `sos_pos_y = -body_len/2 + 8 + sos_r` | 半径 11mm (直径 22mm) | SOS 22mm | ✅ |
| LED 指示灯 | 正面中上, `led_pos_y = body_len/2 - 6`, 间距 `led_spacing=6` | 孔径 3mm, 间距 6mm | LED 3mm 间距6mm | ✅ |
| 喇叭微孔 | 正面中上, `speaker_pos_y = body_len/2 - 12` | 20×14mm 区域, 0.8mm孔径 | — | ✅ |
| Type-C | 右侧正中 | 10×4mm | — | ✅ |
| 挂耳 | 顶部左侧偏心 | 10×14mm, 内孔8mm | — | ✅ |

结果: **✅ SOS 22mm 直径、LED 3mm 间距6mm 完全匹配**

### 5.4 内部堆叠干涉检查

| 元件层 | Z 位置 (中心为0) | 干涉检查 | 状态 |
|--------|-----------------|---------|------|
| 下壳壁 | -6.0 ~ -4.5 | 结构 | ✅ |
| SOS按键 | -4.5 ~ -2.5 (底部) | 无干涉 | ✅ |
| 电池 703048 | -4.5 ~ +2.5 | 无干涉 | ✅ |
| PCB主板 | +2.5 ~ +4.1 | 与电池错层 | ✅ |
| 上壳壁 | +4.5 ~ +6.0 | 结构 | ✅ |
| LIS3DH | PCB顶面 | 无干涉 | ✅ |
| 4G+GPS天线 | 左上区贴底 | 无干涉 | ✅ |
| 振动马达 | 右底部 | 无干涉 | ✅ |

结果: **✅ 无任何物理干涉**

---

## 6. 综合问题清单

### 🔴 Blocker (必须修复才能发布)

| ID | 严重性 | 文件 | 问题描述 |
|----|--------|------|---------|
| B-01 | 🔴 | `firmware/main/main.c:144-191` | location JSON 字段名不匹配：固件用 `sats`/`hdop`/`bat`/`source`，后端期望 `satellites`/`accuracy`/`battery` |
| B-02 | 🔴 | `firmware/main/main.c:208-228` | heartbeat JSON 字段名不匹配：固件用 `bat`/`bat_mv`/`state`/`loc_count`/`sos_count`/`firmware`，后端期望 `battery`/`charging`/`rssi`/`uptime` |
| B-03 | 🔴 | `firmware/main/main.c` | location 和 heartbeat JSON 缺少 `"type"` 字段。后端 `_on_message()` 按 type 路由消息，无 type 则进入 `"unknown"` 分支，导致 location 和 heartbeat 消息完全不被处理 |

### 🟡 Major (建议修复)

| ID | 严重性 | 文件 | 问题描述 |
|----|--------|------|---------|
| M-01 | 🟡 | `firmware/main/config.h` + `mqtt.c` | 缺少 version 消息的宏定义和发布函数。后端订阅了 `keepsafe/v1/{device_id}/version` 但固件不发布 |
| M-02 | 🟡 | `firmware/main/main.c:257-275` | SOS JSON 缺少 `accuracy` 和 `trigger_duration_ms` 字段（后端期望） |
| M-03 | 🟡 | `backend/app/push/fcm.py:71` | FCM 日志打印完整 device token，存在敏感信息泄露风险 |
| M-04 | 🟡 | `firmware/main/main.c` | `power_on_stationary_timeout()` 在主循环中未被调用，MOVING→JUST_STOPPED→STATIONARY 状态转换链断裂 |
| M-05 | 🟡 | `backend/docker-compose.yml` | EMQX 服务缺少 healthcheck 配置 |

### 🟢 Minor (记录即可)

| ID | 严重性 | 文件 | 问题描述 |
|----|--------|------|---------|
| m-01 | 🟢 | `backend/app/config.py` vs `firmware/main/config.h` | MQTT keepalive 后端 60s vs 固件 300s，虽不影响但建议统一 |
| m-02 | 🟢 | `firmware/main/main.c` | 低电量 JSON 字段名 `bat` vs 后端期望 `battery` |
| m-03 | 🟢 | `backend/app/main.py:80` | CORS `allow_origins=["*"]` 在生产环境太宽松 |
| m-04 | 🟢 | `backend/app/mqtt_client.py:276` | SOS push 通知使用 `device_id` 作为 device_token 占位符 |
| m-05 | 🟢 | `backend/app/push/apns.py:131` | APNs 日志只打印 token 前16字符，处理较好但未完全屏蔽 |

---

## 7. 测试总结

### 7.1 总体评分

| 维度 | 评分 | 解释 |
|------|------|------|
| 代码完整性 | ⚠️ 7/10 | Python/../C 语法正确，但 JSON 结构有严重不匹配 |
| 安全合规 | ✅ 9/10 | 所有密钥使用占位符，日志需改进 |
| 架构一致性 | ✅ 8/10 | 状态机/REST API/SOS 流程完整，部分边缘情况缺失 |
| 结构尺寸 | ✅ 10/10 | SCAD 尺寸与规格完全一致，电池可装入 |
| MQTT 数据通路 | ❌ 4/10 | Topic 路径一致但 JSON 字段/type 字段严重不匹配 |

### 7.2 关键发现

1. **🔴 最大风险: JSON Payload 字段名不一致** — 固件使用的字段名 (`sats`, `hdop`, `bat`) 与后端解析的期望字段名 (`satellites`, `accuracy`, `battery`) 完全不匹配。这是两个独立开发团队最常见的集成问题。

2. **🔴 致命缺陷: 缺少 type 字段导致路由失败** — location 和 heartbeat 消息因缺少 type 字段，后端会将其标记为 type="unknown"，不会调用对应的 handler。即使字段名修复了，数据也无法存入数据库。

3. **🟡 架构完整性好但边缘缺失**：version topic 未实现、静止超时检测未在主循环中调用，但整体架构设计合理，修复成本低。

4. **✅ 安全合规表现优秀**：所有密钥使用占位符、密码环境变量分离、日志基本不泄露凭证。

5. **✅ 结构模型验证全部通过**：3D模型尺寸、电池兼容性、开孔位置均与规格一致。

### 7.3 建议修复优先级

1. **立即修复** (发布前): B-01, B-02, B-03 (JSON 字段名 + type 字段)
2. **尽快修复**: M-01 (version topic), M-03 (日志泄露), M-04 (状态机断链)
3. **迭代修复**: M-02, M-05, 所有 Minor

---

*测试报告由 Hermes Agent 自动生成*
*End of Report*

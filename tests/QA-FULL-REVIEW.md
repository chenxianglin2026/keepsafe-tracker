# KeepSafe 全项目 QA 审查报告

**审查日期**: 2026-05-11
**审查范围**: 后端 / 固件 / iOS / Android / 微信小程序 / 硬件
**审查人**: Hermes Agent (AI Code Review)

---

## 目录

1. [后端 (Python/FastAPI)](#1-后端)
2. [固件 (C/ESP-IDF)](#2-固件)
3. [iOS App (Swift)](#3-ios-app)
4. [Android App (Kotlin)](#4-android-app)
5. [微信小程序](#5-微信小程序)
6. [硬件 (OpenSCAD)](#6-硬件)
7. [跨模块数据一致性](#7-跨模块数据一致性)
8. [总结 & 优先级建议](#8-总结--优先级建议)

---

## 1. 后端

### 1.1 Python 语法检查

| 文件 | 状态 |
|------|------|
| `app/main.py` | ✅ 语法正确 |
| `app/config.py` | ✅ 语法正确 |
| `app/db.py` | ✅ 语法正确 |
| `app/mqtt_client.py` | ✅ 语法正确 |
| `app/redis_cache.py` | ✅ 语法正确 |
| `app/lbs_resolver.py` | ✅ 语法正确 |
| `app/api/auth.py` | ✅ 语法正确 |
| `app/api/devices.py` | ✅ 语法正确 |
| `app/api/users.py` | ✅ 语法正确 |
| `app/api/fences.py` | ✅ 语法正确 |
| `app/push/__init__.py` | ✅ 语法正确 |
| `app/push/fcm.py` | ✅ 语法正确 |
| `app/push/apns.py` | ✅ 语法正确 |
| `app/models/*.py` | ✅ 语法正确 |

### 1.2 发现的问题

#### 🔴 Blocker

**B-01: 后端缺少 alert 列表 API**
- **文件**: `app/api/devices.py`, `app/api/users.py`
- **描述**: iOS App 和 Android App 都调用了 `GET /api/v1/alerts`，但后端路由中没有注册 alert 相关的 API 路由（`app/main.py` 只注册了 auth、devices、users、fences 四个路由器）。后端有 `Alert` model 和 `alerts` 表，但没有查询端点。
- **建议**: 新增 `app/api/alerts.py`，包含 `GET /api/v1/alerts`（分页查询）、`PUT /api/v1/alerts/{id}/read`（标记已读）、`PUT /api/v1/alerts/read-all`（标记全部已读）三个端点。

**B-02: iOS APIService 请求的后端端点大量不匹配**
- **文件**: `code/ios/KeepSafe/Services/APIService.swift`
- **描述**: iOS 使用的后端端点路径与实际后端路由严重不一致：
  - `getDevices()` 请求 `GET /devices` → 后端实际: 无此路由 (只有 `/api/v1/devices/{device_id}/...` 形式的端点)
  - `getDevice(id:)` 请求 `GET /devices/{id}` → 后端实际: 无此路由
  - `getAlerts()` 请求 `GET /alerts` → 后端实际: 无此路由（见 B-01）
  - `markAlertRead(id:)` 请求 `POST /alerts/{id}/read` → 后端实际: 无此路由
  - `markAllAlertsRead()` 请求 `POST /alerts/read-all` → 后端实际: 无此路由
  - `getUserProfile()` 请求 `GET /user/profile` → 后端实际: `GET /api/v1/users/profile`
  - `updateUserProfile(nickname:)` 请求 `PUT /user/profile` → 后端实际: `PUT /api/v1/users/profile`
  - `registerPushToken()` 请求 `POST /user/push-token` → 后端实际: 无此路由
  - `bindDevice()` 请求 `POST /devices/bind` → 后端实际: `POST /api/v1/devices/bind` ✅ 正确
  - `unbindDevice(id:)` 请求 `POST /devices/{id}/unbind` → 后端实际: `DELETE /api/v1/devices/{device_id}/bind`
- **建议**: 需要全面对齐 iOS 的 `APIService.swift` 路径与后端实际路由定义。

**B-03: Android ApiService 端点路径大量不匹配**
- **文件**: `code/android/app/src/main/java/com/keepsafe/app/data/api/ApiService.kt`
- **描述**: Android 使用的路径与后端不匹配：
  - `getDevices()` → `GET devices/` → 后端实际: 无此路由
  - `getDevice(deviceId: Long)` → `GET devices/{id}/` → 后端实际: 后端用 `String` 类型 device_id，且无此路由
  - `registerDevice(device:)` → `POST devices/` → 后端实际: 无此路由
  - `updateDevice(id: Long, device:)` → `PUT devices/{id}/` → 后端实际: 无此路由
  - `deleteDevice(id: Long)` → `DELETE devices/{id}/` → 后端实际: 无此路由
  - `getAlerts()` → `GET alerts/` → 后端实际: 无此路由（见 B-01）
  - `markAlertRead(alertId: Long)` → `PUT alerts/{id}/read/` → 后端实际: 无此路由
  - `getProfile()` → `GET profile/` → 后端实际: `GET /api/v1/users/profile`
  - `updateProfile(profile:)` → `PUT profile/` → 后端实际: `PUT /api/v1/users/profile`
  - `reportLocation()` → `POST devices/{id}/location/` → 后端实际: 固件通过 MQTT 上报位置，无此 REST 端点
- **建议**: 全面重新设计 Android ApiService 以匹配后端实际路由。

**B-04: 微信小程序 api.js 端点路径不匹配**
- **文件**: `code/miniapp/utils/api.js`
- **描述**: 小程序使用的端点路径与后端不匹配：
  - `getDeviceList()` → `GET /devices` → 后端实际: 无此路由
  - `getDeviceDetail(deviceId)` → `GET /devices/${deviceId}` → 后端实际: 无 `GET /devices/{id}` 路由
  - `getDeviceLocationHistory()` → `GET /devices/${deviceId}/location/history` → 后端实际: `GET /api/v1/devices/{device_id}/history`
  - `getAlertList()` → `GET /alerts` → 后端实际: 无此路由
  - `markAlertRead()` → `PUT /alerts/${alertId}/read` → 后端实际: 无此路由
  - `markAllAlertsRead()` → `PUT /alerts/read-all` → 后端实际: 无此路由
  - `getShareLink()` → `POST /share` → 后端实际: 无此路由
  - `wxLogin(code)` → `POST /auth/wx-login` → 后端实际: 无此路由（后端 auth 只有 `/api/v1/auth/device` 设备认证）
  - `getUserInfo()` → `GET /user/profile` → 后端实际: `GET /api/v1/users/profile`
  - `updateUserInfo(data)` → `PUT /user/profile` → 后端实际: `PUT /api/v1/users/profile`
- **建议**: 需要全面对齐小程序 API 路径与实际后端路由。

#### 🟡 Major

**M-01: 后端缺少用户设备列表 API**
- **文件**: `app/api/users.py`, `app/api/devices.py`
- **描述**: 后端没有提供 `GET /api/v1/users/me/devices` 或类似端点来获取某用户绑定的所有设备列表。iOS/Android/小程序都期望有这样的接口。
- **建议**: 在 `users.py` 或 `devices.py` 中新增 `GET /api/v1/users/me/devices` 端点，查询 `user_devices` 表返回该用户绑定的设备列表。

**M-02: 后端 device_token 与 push_token 混用**
- **文件**: `app/mqtt_client.py` 第 276、323 行
- **描述**: MQTT 消息处理中，推送通知时传递的是 `device_id`（设备标识）而不是真正的 FCM/APNs push token。`app/push/__init__.py` 中的 `send_sos_push` 和 `send_low_battery_push` 接收到的 `device_token` 实为 `device_id`，这将导致 FCM/APNs 推送失败。
- **建议**: 在 `user_devices` 表或新增 `user_push_tokens` 表 中存储用户设备的 push token，并在推送时查询真正的 push token。

**M-03: 后端 users.py 中的 User model 重复定义**
- **文件**: `app/api/users.py` 第 67-80 行
- **描述**: `User` ORM model 在 `users.py` 中内联定义，而不是在 `app/db.py` 或 `app/models/` 中统一管理。这导致 model 定义分散。
- **建议**: 将 `User` 模型迁移到 `app/db.py`，与其他模型一致；或新建 `app/models/user.py`。

**M-04: 后端 `.dockerignore` 未排除 `.venv`**
- **文件**: `code/backend/.dockerignore`
- **描述**: Dockerfile 使用 multi-stage build，但 `.venv` 如果存在于根目录且未被 `.dockerignore` 排除，可能被 COPY 到 builder 镜像中。
- **建议**: 确认 `.dockerignore` 中包含 `.venv`。

**M-05: iOS 使用 `http://localhost:8000` 作为 base URL**
- **文件**: `code/ios/KeepSafe/Services/APIService.swift` 第 7 行
- **描述**: 在生产环境中应使用 HTTPS 和实际域名。iOS 不允许明文 HTTP 请求（需在 Info.plist 中配置 App Transport Security 例外）。
- **建议**: 添加生产/开发环境切换逻辑，生产环境使用 HTTPS。

#### 🟢 Minor

**m-01: 后端 app/__init__.py 和 api/__init__.py 为空文件**
- **文件**: `app/__init__.py`, `app/api/__init__.py`, `app/models/__init__.py`
- **描述**: 空 `__init__.py` 文件可以正常工作（标记包），无需修改。

**m-02: 后端 config.py 中 lbs_source 默认值问题**
- **文件**: `app/config.py` 第 85 行
- **描述**: `lbs_source: str = "opencellid"` — OpenCellID API 已经更名为 Unwired Labs，URL 也已更新为 `eu1.unwiredlabs.com`，代码中已经正确使用了新 URL，但配置名仍叫 `opencellid`。
- **建议**: 可考虑重命名为 `unwired` 以反映实际服务商。

### 1.3 Docker / 基础设施 ✅

| 项目 | 状态 |
|------|------|
| `Dockerfile` | ✅ multi-stage build，非 root 用户，健康检查 |
| `docker-compose.yml` | ✅ PostgreSQL 15 / Redis 7 / EMQX 5.7 / Backend |
| `requirements.txt` | ✅ 依赖完整 |
| `dbschema/init.sql` | ✅ TimescaleDB hypertable，数据保留策略，压缩策略 |

---

## 2. 固件

### 2.1 文件完整性

| 文件 | 状态 |
|------|------|
| `main.c` | ✅ 语法正确，状态机逻辑完整 |
| `mqtt.c` / `mqtt.h` | ✅ 语法正确，PSM 配置完整 |
| `gps.c` / `gps.h` | ✅ NMEA 解析器完整 |
| `lbs.c` / `lbs.h` | ✅ AT 命令解析完整 |
| `sos.c` / `sos.h` | ✅ SOS 状态机 + 电池 ADC |
| `power.c` / `power.h` | ✅ 电源状态机 (5 状态) |
| `led.c` / `led.h` | ✅ PWM 驱动完整 |
| `accel.c` / `accel.h` | ✅ LIS3DH I2C 驱动完整 |
| `config.h` | ✅ 全部配置项存在 |
| `sdkconfig` | ✅ 存在 (ESP-IDF 配置) |
| `CMakeLists.txt` | ✅ 正确 |

### 2.2 发现的问题

#### 🔴 Blocker

**B-05: 固件 low_battery JSON 字段名与后端不匹配**
- **文件**: `firmware/main/main.c` 第 397-398 行
- **描述**: `report_low_battery()` 中使用字段名 `\"bat\"` 和 `\"bat_mv\"`，但后端 MQTT handler (`mqtt_client.py` 第 285 行起) 只读取 `data.get(\"battery\", 0)`，从未读取 `\"bat\"`。后端将 battery 存储为 `null`。
- **建议**: 将固件的 low_battery JSON 中的 `bat` 改为 `battery`，`bat_mv` 改为 `voltage_mv` 或直接删除（后端未使用）。

**B-06: 固件 LBS JSON 中缺少 `type` 字段**
- **文件**: `firmware/main/main.c` 第 178-192 行
- **描述**: LBS 模式的 location JSON 中没有 `\"type\":\"location\"` 字段（第 178-192 行的 `build_location_json` LBS 分支缺少 `type` 字段）。后端 MQTT handler 的 `_on_message` 方法通过 `data.get(\"type\")` 分支消息，缺失 `type` 字段的消息会被识别为 `\"unknown\"` 并忽略。
- **建议**: 在 LBS JSON 中添加 `\"type\":\"location\"`。

**B-07: 固件 LBS JSON 字段名为 `bat` 而非 `battery`**
- **文件**: `firmware/main/main.c` 第 185 行
- **描述**: LBS 分支使用 `\"bat\":%u` 而 GPS 分支使用 `\"battery\":%u`（第 158 行）。后端统一读取 `data.get(\"battery\")`。
- **建议**: 统一为 `\"battery\"`。

#### 🟡 Major

**M-06: `power_enter_deep_sleep()` 后主循环仍会继续执行**
- **文件**: `firmware/main/main.c` 第 708 行
- **描述**: 主循环最后调用 `power_enter_deep_sleep()`，该函数标记为 `noreturn` 且调用 `esp_deep_sleep_start()`。但注释说 "does not return" 后仍有代码（第 711-714 行注释），这没问题但需要注意 `esp_deep_sleep_start()` 之前有 `vTaskDelay(50)` 和日志输出，如果 `vTaskDelay` 后还有任务切换可能有风险。实际行为正确，只是代码风格问题。
- **建议**: 无需修改，但可以添加 `while(1)` 等待或 `abort()` 作为安全防护。

**M-07: 固件 `sos_vibrate_feedback()` 使用阻塞延迟**
- **文件**: `firmware/main/sos.c` 第 238 行
- **描述**: `vTaskDelay(pdMS_TO_TICKS(duration_ms))` 是阻塞调用，在主循环中会阻塞 200ms。对于不频繁的 SOS 事件可以接受，但如果低电量时反复触发，可能导致主循环瞬间卡顿。
- **建议**: 可以保持当前实现（200ms 的阻塞对于电池寿命影响很小），或使用 timer 实现非阻塞控制。

**M-08: 固件 `main.c` LBS 模式的 JSON 缺少多个字段**
- **文件**: `firmware/main/main.c` 第 178-192 行
- **描述**: LBS location JSON 相比 GPS JSON 缺少 `source` 字段的一致性（LBS 分支有 `source` 但值为 `\"lbs\"`，GPS 分支有 `source` 值为 `\"gps\"`）。另外 LBS 分支没有 `charging`、`fw_version` 字段。后端期望这些字段存在（可选但推荐）。
- **建议**: 在 LBS JSON 中添加 `\"fw_version\"` 和 `\"charging\"` 字段以保持一致。

**M-09: APNs `close()` 方法使用 `await self._client.accept()` 错误**
- **文件**: `app/push/apns.py` 第 149 行
- **描述**: 应该使用 `await self._client.aclose()` 而不是 `await self._client.accept()`。`accept()` 是 ASGI 方法，httpx 中没有此方法。
- **建议**: 将 `_client.accept()` 改为 `_client.aclose()`。

**M-10: 后端 `apns.py` `_generate_token()` 硬编码 1h token**
- **文件**: `app/push/apns.py` 第 60-66 行
- **描述**: APNs provider token 生成中没有设置 `exp` 字段。虽然没有 `exp` 也是有效的（Apple 接受），但最佳实践是设置 1 小时过期时间并缓存 token。
- **建议**: 建议添加 `\"exp\": now + 3600` 到 JWT payload 中。

#### 🟢 Minor

**m-03: 固件 `main.c` 中 SOS 状态的 5 秒 `vTaskDelay`**
- **文件**: `firmware/main/main.c` 第 648 行
- **描述**: SOS 状态下 `vTaskDelay(pdMS_TO_TICKS(5000))` 硬编码 5 秒延迟。SOS 的预期间隔是 `INTERVAL_SOS_REPEAT_MS`（30秒），5秒检查频率合理。
- **建议**: 保持当前实现。

**m-04: 固件 `lbs.c` 中 `stristr` 函数未使用**
- **文件**: `firmware/main/lbs.c` 第 58 行
- **描述**: `stristr()` 函数已定义但未在 `lbs_parse_response()` 中被调用。所有字符串比较使用 `strstr`（大小写敏感），这对 AT 命令响应是安全的。
- **建议**: 可保留供将来使用，或删除。

---

## 3. iOS App

### 3.1 文件完整性

| 文件 | 状态 |
|------|------|
| `KeepSafeApp.swift` | ✅ 语法正确 |
| `ContentView.swift` | ✅ 语法正确 |
| `APIService.swift` | ✅ 语法正确 |
| `Models/Device.swift` | ✅ 语法正确 |
| `Models/User.swift` | ✅ 语法正确 |
| `Models/Alert.swift` | ✅ 语法正确 |
| `ViewModels/MapViewModel.swift` | ✅ 语法正确 |
| `ViewModels/AlertListViewModel.swift` | ✅ 语法正确 |

### 3.2 发现的问题

#### 🔴 Blocker

见 B-02（iOS API 端点与后端完全不匹配）

#### 🟡 Major

**M-11: iOS Device model 字段与后端不一致**
- **文件**: `code/ios/KeepSafe/Models/Device.swift`
- **描述**: iOS `Device` 包含 `id`、`name`、`deviceType`、`status`、`isConnected`、`isMoving` 等字段，后端返回的 `Device` 字段为 `device_id`、`device_token`、`fw_version`、`first_seen`、`last_seen`、`is_active`。两者字段定义完全不同。
- **建议**: 根据后端实际返回的 JSON 结构重新定义 iOS `Device` model。

**M-12: iOS DeviceLocation model 字段与后端不一致**
- **文件**: `code/ios/KeepSafe/Models/Device.swift` 第 76-85 行
- **描述**: iOS `DeviceLocation` 包含 `latitude`/`longitude`/`accuracy`/`timestamp`，后端 `LocationOut` 返回 `lat`/`lng`/`accuracy`/`ts`/`alt`/`speed` 等。iOS 直接将后端 `lat`/`lng` 映射到 `latitude`/`longitude` 会解析失败，因为后端字段名为 `lat`/`lng`。
- **建议**: 在 CodingKeys 中正确映射：`case latitude = "lat"`, `case longitude = "lng"`, `case timestamp = "ts"`。

**M-13: iOS Alert model 的 alert ID 类型不匹配**
- **文件**: `code/ios/KeepSafe/Models/Alert.swift` 第 6 行
- **描述**: iOS `Alert.id` 类型为 `String`，后端 `alerts` 表的 `id` 为自增 `Integer`。
- **建议**: 将 iOS `Alert.id` 类型改为 `Int`。

**M-14: iOS 推送注册端点未实现**
- **文件**: `code/ios/KeepSafe/Services/APIService.swift` 第 161-170 行
- **描述**: `registerPushToken()` 调用 `POST /user/push-token`，后端无此路由。应新增后端 push token 注册端点。
- **建议**: 后端新增 `POST /api/v1/users/me/push-token`，iOS 更新路径。

#### 🟢 Minor

**m-05: iOS ContentView 中 Tab icon 在选中/未选中状态下相同**
- **文件**: `code/ios/KeepSafe/ContentView.swift` 第 20-26 行
- **描述**: 除 alerts 外，其他 tab 的 `activeIcon` 和 `icon` 值相同，无法区分选中状态。

---

## 4. Android App

### 4.1 文件完整性

| 文件 | 状态 |
|------|------|
| `app/build.gradle.kts` | ✅ 配置完整 |
| `build.gradle.kts` (project) | ✅ 配置完整 |
| `ApiService.kt` | ✅ 语法正确 |
| `RetrofitClient.kt` | ✅ 语法正确 |
| `Models.kt` | ✅ 语法正确 |
| `KeepSafeRepository.kt` | ✅ 语法正确 |
| `NavGraph.kt` / `KeepSafeNavHost.kt` | ✅ 语法正确 |
| `MapScreen.kt` / `AlertScreen.kt` / `SettingsScreen.kt` | ✅ 语法正确 |
| `MainActivity.kt` | ✅ 语法正确 |

### 4.2 发现的问题

#### 🔴 Blocker

见 B-03（Android API 端点与后端完全不匹配）

#### 🟡 Major

**M-15: Android Device model 主键类型应为 String 而非 Long**
- **文件**: `code/android/app/src/main/java/com/keepsafe/app/data/model/Models.kt` 第 9 行
- **描述**: Android `Device.id` 类型为 `Long`，后端的 device_id 为 `VARCHAR(16)` 字符串类型（如 "KS-A1B2C3D4"）。
- **建议**: 将 `Device.id` 改为 `String` 类型。

**M-16: Android Alert model 的 deviceId 类型应为 String 而非 Long**
- **文件**: `code/android/app/src/main/java/com/keepsafe/app/data/model/Models.kt` 第 46 行
- **描述**: `Alert.deviceId` 类型为 `Long`，后端 device_id 为字符串。
- **建议**: 改为 `String` 类型。

**M-17: Android UserProfile model 字段与后端不一致**
- **文件**: `code/android/app/src/main/java/com/keepsafe/app/data/model/Models.kt` 第 66-77 行
- **描述**: Android `UserProfile` 使用 `id` (Long)、`username`、`email`、`phone`、`avatarUrl`。后端 `UserProfileOut` 返回 `user_id` (String)、`email`、`nickname`、`avatar_url`、`phone`、`created_at`。
- **建议**: 使用 `@SerializedName("user_id")` 映射 id 字段，将 `username` 改为 `nickname`。

**M-18: Android LocationData 字段与后端不匹配**
- **文件**: `code/android/app/src/main/java/com/keepsafe/app/data/model/Models.kt` 第 28-37 行
- **描述**: 与 iOS 同样的问题 — `latitude`/`longitude` 对应后端 `lat`/`lng`，缺少 `@SerializedName` 映射。
- **建议**: 添加 `@SerializedName("lat")` 和 `@SerializedName("lng")`。

#### 🟢 Minor

**m-06: Android 缺少 proguard-rules.pro 文件**
- **文件**: `app/build.gradle.kts` 第 27 行引用了 `proguard-rules.pro`
- **描述**: release 构建引用了 proguard 规则文件，但该文件可能不存在（未在文件列表中找到）。
- **建议**: 创建空文件或移除引用。

---

## 5. 微信小程序

### 5.1 文件完整性

| 文件 | 状态 |
|------|------|
| `app.json` | ✅ 配置完整 |
| `app.js` | ✅ 语法正确 |
| `utils/api.js` | ✅ 语法正确 |
| `pages/index/index.*` | ✅ 文件完整 |
| `pages/alerts/alert.*` | ✅ 文件完整 |
| `pages/profile/profile.*` | ✅ 文件完整 |
| `components/device-card/*` | ✅ 文件完整 |
| `components/fence-picker/*` | ✅ 文件完整 |

### 5.2 发现的问题

#### 🔴 Blocker

见 B-04（小程序 API 端点与后端完全不匹配）

#### 🟡 Major

**M-19: 小程序 wxLogin 调用 `/auth/wx-login`，后端无此端点**
- **文件**: `code/miniapp/utils/api.js` 第 219 行
- **描述**: 小程序期望微信登录端点 `POST /api/v1/auth/wx-login`，后端只支持 `POST /api/v1/auth/device`（设备认证）。缺少用户微信登录/注册流程。
- **建议**: 后端新增微信登录端点，或小程序改用后端现有的用户注册/登录流程。

**M-20: app.js `silentLogin` 调用 `/auth/verify` 端点不存在**
- **文件**: `code/miniapp/app.js` 第 34 行
- **描述**: `GET /api/v1/auth/verify` 在后端不存在。后端有 `GET /api/v1/users/profile` 可用于验证 token 有效性。
- **建议**: 改为调用 `/api/v1/users/profile` 验证 token。

**M-21: 小程序 `getShareLink` 端点不存在**
- **文件**: `code/miniapp/utils/api.js` 第 207-208 行
- **描述**: `POST /api/v1/share` 在后端不存在。
- **建议**: 确定是否需要该功能，如果需要则在后端实现。

---

## 6. 硬件

### 6.1 文件完整性

| 文件 | 状态 |
|------|------|
| `keepsafe_body.scad` | ✅ 存在且语法正确 |
| `keepsafe_internal_layout.scad` | ✅ 存在且语法正确 |
| `render_stl.sh` | ✅ 存在 |
| `BATTERY_CHECK.md` | ✅ 存在 |

### 6.2 发现的问题

无严重问题。OpenSCAD 文件语法正确，尺寸参数合理（78x48x12mm），内部堆叠布局清晰（电池 703048 / PCB / 天线 / 喇叭 / SOS 键 / 振动马达）。

#### 🟢 Minor

**m-07: 内部布局中备选电池 603048 使用了未定义的变量**
- **文件**: `code/hardware/keepsafe_internal_layout.scad` 第 128 行
- **描述**: `battery_603048()` 模块中使用了 `bat_alt_len` 变量，但该变量未在全局定义。如果该模块被渲染将出错，但目前该模块仅用于可视化对比且可能不会真正渲染。
- **建议**: 定义 `bat_alt_len = 48` 或确保该模块不渲染。

---

## 7. 跨模块数据一致性

### 7.1 MQTT JSON 数据格式一致性

| 字段 | 固件 GPS JSON | 固件 LBS JSON | 固件 Heartbeat | 固件 SOS | 固件 Low Battery | 后端期望 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| `type` | ✅ `"location"` | 🔴 缺失 | ✅ `"heartbeat"` | ✅ `"sos"` | ✅ `"low_battery"` | ⚠️ 需要 |
| `device_id` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `ts` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `lat` / `lng` | ✅ | ✅ (0) | - | ✅ | - | ✅ |
| `battery` | ✅ | 🔴 `bat` | ✅ | ✅ | 🔴 `bat` | ✅ `battery` |
| `charging` | ✅ (false) | 🔴 缺失 | ✅ (false) | - | - | ✅ |
| `rssi` | ✅ (0) | ✅ | ✅ (0) | - | - | ✅ |
| `cell_id` | ✅ (空) | ✅ | - | - | - | ✅ |
| `fw_version` | - | 🔴 缺失 | ✅ | - | - | ✅ |
| `source` | ✅ `"gps"` | ✅ `"lbs"` | - | - | - | ⚠️ 可用 |
| `alt` / `speed` / `heading` / `accuracy` / `satellites` / `fix_type` | ✅ | 🔴 缺失 | - | - | - | ✅ |

### 7.2 REST API 端点一致性

| 端点 | 后端 | iOS | Android | 小程序 |
|------|:---:|:---:|:---:|:---:|
| `GET /health` | ✅ | - | - | - |
| `POST /api/v1/auth/device` | ✅ | - | - | - |
| `GET /api/v1/auth/device/acl` | ✅ | - | - | - |
| `POST /api/v1/users/register` | ✅ | - | - | - |
| `POST /api/v1/users/login` | ✅ | - | - | - |
| `GET /api/v1/users/profile` | ✅ | 🔴 `/user/profile` | 🔴 `/profile/` | 🔴 `/user/profile` |
| `PUT /api/v1/users/profile` | ✅ | 🔴 `/user/profile` | 🔴 `/profile/` | 🔴 `/user/profile` |
| `GET /api/v1/devices/{id}/location` | ✅ | 🔴 `/devices/{id}/location` | 🔴 格式 | ✅ |
| `GET /api/v1/devices/{id}/status` | ✅ | - | - | - |
| `GET /api/v1/devices/{id}/history` | ✅ | - | - | 🔴 路径错误 |
| `GET /api/v1/devices/{id}/sos/events` | ✅ | - | - | - |
| `POST /api/v1/devices/bind` | ✅ | ✅ `/devices/bind` | - | ✅ `/devices/bind` |
| `DELETE /api/v1/devices/{id}/bind` | ✅ | 🔴 POST `/devices/{id}/unbind` | - | ✅ |
| `GET /api/v1/devices/{id}/fences/` | ✅ | - | - | ✅ |
| `POST /api/v1/devices/{id}/fences/` | ✅ | - | - | ✅ |
| `GET /api/v1/devices/{id}/fences/{fid}` | ✅ | - | - | ✅ |
| `PUT /api/v1/devices/{id}/fences/{fid}` | ✅ | - | - | ✅ |
| `DELETE /api/v1/devices/{id}/fences/{fid}` | ✅ | - | - | ✅ |
| `GET /api/v1/alerts` | 🔴 缺失 | 🔴 `/alerts` | 🔴 `/alerts/` | 🔴 `/alerts` |
| `PUT /api/v1/alerts/{id}/read` | 🔴 缺失 | 🔴 `/alerts/{id}/read` | 🔴 `/alerts/{id}/read/` | 🔴 `/alerts/{id}/read` |
| `GET /devices` (list) | 🔴 缺失 | 🔴 `/devices` | 🔴 `/devices/` | 🔴 `/devices` |

---

## 8. 总结 & 优先级建议

### 问题统计

| 级别 | 后端 | 固件 | iOS | Android | 小程序 | 硬件 | 合计 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 🔴 Blocker | 2 | 3 | 1 | 1 | 1 | 0 | **8** |
| 🟡 Major | 4 | 3 | 4 | 4 | 3 | 0 | **18** |
| 🟢 Minor | 2 | 2 | 1 | 1 | 0 | 1 | **7** |
| **合计** | **8** | **8** | **6** | **6** | **4** | **1** | **33** |

### 核心问题

1. **API 端点全面不匹配**: iOS、Android、小程序三个客户端都与后端实际路由定义不一致。这是最严重的系统性问题，需要统一协调。
2. **固件 JSON 字段名不统一**: `bat` vs `battery` 错误导致低电量数据和 LBS 位置数据无法被后端正确解析。
3. **后端缺少 alert 列表 API**: 所有客户端都期望的告警列表端点未实现。
4. **固件 LBS JSON 缺少 `type` 字段**: 导致 LBS 位置消息被后端丢弃。

### 建议修复顺序

1. **第一优先（Blocker）**: 统一固件 JSON 字段名（B-05, B-06, B-07），修复后端 alert API 缺失（B-01）
2. **第二优先（Major）**: 重新设计客户端 API 对齐层（单次修改所有客户端路径与后端一致，B-02, B-03, B-04）
3. **第三优先（Major）**: 修复推送 token 机制（M-02）、APNs close bug（M-09）
4. **第四优先（Minor）**: 统一 model 字段映射，清理未使用代码

---

*报告由 Hermes Agent 自动生成*

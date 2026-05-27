# 开发方案：KEEP-001 — 定位器结构设计与固件基座（v1.1）

> 项目：KeepSafe 防丢器
> 方案编号：KEEP-001
> 版本：v1.1
> 更新内容：根据架构评审 + 老板决策修正：主控选型、电池升级、加速度计、结构工程师分拆
> 编写人：PM（Hermes Agent）
> 状态：待审批

---

## 1. 需求概述

基于老板提供的外观结构规格，完成 KeepSafe 定位器第一轮开发：
1. 结构外观 STL 模型（结构工程师负责）
2. 固件框架搭建：GPS 定位 + 4G 通信 + 心跳上报 + 省电策略
3. 后端基础位置接收服务

---

## 2. 决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| **主控方案** | ESP32-S3 + Air780E（4G+GNSS 单片） | 生态成熟、自带 BLE、调试方便 |
| **电池** | 703048（800mAh，7mm 厚）+ 603048（600mAh）备选 | 12mm 外壳有 1.3mm 余量 |
| **续航策略** | 动态频率（运动 5min/次，静止 GPS 关闭+LBS 30min/次）| 可达 ≥ 7 天 |
| **加速度计** | 新增 LIS3DH（¥2-3） | 续航翻倍，运动唤醒省电 |
| **4G 省电** | PSM 深度睡眠（3~5μA） | 大幅降低待机功耗 |
| **结构建模** | 由 Mech-Dev（结构工程师）独立负责 | Emb-Dev 专注固件 |

---

## 3. 技术方案

### 3.1 整体架构（更新版，含架构评审意见）

```
┌─────────────────────────────────────────────────────┐
│                定位器硬件 (ESP32-S3)                   │
│  ┌─────────┐  ┌──────────────────────┐               │
│  │ GPS Ant │  │  Air780E (4G+GNSS)   │               │
│  │ (陶瓷)  │  │  ┌────────────────┐  │               │
│  └────┬────┘  │  │  GNSS NMEA     │  │               │
│       │       │  │  AGPS 星历辅助 │  │               │
│       ▼       │  │  4G MQTT PSM   │  │               │
│  ┌─────────┐  │  └────────────────┘  │               │
│  │ ESP32-S3 │  └──────────┬───────────┘               │
│  │  · NMEA  │             │ UART                      │
│  │  · MQTT  │◄────────────┘                           │
│  │  · LED   │  ┌────────┐  ┌──────────┐               │
│  │  · SOS   │  │ BLE 5.0│  │ LIS3DH   │               │
│  │  · I2C   │  │ (预留)  │  │ 加速度计 │               │
│  │  · 深睡  │  └────────┘  │ 运动唤醒  │               │
│  └──────────┘              └──────────┘               │
│   ┌──────────────────────┐                            │
│   │  703048 800mAh 锂电池  │  7mm ≤ 8.3mm 可用余量   │
│   │  (备选: 603048 600mAh)│                            │
│   └──────────────────────┘                            │
└─────────────────────┬─────────────────────────────────┘
                      │ MQTT over LTE Cat.1 (TLS 1.3)
                      ▼
┌─────────────────────────────────────────────────────────┐
│              后端服务集群                                  │
│  ┌─────────────────────────────────────────────────┐   │
│  │            EMQX Cluster                          │   │
│  │  topics:                                         │   │
│  │  keepsafe/v1/{id}/location    [QoS 1]            │   │
│  │  keepsafe/v1/{id}/heartbeat   [QoS 0]            │   │
│  │  keepsafe/v1/{id}/sos         [QoS 1]            │   │
│  │  keepsafe/v1/{id}/alert/*     [QoS 1]            │   │
│  │  keepsafe/v1/{id}/cmd/*       [下行]             │   │
│  └────────────────┬────────────────────────────────┘   │
│                   │                                     │
│  ┌────────────────▼────────────────────────────────┐   │
│  │         FastAPI (位置接收服务)                     │   │
│  │  · MQTT 订阅消费                                │   │
│  │  · 位置写入 TimescaleDB                          │   │
│  │  · 缓存最新位置到 Redis                          │   │
│  │  · SOS 推送到 FCM/APNs                          │   │
│  └────────────────┬────────────────────────────────┘   │
│                   │                                     │
│  ┌────────────────▼────────────────────────────────┐   │
│  │         TimescaleDB + PostgreSQL                  │   │
│  │  · locations (Hypertable, 按天分区)               │   │
│  │  · sos_events                                    │   │
│  │  · devices (设备信息+认证)                        │   │
│  │  · users_accounts                                │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────┐  ┌───────────────────┐           │
│  │  Redis Cache    │  │  LBS 基站位置解析  │           │
│  │  · 设备在线状态  │  │  (OpenCellID)     │           │
│  │  · 最新位置缓存  │  └───────────────────┘           │
│  └─────────────────┘                                   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  REST API (供 App 消费)                          │   │
│  │  GET  /api/v1/devices/{id}/location             │   │
│  │  GET  /api/v1/devices/{id}/status               │   │
│  │  GET  /api/v1/devices/{id}/history              │   │
│  │  GET  /api/v1/devices/{id}/sos/events           │   │
│  │  POST /api/v1/devices/bind                      │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3.2 技术选型（更新确认版）

| 层级 | 方案 | 理由 |
|------|------|------|
| 主控芯片 | **ESP32-S3** | 双核 LX7、BLE 5.0、深度睡眠 5~10μA |
| 4G+GNSS 模组 | **Air780E**（合宙） | 单片 4G Cat.1 + GNSS，支持 PSM 3~5μA |
| 加速度计 | **LIS3DH** | 2~10μA 工作电流，运动中断唤醒 |
| 通信协议 | MQTT QoS 1（位置/SOS）/ QoS 0（心跳）| 物联网标准 |
| 定位协议 | NMEA-0183 + AGPS 星历辅助 | 热启动 5s |
| 后端 | Python FastAPI | 异步高吞吐 |
| 数据库 | TimescaleDB + PostgreSQL | 时序位置存储 |
| 缓存 | Redis | 设备在线状态 + 最新位置缓存 |
| MQTT Broker | **EMQX** | 企业级，内置设备认证 |
| 推送 | Firebase Cloud Messaging + APNs | 告警推送 |
| 3D 建模 | OpenSCAD（结构工程师） | 参数化快速迭代 |
| 电池 | **703048（800mAh，7mm）** | 备选 603048（600mAh）|

### 3.3 省电策略

详见 KEEP-001-BATTERY-OPT.md 完整方案，核心参数：

| 状态 | GPS | 定位方式 | 上报频率 | 4G 状态 |
|------|-----|---------|---------|---------|
| 静止 | 关闭 | LBS 基站 | 30min/次 | PSM 3~5μA |
| 运动中 | 开启（热启动 5s）| GPS + LBS | 5min/次 | 上报后 PSM |
| SOS | 强制开启 | GPS 连续 | 实时 3s/次 | 持续在线 |
| MCU | 深度睡眠 8μA，加速度计中断唤醒 | | | |

### 3.4 JSON Payload 定义（固化后不可随意改）

**位置上报（topic: keepsafe/v1/{device_id}/location）**
```json
{
  "type": "location",
  "device_id": "KS-xxxxxxxx",
  "ts": 1700000000,
  "lat": 39.9042,
  "lng": 116.4074,
  "alt": 52,
  "speed": 0.5,
  "heading": 180,
  "accuracy": 8,
  "satellites": 12,
  "fix_type": 3,
  "cell_id": "460-00-12345-6789",
  "battery": 85,
  "charging": false,
  "rssi": -65,
  "fw_version": "1.0.0"
}
```

**心跳（topic: keepsafe/v1/{device_id}/heartbeat）**
```json
{
  "type": "heartbeat",
  "device_id": "KS-xxxxxxxx",
  "ts": 1700000060,
  "battery": 84,
  "charging": false,
  "rssi": -68,
  "uptime": 3600,
  "online": true
}
```

**SOS 紧急上报（topic: keepsafe/v1/{device_id}/sos）**
```json
{
  "type": "sos",
  "device_id": "KS-xxxxxxxx",
  "ts": 1700000100,
  "lat": 39.9042,
  "lng": 116.4074,
  "accuracy": 10,
  "battery": 75,
  "trigger_duration_ms": 3200
}
```

**低电告警（topic: keepsafe/v1/{device_id}/alert/low_battery）**
```json
{
  "type": "low_battery",
  "device_id": "KS-xxxxxxxx",
  "ts": 1700000200,
  "battery": 19,
  "charging": false,
  "lat": 39.9042,
  "lng": 116.4074
}
```

---

## 4. 任务拆分（更新版）

| # | 任务 | 预估工时 | 角色 | 依赖 | 说明 |
|---|------|---------|------|------|------|
| 1 | 结构 3D 模型（OpenSCAD STL）| **6h** | **Mech-Dev** | - | 基于规格参数化建模 + 内部堆叠布局（703048 电池位）|
| 2 | 电池续航评估 + 703048 选型确认 | 2h | Mech-Dev | - | 确认电池位、厚度余量、保护板位置 |
| 3 | 固件：GPS NMEA 解析 + 坐标提取 | 6h | Emb-Dev | - | 串口读 Air780E GNSS NMEA 数据，提取经纬度 |
| 4 | 固件：LBS Cell ID 获取 | 2h | Emb-Dev | 5 | 从 4G 模组获取基站信息 |
| 5 | 固件：MQTT 通信 + PSM 省电 | 6h | Emb-Dev | 3 | EMQX 连接、PSM 配置、断线重连（指数退避）|
| 6 | 固件：LED 状态指示 | 2h | Emb-Dev | - | 联网蓝灯、定位绿灯、低电红灯 |
| 7 | 固件：SOS 按键 + 低电量检测 | 4h | Emb-Dev | 5 | 长按 3s SOS、电量读取、低电 ≤20% 告警 |
| 8 | 固件：电源管理 + 动态定位频率 | 6h | Emb-Dev | 3+4 | 运动/静止状态机、GPS 电源控制、深度睡眠 |
| 9 | 固件：加速度计 LIS3DH 驱动 + 运动唤醒 | 4h | Emb-Dev | - | I2C 驱动、运动中断、唤醒 MCU |
| 10 | 后端：EMQX 搭建 + 设备认证 | 4h | BE-Dev | - | EMQX + Auth HTTP API + 一机一密 |
| 11 | 后端：位置接收 + TimescaleDB 时序存储 | 4h | BE-Dev | 10 | MQTT 消费 5 个 topic → 按天分区入库 |
| 12 | 后端：Redis 设备状态缓存 | 2h | BE-Dev | 11 | 在线状态、最新位置缓存 |
| 13 | 后端：设备状态 REST API | 3h | BE-Dev | 11+12 | location / status / history / sos/events |
| 14 | 后端：LBS 基站位置解析 | 4h | BE-Dev | 11 | OpenCellID API 对接 |
| 15 | 后端：推送服务（FCM/APNs）| 4h | BE-Dev | 11 | SOS 和低电告警推送通道 |
| 16 | QA：GPS 数据流端到端测试 | 4h | QA | 3+5+11 | 固件→EMQX→后端→API 全链路 |
| 17 | QA：SOS 事件 + 推送验证 | 3h | QA | 7+15 | 按键→上报→推送到达 |
| 18 | QA：省电策略续航验证 | 4h | QA | 8+9 | 不同场景功耗实测 |
| 19 | Reviewer：固件代码审查 | 4h | Reviewer | 3-9 | 安全、功耗、规范 |
| 20 | Reviewer：后端代码审查 | 3h | Reviewer | 10-15 | 安全、注入、规范 |

---

## 5. 验收标准（更新版）

| # | 验收项 | 标准 |
|---|--------|------|
| AC-1 | 3D 模型 | STL 尺寸与规格一致，703048 电池位正确 |
| AC-2 | GPS 定位 | 室外热启动 ≤ 10s，精度 ≤ 10m |
| AC-3 | LBS 定位 | 无 GPS 信号时返回基站估算位置 |
| AC-4 | MQTT 上报 | 公网上报延迟 ≤ 3s，后端正确入库 |
| AC-5 | PSM 省电 | 待机电流 ≤ 10μA |
| AC-6 | 动态频率 | 静止时 GPS 关闭、30min/次 LBS → 运动时恢复 GPS 5min/次 |
| AC-7 | 加速度计 | 运动检测正确触发状态切换 |
| AC-8 | SOS | 长按 3s 上报 + 推送到达，端到端 ≤ 8s |
| AC-9 | 低电告警 | 电量 ≤ 20% 触发上报 + 推送 |
| AC-10 | LED 指示 | 三种状态指示正确 |
| AC-11 | 续航 | ≥ 7 天（168h），按每日 30% 运动 70% 静止实测 |
| AC-12 | 后端 API | 5 个端点返回正确数据 |
| AC-13 | 推送 | FCM/APNs 推送延迟 ≤ 5s |

---

## 6. 密钥点位

| 位置 | 占位符 | 说明 |
|------|--------|------|
| 后端 .env | `{{PLACEHOLDER_EMQX_PASSWORD}}` | EMQX 管理员密码 |
| 后端 .env | `{{PLACEHOLDER_DB_PASSWORD}}` | TimescaleDB 密码 |
| 后端 .env | `{{PLACEHOLDER_JWT_SECRET}}` | JWT 签名密钥 |
| 后端 .env | `{{PLACEHOLDER_FCM_KEY}}` | Firebase 服务端密钥 |
| 后端 .env | `{{PLACEHOLDER_APNS_KEY}}` | APNs 密钥 |
| 固件配置 | `{{PLACEHOLDER_MQTT_HOST}}` | EMQX 服务器地址 |
| 固件配置 | `{{PLACEHOLDER_APN_NAME}}` | 4G SIM 卡 APN |

> 上述占位符将在后续由你亲自填入真实值。Agent 无权接触。

---

## 7. 风险与注意事项

- ⚠️ 703048（7mm）电池装入 12mm 外壳，需确认顶部缓冲泡棉厚度
- ⚠️ 天线位置——左上区陶瓷天线远离挂耳金属件，挂耳确认塑胶材质
- ⚠️ ESP32-S3 与 Air780E UART 通信波特率需提前确认
- ⚠️ MQTT PSM 配置需要运营商网络支持（Cat.1 均支持）
- ⚠️ 推送通道需 Firebase 和 Apple 开发者账号，提前准备
- ⚠️ 所有密钥以 `{{PLACEHOLDER}}` 形式出现，由你亲手填入

---

## 8. 总工时预估

| 角色 | 工时 |
|------|------|
| Mech-Dev（结构工程师）| 8h |
| Emb-Dev（嵌入式开发）| 30h |
| BE-Dev（后端开发）| 21h |
| QA（测试）| 11h |
| Reviewer（代码审查）| 7h |
| **合计** | **77h** |

---

*编写：PM v1.1 | 审批人：老板（你） | 审批后并行开干*

# MQTT Topic 映射表: DTU格式 → KeepSafe后端格式

> Version: v1.0
> Date: 2026-06-10
> Platform: YED DTU3 (EC718P-M100PG) → KeepSafe Backend (EMQX @ 43.163.5.90:1883)

---

## 一、映射总览

YED DTU3 默认使用 DTU JSON 透传协议，topic 格式与 KeepSafe 后端不同。
本文档定义两种 topic 格式之间的映射关系。

| DTU 默认 Topic | KeepSafe 后端 Topic | QoS | 说明 |
|---------------|-------------------|-----|------|
| `dtu/{device_id}/data` | `keepsafe/v1/{device_id}/location` | 1 | GPS定位数据上报 |
| `dtu/{device_id}/heart` | `keepsafe/v1/{device_id}/heartbeat` | 0 | 设备心跳 |
| `dtu/{device_id}/alarm` | `keepsafe/v1/{device_id}/sos` | 1 | SOS告警 |
| `dtu/{device_id}/lowbatt` | `keepsafe/v1/{device_id}/alert/low_battery` | 1 | 低电量告警 |
| `dtu/{device_id}/cmd` | `keepsafe/v1/{device_id}/cmd` | 0 | 下行指令 (不变) |
| `dtu/{device_id}/version` | `keepsafe/v1/{device_id}/version` | 0 | 固件版本上报 |

---

## 二、JSON Payload 字段映射

### 2.1 位置上报 (location)

DTU格式 (EC718P DTU默认JSON):
```json
{
  "imei": "869234050000001",
  "ts": 1718000000,
  "lat": 22.5431,
  "lng": 113.9346,
  "alt": 15.0,
  "spd": 1.8,
  "sat": 12,
  "hdop": 0.9,
  "bat": 85,
  "rssi": 25,
  "cell": "46001,ABCD,1234"
}
```

KeepSafe后端格式 (normalize后):
```json
{
  "device_id": "KS-XXXXXXXX",
  "fw_version": "2.0.0",
  "ts": 1718000000,
  "lat": 22.5431,
  "lng": 113.9346,
  "alt": 15.0,
  "speed": 1.8,
  "satellites": 12,
  "hdop": 0.9,
  "battery": 85,
  "rssi": 25,
  "cell_id": "46001,ABCD,1234"
}
```

字段映射规则:
| DTU字段 | 后端字段 | 转换 |
|--------|---------|------|
| `imei` | `device_id` | IMEI → device_id lookup |
| `ts` | `ts` | 直接传递 |
| `lat` | `lat` | 直接传递 |
| `lng` | `lng` | 直接传递 |
| `alt` | `alt` | 直接传递 |
| `spd` | `speed` | 直接传递 (m/s) |
| `sat` | `satellites` | 直接传递 |
| `hdop` | `hdop` | 直接传递 |
| `bat` | `battery` | 直接传递 (0-100%) |
| `rssi` | `rssi` | 直接传递 (0-31) |
| `cell` | `cell_id` | 直接传递 |

### 2.2 心跳 (heartbeat)

DTU格式:
```json
{
  "imei": "869234050000001",
  "ts": 1718000000,
  "state": 0,
  "bat": 90,
  "rssi": 22
}
```

KeepSafe后端:
```json
{
  "device_id": "KS-XXXXXXXX",
  "fw_version": "2.0.0",
  "ts": 1718000000,
  "state": "STATIONARY",
  "battery": 90,
  "rssi": 22
}
```

状态映射: DTU state (0/1/2/3) → KeepSafe state ("STATIONARY"/"MOVING"/"JUST_STOPPED"/"SOS_ACTIVE")

### 2.3 SOS告警 (sos)

DTU格式:
```json
{
  "imei": "869234050000001",
  "ts": 1718000000,
  "lat": 22.5431,
  "lng": 113.9346,
  "bat": 80,
  "type": 1
}
```

KeepSafe后端:
```json
{
  "device_id": "KS-XXXXXXXX",
  "fw_version": "2.0.0",
  "ts": 1718000000,
  "alert": "sos",
  "lat": 22.5431,
  "lng": 113.9346,
  "battery": 80
}
```

### 2.4 低电量告警 (low_battery)

DTU格式:
```json
{
  "imei": "869234050000001",
  "ts": 1718000000,
  "bat": 15,
  "threshold": 20
}
```

KeepSafe后端:
```json
{
  "device_id": "KS-XXXXXXXX",
  "fw_version": "2.0.0",
  "ts": 1718000000,
  "alert": "low_battery",
  "battery": 15,
  "threshold": 20
}
```

---

## 三、适配方式

### 方案A: 后端适配 (推荐快速验证)

在 `mqtt_client.py` 中增加 DTU topic 订阅和 payload 转换：

```python
# 后端新增订阅 DTU 默认 topic
client.subscribe("dtu/+/data", qos=1)
client.subscribe("dtu/+/heart", qos=0)
client.subscribe("dtu/+/alarm", qos=1)
client.subscribe("dtu/+/lowbatt", qos=1)

# _on_message 中增加 topic 路由:
if topic.startswith("dtu/"):
    data = _normalize_dtu_payload(topic, data)
```

IMEI → device_id 映射表 (Redis):
```
dtu_imei:869234050000001 → KS-XXXXXXXX
```

### 方案B: 前端适配 (推荐生产)

在 DTU 固件 (LuatOS) 中直接使用 KeepSafe topic 格式，
修改 `config.lua` MQTT topic 配置即可，payload 保持 KeepSafe 格式。

```lua
-- config.lua (已配置为KeepSafe格式)
CONFIG.TOPIC_LOCATION   = string.format("keepsafe/v1/%s/location", CONFIG.DEVICE_ID)
CONFIG.TOPIC_HEARTBEAT  = string.format("keepsafe/v1/%s/heartbeat", CONFIG.DEVICE_ID)
```

### 方案C: EMQX Rule Engine 桥接

在 EMQX 中配置规则引擎，自动完成 topic 重写和 payload 转换，
无需固件或后端改动。

```sql
-- EMQX Rule SQL
SELECT 
  payload.imei as device_id,
  payload.ts as ts,
  payload.lat as lat,
  payload.lng as lng,
  payload.spd as speed,
  payload.bat as battery
FROM "dtu/+/data"
```

---

## 四、实现状态

- [x] Topic 映射定义完成
- [ ] 后端 `_normalize_dtu_payload()` 函数实现
- [ ] IMEI → device_id Redis 映射表初始化
- [ ] EMQX Rule Engine 备选方案验证
- [ ] DTU 固件 topic 配置切换为方案B

---

*本文档在 DTU 协议适配完成后更新为最终方案。*

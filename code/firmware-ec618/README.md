# KeepSafe 固件 (Air780EG / EC618 + LuatOS)

> Platform: 合宙 Air780EG (EC618 内核)  
> OS: LuatOS-SoC (出厂预装)  
> Chip: EC618 (移芯 Cat.1 bis, 内置 GNSS)  
> Status: 固件开发中 — 等待 Air780EG 开发板到货烧录验证  
> Date: 2026-06-13

---

## 目录结构

```
firmware-ec618/
├── README.md              # 本文件
├── luatos/                # LuatOS 固件 (Air780EG 原生方案)
│   ├── main.lua           # 主入口 + 状态机 + SOS + JSON 构建
│   ├── config.lua         # 全局配置 (MQTT/GPS/GPIO/PSM/间隔)
│   ├── mqtt.lua           # MQTT 客户端 (指数退避/断路器/健康检查)
│   ├── gps.lua            # GNSS 定位 (AT+CGNSINF 解析)
│   ├── psm.lua            # PSM 省电 (3GPP 深度睡眠 <20µA)
│   ├── accel.lua          # LIS3DH 加速度计 (I2C, 运动检测)
│   ├── battery.lua        # 电池电压/百分比 (ADC0, LiPo 放电曲线)
│   └── led.lua            # LED 状态指示 (STATUS + NET)
├── at-scripts/            # AT 指令工具 (验证/调试用)
│   └── mqtt_at.py         # MQTT AT 指令端到端测试脚本
└── shared/                # 共享参考文件
```

## 模块架构

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  accel   │   │   gps    │   │ battery  │   │   led    │
│ LIS3DH   │   │  GNSS    │   │  ADC0    │   │ GPIO24/27│
└────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
     │              │              │              │
     └──────────────┼──────────────┼──────────────┘
                    │              │
               ┌────┴──────────────┴─────┐
               │       main.lua          │
               │    State Machine        │
               └────────────┬────────────┘
                            │
               ┌────────────┴────────────┐
               │         mqtt            │
               │    EMQX @ VPS:1883      │
               └────────────┬────────────┘
                            │
               ┌────────────┴────────────┐
               │         psm             │
               │  Deep Sleep <20µA       │
               └─────────────────────────┘
```

## 状态机

```
INIT → STATIONARY ←→ MOVING
          ↓              ↓
     JUST_STOPPED   SOS_ACTIVE (可从任意状态进入)
```

| 状态 | 上报间隔 | LED | PSM | 说明 |
|------|---------|-----|-----|------|
| INIT | - | 慢闪 | 关 | 初始化中 |
| STATIONARY | 30min | 呼吸 | 开 | 静止省电 |
| MOVING | 5min | 慢闪 | 关 | 运动中 |
| JUST_STOPPED | 30min | 呼吸 | 开 | 刚停止(过渡态) |
| SOS_ACTIVE | 30s | 快闪 | 关 | 紧急求救 |

## MQTT Topic

| Topic | QoS | 用途 |
|-------|-----|------|
| `keepsafe/v1/{id}/location` | 1 | GPS 位置上报 |
| `keepsafe/v1/{id}/heartbeat` | 0 | 心跳 |
| `keepsafe/v1/{id}/sos` | 1 | SOS 紧急告警 |
| `keepsafe/v1/{id}/alert/low_battery` | 1 | 低电量告警 |

## 功耗预估

| 模式 | 电流 | 说明 |
|------|------|------|
| Active (4G TX) | ~200-500mA | MQTT 发布中 |
| Idle (4G RX) | ~10-20mA | 网络待机 |
| eDRX | ~1-2mA | 扩展非连续接收 |
| PSM Deep Sleep | <20µA | 深度睡眠 |

200mAh 电池 + 30min 静止上报 → 预估续航 **3-6 个月**

## 快速开始

### 1. 硬件准备
- 合宙 Air780EG 开发板 ×1
- 4G 天线 (IPEX-1)
- GNSS 有源天线 (IPEX-1)
- IoT SIM 卡 (已激活)
- USB Type-C 数据线

### 2. 烧录固件
```bash
# 使用合宙 Luatools 工具
# 1. 下载: https://wiki.luatos.com/pages/tools.html
# 2. 连接开发板 (Type-C)
# 3. 选择 luatos/ 目录下所有 .lua 文件
# 4. 点击"下载脚本"

# 或使用 LuatOS 命令行工具
luatos-soc --port /dev/cu.usbmodemXXXX download luatos/*.lua
```

### 3. 验证
```bash
# 串口监控 (115200 8N1)
screen /dev/cu.usbmodemXXXX 115200

# 预期日志:
# KeepSafe DTU v2.1.0
# Device: KS-PROTO-001
# Platform: Air780EG (EC618)
# ...
# MQTT Connected
# Published location
```

### 4. AT 指令调试 (可选)
```bash
python3 at-scripts/mqtt_at.py --port /dev/cu.usbmodemXXXX
```

## 从 ESP32-S3 迁移记录

| 旧模块 (C) | 新模块 (Lua) | 状态 |
|-----------|-------------|------|
| main.c | main.lua | ✅ 已迁移 |
| config.h | config.lua | ✅ 已迁移 |
| mqtt.c/mqtt.h | mqtt.lua | ✅ 已迁移 |
| gps.c/gps.h | gps.lua | ✅ 已迁移 |
| (新) | psm.lua | ✅ 已实现 |
| accel.c/accel.h | accel.lua | ✅ 已迁移 |
| (新) | battery.lua | ✅ 已实现 |
| (新) | led.lua | ✅ 已实现 |

## 待办

- [ ] Air780EG 开发板到货 → 烧录验证
- [ ] GNSS 冷启动定位精度测试
- [ ] PSM 功耗实测
- [ ] MQTT 端到端联调 (固件→EMQX→后端→小程序)
- [ ] SOS 按钮长按响应测试
- [ ] 电池续航实测
- [ ] OTA 升级方案设计

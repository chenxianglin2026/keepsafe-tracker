# KeepSafe EC618 Firmware

> Platform: Air780EG (EC618 core) — 合宙 LTE Cat.1 + GNSS 模组
> OS: LuatOS (出厂预装, 无需重新烧录)
> Status: 准备阶段 — 框架搭建完成, 待 SIM 卡到位后硬件验证
> Date: 2026-06-09

---

## 目录结构

```
firmware-ec618/
├── README.md              # 本文件
├── luatos/                # LuatOS 固件 (方案 A, 推荐)
│   ├── main.lua           # 主入口 + 状态机主循环 (移植自 main.c)
│   ├── config.lua         # 全局配置 (移植自 config.h)
│   ├── mqtt.lua           # MQTT 客户端 (LuatOS socket 库)
│   ├── psm.lua            # PSM 低功耗省电模块 (3GPP Rel-12)
│   └── gps.lua            # GNSS/GPS 定位模块
├── at-scripts/            # AT 指令工具脚本
│   └── mqtt_at.py         # MQTT AT 指令连接脚本 (MQTTCONNCFG/PUB/SUB/DISC)
└── shared/                # 共享参考文件
    └── (从 ESP32-S3 固件可复用的模块参考)
```

## 方案选择

| 方案 | 固件类型 | 说明 |
|------|---------|------|
| **A (推荐)** | LuatOS | Air780EG 出厂预装, MQTT via Lua socket 库, 单芯片方案 |
| B (备选) | AT Firmware | 需手动烧录, MQTT via AT+MQTT* 指令 |

当前框架按方案 A (LuatOS) 构建。AT 方案提供 mqtt_at.py 脚本用于验证/调试。

---

## 从 ESP32-S3 可复用的模块

| 模块 | 难度 | 复用方式 |
|------|------|---------|
| power.h (状态机枚举) | LOW | 直接翻译为 Lua table |
| mqtt.h (接口定义) | LOW | 直接翻译为 Lua module API |
| gps.h (GPS 数据结构) | LOW | 直接翻译为 Lua table |
| gps.c (NMEA 解析) | LOW | 直接复用逻辑; EC618 也可用 CGNSINF 直接输出 |
| lbs.h (LBS 数据结构) | LOW | 直接翻译为 Lua table |
| sos.h (SOS 数据结构) | LOW | 直接翻译为 Lua table |
| led.h (LED 模式枚举) | LOW | 直接翻译为 Lua table |
| accel.h (LIS3DH 寄存器) | LOW | 寄存器地址直接复用 |
| config.h (配置宏) | MEDIUM | 大部分参数可直接翻译到 config.lua |
| power.c (状态机逻辑) | MEDIUM | 概念翻译为 Lua 事件驱动 |
| main.c (主循环+JSON构建) | MEDIUM | JSON 构建函数直接翻译为 Lua |
| lbs.c (LBS AT 解析) | MEDIUM | 解析逻辑可移植, AT 响应格式需验证 |
| mqtt.c (MQTT AT 封装) | HIGH | EC618 MQTT 用 LuatOS socket 库, AT 方式不同 |
| accel.c (I2C 驱动) | HIGH | LuatOS I2C API 完全不同, 寄存器操作逻辑可参考 |
| sos.c (GPIO/ADC) | HIGH | LuatOS GPIO/ADC API 完全重写 |
| led.c (PWM) | HIGH | LuatOS PWM API 完全重写 |

---

## 快速开始 (硬件验证)

### 1. 串口连接
```bash
# Air780EG 开发板 Type-C → 电脑 USB
ls /dev/cu.*usbmodem*
# 应显示: /dev/cu.usbmodem0000000000013
```

### 2. AT 基础测试
```bash
python3 ~/projects/keepsafe/scripts/test_at.py
```

### 3. MQTT AT 测试 (AT 固件方案)
```bash
python3 ~/projects/keepsafe/code/firmware-ec618/at-scripts/mqtt_at.py \
  --port /dev/cu.usbmodem0000000000013
```

### 4. LuatOS 烧录
```bash
# 使用合宙 Luatools 工具烧录脚本到 Air780EG
# 脚本文件: luatos/*.lua
```

---

## 待办事项

- [ ] SIM 卡激活后验证 AT 基础通信
- [ ] 确认固件类型 (LuatOS / AT)
- [ ] 完成 LuatOS MQTT 连接 + 发布测试
- [ ] 移植 power 状态机到 Lua
- [ ] 移植 LIS3DH I2C 驱动到 LuatOS API
- [ ] 移植 LED PWM 驱动
- [ ] 移植 SOS 按键 + 电池 ADC
- [x] PSM 省电配实验证 (psm.lua 模块已实现)
- [ ] GNSS 定位精度测试
- [ ] 端到端联调 (固件 → MQTT → 后端 → 小程序)

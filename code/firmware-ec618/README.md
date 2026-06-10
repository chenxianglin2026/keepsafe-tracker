# KeepSafe DTU Firmware (YED DTU3 / EC718P)

> Platform: YED DTU3 (EC718P 内核, 非 EC618) — 亿佰特 LTE Cat.1 + GNSS DTU
> OS: LuatOS-SoC V1003 (出厂预装, 无需重新烧录)
> Chip: EC718P-M100PG (移芯 Cat.1 bis 通信芯片)
> Status: 适配阶段 — DTU协议适配中, 框架基于EC618迁移
> Date: 2026-06-10

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
| **A (推荐)** | LuatOS-SoC | YED DTU3 出厂预装 LuatOS-SoC V1003, MQTT via DTU协议/Lua socket 库, 单芯片方案 |
| B (备选) | AT Firmware | 需手动烧录, MQTT via AT+MQTT* 指令 |

当前框架按方案 A (LuatOS) 构建。DTU协议适配中。AT 方案提供 mqtt_at.py 脚本用于验证/调试。

**重要**: YED DTU3 使用 EC718P 芯片, 非 EC618。LuatOS API 兼容但 GPIO 管脚映射不同。

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
# YED DTU3 Type-C → 电脑 USB
ls /dev/cu.*usbmodem*
# 应显示: /dev/cu.usbmodemXXXX
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
# 使用亿佰特 DTU配置工具 或 合宙 Luatools 工具烧录脚本到 YED DTU3
# 脚本文件: luatos/*.lua
```

## DTU协议适配

YED DTU3 自带DTU透传协议, 支持 JSON/MODBUS/自定义格式。适配方案:
1. **DTU原生协议**: 利用DTU内置JSON上报格式, 后端适配解析
2. **LuatOS透传**: 禁用DTU协议, 直接用Lua脚本控制MQTT topic和payload
3. **混合模式**: DTU协议负责注册/心跳, Lua脚本负责业务数据

当前推荐方案2 (LuatOS透传), 保持与EC618代码兼容性, 最大化控制灵活性。

### MQTT Topic映射

DTU默认topic格式 → KeepSafe后端topic格式:
- `dtu/{device_id}/data` → `keepsafe/v1/{device_id}/location`
- `dtu/{device_id}/heart` → `keepsafe/v1/{device_id}/heartbeat`
- `dtu/{device_id}/alarm` → `keepsafe/v1/{device_id}/sos`

详见: `code/firmware-ec618/MQTT-TOPIC-MAP.md`

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

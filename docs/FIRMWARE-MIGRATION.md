# KeepSafe EC618 固件迁移准备

> 文档类型: 固件迁移清单 + 操作指南
> 日期: 2026-06-05
> 当前固件: ESP32-S3 (ESP-IDF) + Air780E 外挂 Modem
> 目标平台: EC618 (合宙 Air780E 开发板, AT 指令方案)

---

## 零、硬件状态

| 硬件 | 状态 | 备注 |
|------|------|------|
| Air780E (EC618) 开发板 | ✅ 已采购 | 2026-06-05 到货，可开始验证 |
| SIM 卡 | ⬜ 待准备 | 需物联网卡 (电信/移动) |
| 4G 天线 (IPEX-1) | ⬜ 待确认 | 开发板可能已自带 |
| USB 转串口 (CH340G) | ⬜ 待准备 | macOS 需安装驱动 |

---

## 一、现有固件代码清单 (18 文件)

代码位置: `code/firmware/main/`

| # | 文件 | 行数 | 大小 | 功能 |
|---|------|------|------|------|
| 1 | main.c | 715 | 22.6KB | 主入口 + 状态机主循环 + JSON 构建 + GPS 获取 + ISR |
| 2 | config.h | 158 | 7.1KB | 全局配置 (GPIO/UART/MQTT/电量/PSM/SOS/LED/深度睡眠) |
| 3 | power.c | 358 | 10.8KB | 电源管理状态机 (静止/移动/刚停下/SOS/深睡) |
| 4 | power.h | 183 | 5.3KB | 电源管理接口 |
| 5 | mqtt.c | 418 | 12.4KB | MQTT AT 指令封装 (Air780E MQTTCONN/PUB/SUB/DISC) + PSM 配置 + 指数退避重连 |
| 6 | mqtt.h | 164 | 4.5KB | MQTT 接口 |
| 7 | gps.c | 337 | 9.6KB | GPS NMEA 解析 ($GNGGA/$GNRMC) + 线程安全互斥 |
| 8 | gps.h | 96 | 3.0KB | GPS 数据结构 + 接口 |
| 9 | lbs.c | 236 | 7.8KB | LBS 基站定位 (AT+CSQ/CREG/COPS/CENG 解析) |
| 10 | lbs.h | 97 | 2.9KB | LBS 接口 |
| 11 | accel.c | 343 | 11.2KB | LIS3DH 加速度计 I2C 驱动 + 运动检测中断 |
| 12 | accel.h | 161 | 4.9KB | LIS3DH 寄存器定义 + 接口 |
| 13 | sos.c | 397 | 12.2KB | SOS 按键 (长按3秒) + 电池 ADC 读取 + 振动马达反馈 |
| 14 | sos.h | 145 | 4.2KB | SOS 事件结构 + 电池结构 + 接口 |
| 15 | led.c | 221 | 6.5KB | LED PWM 驱动 (蓝/绿/红, 脉冲省电) |
| 16 | led.h | 99 | 2.4KB | LED 模式定义 + 接口 |
| 17 | wifi_mqtt.c | 49 | 2.0KB | WiFi MQTT 直连 (ESP-IDF mqtt_client, 开发调试用) |
| 18 | wifi_mqtt.h | 7 | 0.2KB | WiFi MQTT 接口 |

---

## 二、迁移难度评估

### 难度分级说明

- **LOW**: 纯逻辑/算法, 不依赖硬件, 可直接复用或微调
- **MEDIUM**: 逻辑可移植但 API 需适配, 或结构需拆分
- **HIGH**: 深度绑定 ESP-IDF / 原硬件架构, 需完全重写
- **DROP**: 不再需要, 直接删除

### 逐文件评估

| # | 文件 | 难度 | 说明 |
|---|------|------|------|
| 1 | main.c | **MEDIUM** | 状态机主循环逻辑通用, 但 UART/GPIO/FreeRTOS 全部需要适配。JSON 构建函数可直接复用。GPS 获取流程需改写为 AT 指令串行调用。 |
| 2 | config.h | **MEDIUM** | 宏定义大部分可复用 (设备ID/版本/MQTT Broker/间隔参数/电量阈值/SOS 参数)。GPIO 宏全部作废 (EC618 引脚不同)。PSM 参数改为 EC618 AT 格式。 |
| 3 | power.c | **MEDIUM** | 状态机逻辑 (state_name/transition/wake_reason_detect) 概念完全可移植。ESP 深度睡眠 API (esp_deep_sleep_start/esp_sleep_enable_timer_wakeup) 需替换为 EC618 sleep 机制。GPS on/off 改为 AT 指令。 |
| 4 | power.h | **LOW** | 枚举和结构定义几乎直接可用, 无需改动。 |
| 5 | mqtt.c | **HIGH** | 当前用 Air780E 内置 MQTT AT 指令。EC618 作为主控仍有 4G 能力, 但 MQTT AT 指令集可能不同 (合宙 Air780E 固件不同)。需验证 AT+MQTTCONNCFG/CONN/PUB 在 EC618 上是否可用。指数退避逻辑可移植。 |
| 6 | mqtt.h | **LOW** | 接口定义可直接复用, 几乎无改动。 |
| 7 | gps.c | **LOW** | NMEA 解析器是纯 C 逻辑 (strtok/sscanf/atof), 完全不依赖硬件。这是最有价值的可直接复用的模块。Mutex 需替换为 EC618 同步原语。 |
| 8 | gps.h | **LOW** | 数据结构可直接复用。 |
| 9 | lbs.c | **MEDIUM** | LBS AT 命令解析逻辑 (CSQ/CREG/COPS/CENG) 概念成立。但 Air780E 的 AT 响应格式与 EC618 可能不同, 需验证和适配解析器。 |
| 10 | lbs.h | **LOW** | 数据结构可直接复用。 |
| 11 | accel.c | **HIGH** | 完全依赖 ESP-IDF I2C 驱动 (driver/i2c.h)。EC618 需要不同的 I2C API。LIS3DH 寄存器操作逻辑可参考, 但代码基本重写。CTRL1/CTRL4 配置值可复用。 |
| 12 | accel.h | **MEDIUM** | LIS3DH 寄存器地址定义可直接复用。数据结构可直接复用。但底层 I2C API 不同。 |
| 13 | sos.c | **HIGH** | GPIO 中断/ADC 读取/振动马达全部依赖 ESP-IDF API (driver/gpio.h, driver/adc.h, esp_adc_cal.h)。按键去抖逻辑可移植, 但需要适配 EC618 GPIO/ADC API。 |
| 14 | sos.h | **LOW** | 枚举和结构定义可直接复用。 |
| 15 | led.c | **HIGH** | 完全依赖 ESP-IDF LEDC PWM 外设 (driver/ledc.h)。EC618 的 PWM 机制完全不同。LED 闪烁模式逻辑可移植, 但硬件层需要重写。 |
| 16 | led.h | **LOW** | LED 模式枚举可直接复用。 |
| 17 | wifi_mqtt.c | **DROP** | ESP32 WiFi 调试专用。EC618 没有 WiFi, 直接删除。 |
| 18 | wifi_mqtt.h | **DROP** | 同上。 |

### 汇总

| 难度 | 数量 | 文件 |
|------|------|------|
| LOW | 8 | power.h, mqtt.h, gps.c, gps.h, lbs.h, sos.h, led.h, accel.h (头文件+纯逻辑) |
| MEDIUM | 5 | main.c, config.h, power.c, lbs.c, accel.h |
| HIGH | 5 | mqtt.c, accel.c, sos.c, led.c (硬件驱动层) |
| DROP | 2 | wifi_mqtt.c, wifi_mqtt.h |

---

## 三、EC618 开发板到手后第一步操作指南

### Step 1: 硬件连接 (预计 10 分钟)

```
USB-C ─── CH340G USB转串口 ─── EC618 开发板
          TX ────────────── RX
          RX ────────────── TX
          GND ───────────── GND

Air780E 开发板上的:
  - USB 口供电 (5V, 建议用电脑 USB 或独立 5V 电源)
  - NET 灯: 4G 网络状态指示
  - 可能需要外接 4G 天线 (IPEX-1)
```

### Step 2: 串口连接验证 (预计 5 分钟)

```bash
# macOS 识别串口
ls /dev/cu.*

# 串口通信 (115200 8N1)
screen /dev/cu.usbserial-XXXX 115200

# 发送 AT 测试指令
AT
# 应返回: OK

AT+CPIN?
# 检查 SIM 卡状态, 返回: +CPIN: READY

AT+CSQ
# 检查信号强度
```

### Step 3: 4G 网络注册验证 (预计 5 分钟)

```bash
AT+CGATT=1
# 附着网络

AT+CEREG?
# 检查网络注册状态
# 期望: +CEREG: 0,1  (已注册)

AT+COPS?
# 查看运营商
# 期望返回运营商信息
```

### Step 4: MQTT 连接测试 (预计 15 分钟)

```bash
# 配置 PDP 上下文 (电信 APN: ctnet)
AT+CGDCONT=1,"IP","ctnet"

# 激活 PDP
AT+CGACT=1,1

# MQTT 连接 (如果 Air780E 固件支持 MQTT AT 指令)
AT+MQTTCONNCFG=0,0,"43.163.5.90",1883,0,300,"KS-TEST001"
AT+MQTTCONN=0,"43.163.5.90",1883,0

# 发布测试消息
AT+MQTTPUB=0,"keepsafe/v1/KS-TEST001/heartbeat","{\"test\":1}",0,0
```

### Step 5: GNSS 定位测试 (预计 5-10 分钟, 空旷室外)

```bash
# 开启 GNSS
AT+CGNSPWR=1

# 等待定位 (冷启动约 35 秒)
# 查询 NMEA 数据
AT+CGNSINF

# 期望返回类似:
# +CGNSINF: 1,1,20260605120000.000,22.123456,113.654321,100.5,2.5,180.0,1,10,1.5,3
```

### Step 6: 确认开发环境

```bash
# 确认 Air780E 固件版本
AT+CGMR
# 记录版本号

# 确认支持哪些 MQTT AT 命令
AT+MQTT?
# 如果返回 ERROR, 说明固件需要升级或使用 LuatOS 脚本方案

# 确认 PSM 支持
AT+CPSMS?
```

### 关键验证清单

- [ ] 串口通信正常 (AT 返回 OK)
- [ ] SIM 卡识别 (AT+CPIN? → READY)
- [ ] 4G 附着成功 (AT+CEREG? → 已注册)
- [ ] MQTT 连接到 VPS Broker (43.163.5.90:1883)
- [ ] MQTT 发布消息成功
- [ ] GNSS 定位获取到有效坐标
- [ ] 记录固件版本号
- [ ] 确认 MQTT AT 指令集兼容性

### 重要决策点

**如果 Air780E 的 MQTT AT 指令不可用:**
→ 改用 LuatOS 脚本方案 (合宙官方提供, 基于 Lua)

**如果 MQTT 可用:**
→ 继续用 AT 指令方案, 只需翻译 C 代码中的 AT 命令格式

---

## 四、迁移策略

### 推荐方案: AT 指令 → LuatOS 脚本

由于 EC618 (Air780E) 官方主推 LuatOS, MQTT AT 指令可能在部分固件版本中不可用。
推荐迁移路径:

```
Phase 1: 用 AT 命令验证硬件链路 (1 天)
Phase 2: 如果 MQTT AT 可用 → 翻译 C 逻辑到 AT 命令序列 (2 周)
Phase 3: 如果 MQTT AT 不可用 → 用 LuatOS 重写核心逻辑 (3 周)
```

### 可复用的模块 (直接翻译/迁移)

1. **JSON 构建逻辑** (main.c 中 build_*_json 函数) — 直接翻译为 LuatOS
2. **NMEA 解析** (gps.c) — 逻辑简单, 可能不需要 (EC618 直接输出 GNSS 解析结果)
3. **状态机逻辑** (power.c 状态转换) — 概念翻译
4. **LIS3DH 寄存器值** (accel.h 寄存器地址) — 直接复用

---

*本文档在开发板到货后应及时更新为实际验证结果。*

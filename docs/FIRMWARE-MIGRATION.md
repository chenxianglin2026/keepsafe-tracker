# KeepSafe EC618 固件迁移准备

> 文档类型: 固件迁移清单 + 操作指南
> 日期: 2026-06-06 (更新)
> 当前固件: ESP32-S3 (ESP-IDF) + Air780E 外挂 Modem
> 目标平台: EC618 内核 (合宙 Air780EG 模组, LuatOS 方案)

---

## 零、硬件状态

| 硬件 | 状态 | 备注 |
|------|------|------|
| Air780EG (EC618 内核) 开发板 | ✅ 已采购 | 2026-06-05 到货，合宙官方开发板 / 核心板 |
| Air780EG 模组规格 | ✅ 确认 | EC618 内核, 支持 LTE Cat.1 + GNSS, LuatOS 固件 |
| SIM 卡 | ⬜ 待准备 | 需物联网卡 (推荐电信 ctnet APN, 或移动 cmnet) |
| 4G 天线 (IPEX-1) | ⬜ 待确认 | 开发板通常自带 FPC 天线或 IPEX 接口 |
| USB 转串口 | ✅ 内置 | Air780EG 开发板板载 USB-TypeC + CH340/CH343 串口芯片 |
| macOS CH340 驱动 | ⬜ 待安装 | 如系统未自动识别，需安装 WCH CH34x 驱动 |

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

## 三、Air780EG (EC618) 到手后精确操作步骤

### Step 1: 硬件连接 (预计 5 分钟)

Air780EG 开发板通常自带 USB-TypeC 接口和板载 CH340/CH343 串口芯片，无需外接 USB 转串口模块:

```
Air780EG 开发板 Type-C ─── USB 线 ─── 电脑 USB 口
  (板载串口芯片自动完成 USB↔UART 转换)

开发板上:
  - Type-C 口供电 + 串口通信 (二合一)
  - NET 灯: 4G 网络状态指示 (快闪=搜网, 慢闪=已注册)
  - STA 灯: 模块运行状态
  - 如无内置天线，需外接 4G 天线 (IPEX-1 接口)
  - SIM 卡槽: 插入物联网卡 (缺口朝内, 金属触点朝下)
```

### Step 2: 串口连接验证 (预计 5 分钟)

```bash
# macOS 识别串口 (Air780EG 通常显示为 cu.usbserial-XXXX 或 cu.wchusbserial-XXXX)
ls /dev/cu.*usbserial*
ls /dev/cu.*usbmodem*

# 串口通信 (115200 8N1, Air780EG 默认波特率)
screen /dev/cu.usbserial-XXXX 115200

# 或使用项目自带脚本自动检测并测试:
python3 ~/projects/keepsafe/scripts/test_at.py

# 手动发送 AT 测试指令
AT
# 应返回: OK

AT+CPIN?
# 检查 SIM 卡状态, 返回: +CPIN: READY

AT+CGMR
# 查看固件版本 (确认是 LuatOS 还是 AT 固件)
# AT 固件返回类似: "AirM2M_780EG_VXXXX_LTE_AT"
# LuatOS 固件返回类似: "LuatOS-SoC_VXXXX_EC618"
```

### Step 3: 4G 网络注册验证 (预计 5 分钟)

```bash
AT+CGATT=1
# 附着 GPRS 网络

AT+CEREG?
# 检查网络注册状态
# 期望: +CEREG: 0,1  (已注册 home network)
#        +CEREG: 0,5  (已注册 roaming)

AT+COPS?
# 查看运营商
# 期望返回类似: +COPS: 0,0,"China Telecom",7

AT+CSQ
# 信号强度 (0-31, 99=无信号)
# +CSQ: 20,99  (rssi=20 表示 -77dBm, ber=99 表示未知)
```

### Step 4: PDP 激活 + 网络连通性测试 (预计 5 分钟)

```bash
# 配置 PDP 上下文 (电信 APN: ctnet, 移动: cmnet)
AT+CGDCONT=1,"IP","ctnet"

# 激活 PDP (cid=1)
AT+CGACT=1,1

# 检查是否获取到 IP
AT+CGPADDR=1
# 期望: +CGPADDR: 1,10.x.x.x (获取到运营商内网 IP 表示成功)

# Ping 测试外网连通性 (可选)
AT+PING="43.163.5.90"
# 期望: +PING: 43.163.5.90,<time>ms,<ttl>
```

### Step 5: LuatOS 固件确认 + MQTT 方案决策 (关键步骤!)

```bash
# Air780EG 出厂默认烧录 LuatOS 固件，AT 固件需要手动烧录。
# 如果你拿到手的是 LuatOS 固件 (大概率), MQTT AT 指令不可用。
# 用 test_at.py 脚本自动检测:
python3 ~/projects/keepsafe/scripts/test_at.py

# 手动确认固件类型:
AT+CGMR
# LuatOS: "LuatOS-SoC_VXXXX_EC618" → MQTT 方案用 LuatOS socket + Lua 实现
# AT固件: "AirM2M_780EG_VXXXX_LTE_AT" → MQTT 可用 AT+MQTTCONNCFG 等指令

# MQTT AT 指令兼容性检查 (仅 AT 固件)
AT+MQTT?
# 返回 OK → MQTT AT 可用
# 返回 ERROR → 必须用 LuatOS 方案
```

**决策结果 (推荐):**

**方案 A — LuatOS (推荐, 默认选择):**
- Air780EG 出厂预装 LuatOS, 无需重新烧录
- 合宙官方持续维护 LuatOS, 生态成熟
- MQTT 通过 Lua socket 库实现, 灵活可控
- 项目现有 C 代码逻辑直接翻译为 Lua
- JSON 构建/NMEA 解析/状态机在 Lua 中简洁实现
- 无需外挂 MCU (ESP32-S3可省去), Air780EG 单芯片搞定

**方案 B — AT 固件 (备选):**
- 需要手动烧录合宙 AT 固件
- MQTT 通过 AT+MQTTCONNCFG/PUB/SUB 等指令
- 适合已有 MCU (ESP32-S3) 做主控的场景
- AT 指令串行执行, 实时性不如 LuatOS 事件驱动

### Step 6: GNSS 定位测试 (预计 5-10 分钟, 空旷室外)

```bash
# 开启 GNSS (LuatOS 固件可用 AT 指令控制)
AT+CGNSPWR=1

# 等待定位 (冷启动约 35 秒)
# 查询定位结果
AT+CGNSINF

# 期望返回类似:
# +CGNSINF: 1,1,20260606120000.000,22.123456,113.654321,100.5,2.5,180.0,1,10,1.5,3

# 也可使用 AT+CGPSINFO (部分固件支持)
AT+CGPSINFO
# 返回: +CGPSINFO: 2230.123456,N,11339.654321,E,...
```

### Step 7: PSM 省电配置验证

```bash
# 查询 PSM 状态
AT+CPSMS?

# 配置 PSM (LuatOS 固件)
# Active Time (T3324): 10s, TAU (T3412): 54min
AT+CPSMS=1,,,"00001000","00000101"

# 查询 eDRX 状态
AT+CEDRXS?
```

### 关键验证清单

- [ ] 串口通信正常 (AT 返回 OK)
- [ ] SIM 卡识别 (AT+CPIN? → READY)
- [ ] 4G 网络注册成功 (AT+CEREG? → 0,1 或 0,5)
- [ ] PDP 激活获取 IP (AT+CGPADDR=1 → 有效 IP)
- [ ] 确认固件类型: LuatOS / AT (AT+CGMR)
- [ ] GNSS 定位获取到有效坐标
- [ ] PSM/eDRX 省电配置确认
- [ ] 根据固件类型确定 MQTT 实现方案
- [ ] 使用 test_at.py 脚本输出测试报告

### 重要决策点: LuatOS vs AT 最终确认

**Air780EG (EC618) 出厂默认为 LuatOS 固件。** 合宙官方推荐使用 LuatOS 进行二次开发。

| 对比维度 | LuatOS (推荐) | AT 固件 (备选) |
|---------|--------------|---------------|
| 出厂状态 | ✅ 预装，无需烧录 | ❌ 需手动烧录 AT 固件 |
| MQTT 实现 | Lua socket 库 (灵活) | AT+MQTT* 指令集 (受限) |
| 主控架构 | Air780EG 单芯片 | 需外挂 MCU (ESP32-S3) |
| 事件驱动 | ✅ 原生支持 | ❌ AT 轮询，实时性差 |
| PSM 深度睡眠 | ✅ LuatOS API 原生支持 | AT+CPSMS 配置 |
| 固件生态 | 合宙主力维护 | 部分高级功能不可用 |
| 开发效率 | 逻辑翻译 C→Lua | 仅发送 AT 命令 |
| 社区支持 | 活跃 (LuatOS 社区) | 一般 |

**最终决策: 采用方案 A — LuatOS 固件方案**

迁移路径:
```
Phase 1: 用 test_at.py 验证硬件链路 + 确认固件类型 (1 小时)
Phase 2: LuatOS 核心逻辑翻译 (2-3 周)
  - C 代码中的 JSON 构建、状态机、NMEA 解析翻译为 Lua
  - MQTT 使用 LuatOS socket + mqtt 库
  - 传感器驱动 (LIS3DH I2C) 使用 LuatOS GPIO/I2C API
Phase 3: 联调测试 + 省电优化 (1 周)
```

---

## 四、迁移策略 (LuatOS 方案)

### 已确认方案: C/ESP-IDF → LuatOS (Air780EG 单芯片)

Air780EG 出厂预装 LuatOS 固件，且 EC618 是合宙主力维护平台。
采用 LuatOS 单芯片方案，省去 ESP32-S3 外挂 MCU。

### AT 指令快速验证脚本

项目已提供自动化测试脚本 `scripts/test_at.py`:
```bash
# 自动检测 Air780EG 并运行基础 AT 测试 (AT → AT+CSQ → AT+CGPSINFO)
python3 ~/projects/keepsafe/scripts/test_at.py

# 完整测试套件 (SIM卡/网络/固件/GNSS/PSM)
python3 ~/projects/keepsafe/scripts/test_at.py --full

# 列出所有可用串口
python3 ~/projects/keepsafe/scripts/test_at.py --list
```

### 可复用的模块 (直接翻译/迁移)

1. **JSON 构建逻辑** (main.c 中 build_*_json 函数) — 直接翻译为 LuatOS Lua 表 + json.encode()
2. **NMEA 解析** (gps.c) — 逻辑简单，可能不需要 (EC618 直接输出 GNSS 解析结果 via CGNSINF)
3. **状态机逻辑** (power.c 状态转换) — 概念翻译为 Lua 事件驱动
4. **LIS3DH 寄存器值** (accel.h 寄存器地址) — 直接复用，LuatOS I2C API 调用

### LuatOS 开发资源

- 合宙 LuatOS 官方文档: https://docs.openluat.com/
- Air780EG 产品页: https://docs.openluat.com/air780eg/
- LuatOS MQTT 库: socket + mqtt 标准库
- 固件烧录工具: Luatools (合宙官方), 支持固件下载/脚本烧录/日志查看

---

*本文档在开发板到货后应及时更新为实际验证结果。*

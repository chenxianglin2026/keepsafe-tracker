# KeepSafe — 测试指南

> 版本: v1.0
> 日期: 2026-06-06
> 硬件平台: ESP32-S3 + Air780E (EC618)
> 固件: ESP-IDF (当前) → LuatOS (迁移中)

---

## 一、测试总览

| 测试类别 | 覆盖范围 | 工具/脚本 | 预计耗时 |
|----------|----------|-----------|----------|
| 后端 API | 27 tests (health/auth/devices/fences/alerts/users) | pytest | 30s |
| 固件 AT 指令 | Air780E 模组串口通信验证 | test_at.py | 2min |
| 硬件功能 | GPIO/传感器/按键/电池/MQTT | 串口 + 万用表 | 15min |
| 固件烧录 | esptool 写入 ESP32-S3 | esptool.py | 3min |
| GNSS 定位 | 室外定位精度 | test_at.py --full | 10min |
| PSM 省电 | 深度睡眠功耗 | 串口 + 直流电源 | 30min |
| MQTT 端到端 | 固件 → EMQX → 后端 | docker compose logs | 5min |

---

## 二、后端 API 测试

### 前提条件
- Python 3.9+ (yijiaren 用 3.9) / 3.11+ (keepsafe 用 3.11)
- 虚拟环境已安装依赖
- DEV_MODE=true (使用 SQLite 测试库)

### 运行测试
```bash
cd ~/projects/keepsafe/code/backend

# 激活虚拟环境
source .venv/bin/activate

# 安装测试依赖
pip install pytest pytest-asyncio httpx

# 运行全部测试 (27 个)
pytest tests/test_api.py -v

# 预期输出:
# tests/test_api.py::TestHealth::test_health_ok PASSED
# tests/test_api.py::TestHealth::test_docs PASSED
# tests/test_api.py::TestAuth::test_login_ok PASSED
# ... (全部 27 个)
# ======================== 27 passed in X.XXs ========================
```

### 测试覆盖清单

**Health Check (2)**
- [x] GET /health → 200, status=ok
- [x] GET /docs → 200

**Auth (5)**
- [x] POST /api/v1/users/login (正确密码) → 200, 返回 token
- [x] POST /api/v1/users/login (错误密码) → 401
- [x] POST /api/v1/users/login (不存在用户) → != 200
- [x] 未认证请求受保护接口 → 401
- [x] 错误 token 请求受保护接口 → 401

**Devices (8)**
- [x] GET /api/v1/devices/{id}/status → 200
- [x] GET /api/v1/devices/{id}/location → 200/404
- [x] GET /api/v1/devices/{id}/history → 200, list
- [x] GET /api/v1/devices/{id}/sos/events → 200, list
- [x] POST /api/v1/devices/bind (新设备) → 200
- [x] POST /api/v1/devices/bind (已存在绑定) → 200
- [x] POST /api/v1/devices/bind (错误token) → 403
- [x] 访问他人设备 → 403

**Users (3)**
- [x] GET /api/v1/users/me → 200/404
- [x] PUT /api/v1/users/me → 200/404
- [x] POST /api/v1/users/register → 200/201/400

**Fences (3)**
- [x] POST /api/v1/fences → 200/201/404
- [x] GET /api/v1/fences → 200/404
- [x] DELETE /api/v1/fences/{id} → 200/404

**Alerts (2)**
- [x] GET /api/v1/alerts → 200/404
- [x] PUT /api/v1/alerts/{id}/read → 200/404

**Edge Cases (4)**
- [x] 空 JSON 登录 → 422
- [x] 非法 JSON → 400/422
- [x] 超长 device_id → 不崩溃
- [x] 绑定设备到他人 → 403

### 手动 API 调试
```bash
# 测试登录
curl -X POST http://localhost:8000/api/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@keepsafe.com","password":"test123456"}'

# 使用返回的 token 访问设备 (替换 YOUR_TOKEN)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/devices/KS-00000001/status
```

---

## 三、固件 AT 指令测试

### 硬件连接
```
Air780E 开发板 Type-C ──── USB 线 ──── Mac USB 口
  (板载 CH340/CH343 串口芯片自动完成 USB↔UART 转换)

开发板上:
  - Type-C: 供电 + 串口通信 (二合一)
  - NET 灯: 快闪 = 搜网,  慢闪 = 已注册
  - SIM 卡槽: 插入物联网卡 (缺口朝内, 金属触点朝下)
  - 4G 天线: IPEX-1 接口 (如无内置天线)
```

### 自动测试 (推荐)
```bash
cd ~/projects/keepsafe
python3 scripts/test_at.py

# 自动检测 Air780E 模组并运行基础测试:
# AT → AT+CSQ → AT+CGPSINFO

# 完整测试套件 (SIM/网络/固件/GNSS/PSM):
python3 scripts/test_at.py --full

# 列出所有可用串口:
python3 scripts/test_at.py --list

# 指定串口:
python3 scripts/test_at.py --port /dev/cu.usbserial-110

# 指定波特率:
python3 scripts/test_at.py --baud 9600
```

### 手动 AT 指令测试

使用 screen 或 minicom:
```bash
# 方法一: screen
screen /dev/cu.usbserial-XXXX 115200

# 方法二: minicom
minicom -D /dev/cu.usbserial-XXXX -b 115200

# 方法三: cu
cu -l /dev/cu.usbserial-XXXX -s 115200
```

#### 基础测试序列
```
AT                          # 基本响应, 期望: OK
AT+CPIN?                    # SIM 卡状态, 期望: +CPIN: READY
AT+CGMR                     # 固件版本
AT+CGSN                     # IMEI
AT+CSQ                      # 信号强度 (0-31)
AT+CEREG?                   # 网络注册, 期望: +CEREG: 0,1
AT+COPS?                    # 运营商
```

#### 网络测试
```
AT+CGATT=1                  # 附着 GPRS
AT+CGDCONT=1,"IP","ctnet"   # 设置 APN (电信 ctnet / 移动 cmnet)
AT+CGACT=1,1                # 激活 PDP
AT+CGPADDR=1                # 获取 IP 地址
AT+PING="43.163.5.90"       # Ping VPS
```

#### GNSS 定位测试 (室外)
```
AT+CGNSPWR=1                # 开启 GNSS
# 等待 35 秒 (冷启动)
AT+CGNSINF                  # 查询定位结果
# 期望: +CGNSINF: 1,1,20260606120000.000,22.123456,113.654321,100.5,...
AT+CGPSINFO                 # 备用查询
```

#### PSM 省电测试
```
AT+CPSMS?                   # 查询 PSM 状态
AT+CPSMS=1,,,"00001000","00000101"   # 配置 PSM
AT+CEDRXS?                  # 查询 eDRX 状态
```

### AT 指令参考表

| 指令 | 功能 | 期望响应 |
|------|------|----------|
| AT | 基本通信检测 | OK |
| AT+CPIN? | SIM 卡状态 | +CPIN: READY |
| AT+CSQ | 信号强度 | +CSQ: 15-31,99 |
| AT+CGATT? | GPRS 附着 | +CGATT: 1 |
| AT+CEREG? | 网络注册 | +CEREG: 0,1 或 0,5 |
| AT+COPS? | 运营商名称 | +COPS: 0,0,"China Telecom",7 |
| AT+CGMR | 固件版本 | LuatOS-SoC... 或 AirM2M_780EG... |
| AT+CGSN | IMEI | 15 位数字 |
| AT+CGNSPWR=1 | 开启 GNSS | OK |
| AT+CGNSINF | GNSS 定位 | 坐标 + 精度 + 速度 |
| AT+CGPSINFO | GPS 坐标 | +CGPSINFO: lat,N,lon,E,... |
| AT+CPSMS? | PSM 状态 | +CPSMS: ... |
| AT+CGPADDR=1 | IP 地址 | +CGPADDR: 1,10.x.x.x |
| AT+HTTPPARA/GET | HTTP 测试 | 用于网络连通性验证 |

---

## 四、固件烧录 (ESP32-S3)

### 硬件准备
```
ESP32-S3 开发板:
  - 使用 USB-OTG 口 (标记为 USB/OTG), 非 UART 口
  - 不要用 USB-to-UART 口 (该口仅用于串口调试)
  - 设备路径: /dev/cu.usbmodem101
```

### 安装 esptool
```bash
pip3 install esptool
# 验证
esptool.py version
```

### 擦除 Flash
```bash
esptool.py --chip esp32s3 --port /dev/cu.usbmodem101 erase_flash
```

### 烧录固件
```bash
# 编译固件
cd ~/projects/keepsafe/code/firmware

# 使用 ESP-IDF 构建
idf.py set-target esp32s3
idf.py menuconfig   # 配置串口 (默认 UART0: USB JTAG)
idf.py build

# 烧录 (自动进入下载模式)
idf.py -p /dev/cu.usbmodem101 flash

# 或手动 esptool (4 个 bin 文件)
esptool.py --chip esp32s3 --port /dev/cu.usbmodem101 --baud 921600 \
  --before default_reset --after hard_reset write_flash \
  --flash_mode dio --flash_size 16MB --flash_freq 80m \
  0x0 build/bootloader/bootloader.bin \
  0x8000 build/partition_table/partition-table.bin \
  0x10000 build/keepsafe.bin
```

### 烧录后验证
```bash
# 打开串口监视器
idf.py -p /dev/cu.usbmodem101 monitor

# 或 screen
screen /dev/cu.usbmodem101 115200

# 查看启动日志
# 期望看到:
#   I (xxx) cpu_start: Starting scheduler
#   I (xxx) keepsafe: Firmware v1.0.0 starting...
#   I (xxx) keepsafe: Device ID: KS-XXXXXXXX
```

### 常见烧录问题
| 问题 | 原因 | 解决 |
|------|------|------|
| `Failed to connect` | 串口错误 | 确认使用 USB-OTG 口, 检查 /dev/cu.usbmodem* |
| `Invalid head of packet` | 波特率不匹配 | 降速至 115200 或 460800 |
| `Flash size mismatch` | Flash 大小错误 | 加 --flash_size 16MB |
| `设备未进入下载模式` | GPIO0 未拉低 | 按住 BOOT → 按 RST → 松开 BOOT |
| `Brownout detector` | 供电不足 | 使用有源 USB Hub 或外接 5V |

---

## 五、硬件功能测试

### 5.1 GPIO 测试

#### LED 测试
```
Air780E 开发板 (LuatOS):
  GPIO10 → 蓝色 LED
  GPIO11 → 绿色 LED
  GPIO12 → 红色 LED

测试: 上电后观察 LED 闪烁序列
  - 蓝闪: 搜网中
  - 绿闪: 已注册 + MQTT 已连接
  - 红闪: 低电量告警
  - 红蓝交替: SOS 激活中
```

#### 按键测试
```
SOS 按键 → GPIO4 (下拉)
  测试: 长按 3 秒
  期望: 振动马达震动 200ms, 红色 LED 闪烁, MQTT SOS 消息发送
```

#### 电池 ADC 测试
```
电池 ADC → GPIO7 (ADC1_CHANNEL_6)
  测量: Vbat = ADC 读数 × 分压比 (2.0)
  满电: 4.2V → ADC ≈ 2.1V
  低电: 3.3V → ADC ≈ 1.65V
  阈值: < 20% → 触发低电告警 + MQTT 发送
```

### 5.2 LIS3DH 加速度计测试 (I2C)

```
I2C 连接:
  SCL → GPIO8
  SDA → GPIO9
  地址: 0x18 (SA0 接地)
  频率: 400kHz

测试步骤:
  1. 读取 WHO_AM_I 寄存器 (0x0F) → 期望 0x33
  2. 配置 CTRL_REG1 (0x20) = 0x57 (100Hz, 正常模式, XYZ 使能)
  3. 读取 OUT_X_L/OUT_X_H (0x28-0x2D) → 加速度值
  4. 晃动设备 → 读数变化

运动检测:
  INT1 → GPIO6 (RTC_GPIO)
  晃动触发 → 中断触发 → 设备从深度睡眠唤醒
```

### 5.3 深度睡眠测试

```
进入条件: 静止超过 INTERVAL_STATIONARY_MS (30分钟)
唤醒方式:
  - RTC 定时器 (下一个上报周期)
  - SOS 按键 (GPIO4)
  - 运动检测 (LIS3DH INT1, GPIO6)

功耗测量:
  运行: ~40mA (ESP32-S3 + Air780E 活动)
  空闲: ~0.4-1mA (无 PSM)
  PSM 深度睡眠: ~15µA (仅 RTC + GPIO 唤醒源)
  ESP32-S3 深睡: ~8µA
```

### 5.4 MQTT 端到端测试

```bash
# 确保 EMQX 容器运行
cd ~/projects/keepsafe/code
docker compose ps | grep emqx

# 订阅设备 topic 观察上行数据
docker compose exec emqx emqx_ctl topics list

# 使用 MQTT 客户端手动订阅
mosquitto_sub -h localhost -p 1883 \
  -t "keepsafe/v1/KS-00000001/#" -v

# 开启后端日志查看 MQTT 消息处理
cd ~/projects/keepsafe/code
docker compose logs -f backend | grep -i mqtt
```

MQTT Topics:
| Topic | QoS | 说明 |
|-------|-----|------|
| keepsafe/v1/{id}/location | 1 | GPS 位置上报 |
| keepsafe/v1/{id}/heartbeat | 0 | 心跳 |
| keepsafe/v1/{id}/sos | 1 | SOS 紧急告警 |
| keepsafe/v1/{id}/alert/low_battery | 1 | 低电量告警 |

---

## 六、完整回归测试流程

新品/固件升级后的完整测试清单:

### Phase 1: 硬件基础 (5 min)
- [ ] 串口通信正常 (AT → OK)
- [ ] SIM 卡识别 (AT+CPIN? → READY)
- [ ] 4G 网络注册 (AT+CEREG? → 0,1)
- [ ] IMEI 读取 (AT+CGSN)

### Phase 2: 网络连通 (5 min)
- [ ] PDP 激活 (AT+CGACT=1,1)
- [ ] IP 获取 (AT+CGPADDR=1)
- [ ] Ping VPS (AT+PING="43.163.5.90")
- [ ] DNS 解析 (AT+CDNSGIP="www.baidu.com")

### Phase 3: 定位功能 (10 min, 室外)
- [ ] GNSS 冷启动 (< 35s)
- [ ] 获取有效坐标 (AT+CGNSINF)
- [ ] 定位精度 < 10m
- [ ] 热启动 < 15s (AGPS 辅助)

### Phase 4: 省电 (30 min)
- [ ] PSM 配置确认 (AT+CPSMS?)
- [ ] 进入深度睡眠 (串口静默)
- [ ] RTC 定时唤醒 (预设间隔)
- [ ] SOS 按键唤醒 (< 3s 长按)
- [ ] 运动检测唤醒 (LIS3DH INT1)
- [ ] 唤醒后数据上报正常

### Phase 5: MQTT 端到端 (5 min)
- [ ] MQTT 连接 EMQX
- [ ] 位置消息发布
- [ ] 心跳消息发布
- [ ] SOS 消息发布
- [ ] 低电量告警发布
- [ ] 后端正确入库 (PostgreSQL)

### Phase 6: 后端 API (1 min)
- [ ] `pytest tests/test_api.py -v` 全部 27 通过
- [ ] 健康检查 /health → 200
- [ ] MQTT 消息触发正确 API 返回

---

## 七、使用种子数据测试

```bash
cd ~/projects/keepsafe/code/backend

# 插入模拟设备和定位数据
source .venv/bin/activate
python seed_mock.py

# 验证数据
python -c "
from app.db import async_session_factory, Device
from sqlalchemy import select
import asyncio

async def check():
    async with async_session_factory() as s:
        r = await s.execute(select(Device))
        for d in r.scalars():
            print(f'Device: {d.device_id}, fw: {d.fw_version}, last_seen: {d.last_seen}')

asyncio.run(check())
"
```

---

## 八、测试环境对照表

| 环境 | 数据库 | 后端端口 | MQTT Broker |
|------|--------|----------|-------------|
| 本地开发 | SQLite (keepsafe_dev.db) | 8000 | EMQX (localhost:1883) |
| 本地 Docker | PostgreSQL (Docker) | 8000 | EMQX (Docker) |
| VPS 生产 | PostgreSQL (VPS) | 8000 | EMQX (Docker, VPS) |
| 固件目标 | - | - | EMQX (43.163.5.90:1883) |

---

## 九、参考文档

- FIRMWARE-MIGRATION.md — EC618/LuatOS 迁移详细指南
- scripts/test_at.py — AT 指令自动化测试脚本
- code/firmware/main/config.h — 固件引脚和参数定义
- code/backend/tests/test_api.py — 后端 API 测试套件

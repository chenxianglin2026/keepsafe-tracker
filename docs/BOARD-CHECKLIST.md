# KeepSafe 开发板到货准备清单

> 版本: v2.0
> 日期: 2026-06-10
> 硬件: YED DTU3 (EC718P-M100PG 内核, 非 EC618)
> 固件方案: LuatOS-SoC V1003 (出厂默认)
> 厂商: 亿佰特 (Ebyte)

---

## 一、开箱检查项

### 1.1 包装内容物核对

- [ ] YED DTU3 设备本体 ×1
- [ ] USB Type-C 数据线 ×1 (部分套餐含)
- [ ] 4G 天线 (IPEX-1 接口, FPC 或棒状) ×1
- [ ] GPS 天线 (IPEX-1 接口, 部分套餐含)
- [ ] 排针 (2.54mm 间距, 未焊接)

### 1.2 外观检查

- [ ] PCB 无明显划痕、焊点脱落、元件缺失
- [ ] Type-C 接口牢固、无松动
- [ ] SIM 卡槽弹性正常 (按压弹出/锁紧)
- [ ] IPEX-1 天线座完好、无变形
- [ ] 排针焊盘无氧化、短路

### 1.3 指示灯说明

| 指示灯 | 颜色 | 功能 | 正常状态 |
|--------|------|------|----------|
| NET | 红/绿 | 4G 网络状态 | 快闪=搜网, 慢闪=已注册, 常亮=数据传输 |
| STA | 蓝 | 模块运行状态 | 上电后闪烁, 系统就绪后常亮或慢闪 |
| PWR | 红 | 电源指示 | 上电常亮 |

### 1.4 物料准备确认 (以下缺一不可)

- [ ] 物联网 SIM 卡 (推荐电信 ctnet, 或移动 cmnet) — 已插入卡槽
- [ ] 4G 天线已接到 IPEX-1 接口 (Main 天线座)
- [ ] GPS 天线已接到 IPEX-1 接口 (GNSS 天线座, 如有独立)
- [ ] USB Type-C 数据线 (需支持数据传输, 非仅充电线)

> **警告**: 无天线开机可能损坏射频功放模块! 务必先接天线再上电。

### 1.5 SIM 卡安装

```
1. 缺口朝内、金属触点朝下
2. 推入卡槽直到听到"咔嗒"锁定声
3. 按压弹出确认弹性正常
```

---

## 二、串口驱动安装 (macOS CH340/CH343)

YED DTU3 开发板集成 CH340 或 CH343 USB 转串口芯片。macOS 需安装对应驱动。

### 2.1 检查当前驱动状态

```bash
# 查看已识别的串口设备
ls -la /dev/cu.*usbserial* /dev/cu.*wchusbserial* /dev/cu.*usbmodem* 2>/dev/null

# 查看 USB 设备树 (未识别时 CH340 会显示)
system_profiler SPUSBDataType | grep -A 10 -i "ch340\|ch343\|wch\|usb-serial"
```

### 2.2 安装 CH34x 驱动

```bash
# 方式一: 从 WCH 官网下载 (推荐)
# https://www.wch.cn/downloads/CH34XSER_MAC_ZIP.html
# 下载 → 解压 → 运行 .pkg 安装程序

# 方式二: Homebrew 安装 (如果可用)
# brew install --cask wch-ch34x-usb-serial-driver

# 安装后重启 Mac 或重新插拔开发板
```

### 2.3 验证驱动

```bash
# 插上开发板后检查是否出现串口设备
ls -la /dev/cu.*usbserial* /dev/cu.*wchusbserial*

# 常见设备名:
# /dev/cu.usbserial-XXXX  (CH340)
# /dev/cu.wchusbserialXXXX (CH340 旧版驱动)
# /dev/cu.usbmodemXXXX     (部分板载 USB-Serial)

# YED DTU3 开发板 Type-C 直连 macOS 常见显示:
# /dev/cu.usbserial-110  或  /dev/cu.wchusbserial110
```

### 2.4 macOS 安全设置 (如驱动被拦截)

```
系统偏好设置 → 安全性与隐私 → 通用
  → 允许来自 "WCH" 的扩展
  → 如提示点击"允许"后重启
```

---

## 三、AT 指令快速验证

### 3.1 自动化测试 (推荐)

```bash
# 检查 pyserial 依赖
pip3 install pyserial

# 自动检测 YED DTU3 串口 + 基础 AT 测试
python3 ~/projects/keepsafe/scripts/test_at.py

# 完整测试套件 (SIM卡/网络注册/固件版本/IMEI/运营商)
python3 ~/projects/keepsafe/scripts/test_at.py --full

# 仅列出所有串口设备
python3 ~/projects/keepsafe/scripts/test_at.py --list
```

### 3.2 手动 AT 指令验证 (备用)

```bash
# 连接串口 (115200 8N1, YED DTU3 默认波特率)
screen /dev/cu.usbserial-XXXX 115200
# 或使用 minicom / picocom 等终端工具
```

#### 基础验证序列

| 步骤 | AT 指令 | 期望响应 | 说明 |
|------|---------|----------|------|
| 1 | `AT` | `OK` | 串口通信正常 |
| 2 | `AT+CGMR` | `LuatOS-SoC_VXXXX_EC618` 或 `AirM2M_780EG_VXXXX_LTE_AT` | 确认固件类型 |
| 3 | `AT+CPIN?` | `+CPIN: READY` | SIM 卡识别正常 |
| 4 | `AT+CSQ` | `+CSQ: 20,99` | 信号强度 (0-31, 99=无信号) |
| 5 | `AT+CEREG?` | `+CEREG: 0,1` | 网络注册成功 (0,1=home, 0,5=roaming) |
| 6 | `AT+COPS?` | `+COPS: 0,0,"China Telecom",7` | 运营商识别 |

### 3.3 固件类型判定

| AT+CGMR 返回值 | 类型 | MQTT 方案 |
|-----------------|------|-----------|
| `LuatOS-SoC_VXXXX_EC718P` | LuatOS-SoC | Lua socket 实现 MQTT |
| `AirM2M_EC718P_VXXXX_LTE_AT` | AT 固件 | AT+MQTTCONNCFG 等指令集 |

> **重要**: YED DTU3 使用 EC718P 芯片, 非 EC618。出厂默认 LuatOS-SoC V1003, 本项目推荐使用 LuatOS 透传方案。

### 3.4 测试通过标准

- [x] `AT` → `OK`
- [ ] `AT+CPIN?` → `READY`
- [ ] `AT+CEREG?` → `0,1` 或 `0,5`
- [ ] `AT+CSQ` → 信号值 >= 10 (室内可接受)
- [ ] 固件类型确认 (LuatOS 或 AT)
- [ ] test_at.py 脚本输出 PASS

---

## 四、LuatOS 烧录步骤

### 4.1 烧录前确认

- [ ] DTU 已通过 Type-C 连接到电脑
- [ ] CH340/CH343 驱动已安装并识别串口
- [ ] 确定烧录目标: LuatOS-SoC 固件 (.soc 文件) 或 Lua 脚本 (.lua / .luac)

### 4.2 安装 Luatools (合宙官方烧录工具)

```bash
# 下载 Luatools (macOS 版本)
# 官方地址: https://docs.openluat.com/Luatools/
# 或去合宙官网下载最新版

# 安装后打开 Luatools.app
# 首次运行需在 系统偏好设置 → 安全性与隐私 中允许运行
```

### 4.3 YED DTU3 固件烧录 (LuatOS-SoC 完整固件)

```
1. 打开 Luatools
2. 选择模块: EC718P (或 Air780EG 兼容模式)
3. 点击"下载固件":
   - 选择 LuatOS-SoC 固件版本 (推荐 V1003+)
   - 或使用本地 .soc 文件
4. 点击"下载脚本":
   - 选择项目 Lua 脚本目录
   - 勾选"核心脚本"(如需)
5. 点击"开始下载"
6. 等待进度条完成 → 显示"下载成功"
```

### 4.4 YED DTU3 进入下载模式

```
方式一 (推荐): Luatools 自动触发
  → 工具会发送 AT 指令让模组进入下载模式

方式二: 手动进入 (上电前操作)
  → 按住 BOOT 按键不放
  → 插入 USB 供电
  → 等待 2 秒后松开 BOOT 键
  → Luatools 识别到设备后开始下载

方式三: 脚本烧录 (仅更新 Lua 脚本)
  → 模组正常运行状态下
  → Luatools 直接推送 .lua 文件
  → 无需进入下载模式
```

### 4.5 烧录验证

```bash
# 烧录完成后重新上电, 串口连接:
screen /dev/cu.usbserial-XXXX 115200

# 上电后应看到 LuatOS-SoC 启动日志:
# LuatOS-SoC@EC718P base 23.xx bsp V1003
# ...

# 发送 AT 确认版本:
AT+CGMR
# 应返回: LuatOS-SoC_V1003_EC718P
```

### 4.6 烧录文件位置 (项目目录)

```
~/projects/keepsafe/code/firmware-ec618/  # DTU固件 (EC718P, 非EC618, 目录名保留兼容)
~/projects/keepsafe/code/firmware-ec618/luatos/  # Lua脚本

---

## 五、4G 联网 + GPS 定位完整流程

### 5.1 环境要求

- 测试地点: **室外空旷地带** (GPS 需可见天空)
- 4G 信号: 电信/移动/联通覆盖区域
- 天气: 晴朗 (阴天 GPS 首次定位时间更长)

### 5.2 操作流程 (预计 15 分钟)

#### Phase 1: 4G 网络注册 (预计 3 分钟)

```bash
# 1. 确认 SIM 卡状态
AT+CPIN?
# → +CPIN: READY

# 2. 配置 PDP 上下文 (APN)
# 电信: ctnet / 移动: cmnet / 联通: 3gnet
AT+CGDCONT=1,"IP","ctnet"

# 3. 激活 PDP
AT+CGACT=1,1
# → OK

# 4. 检查网络注册
AT+CEREG?
# → +CEREG: 0,1  (0,1=已注册, 0,5=漫游注册)

# 5. 查看运营商
AT+COPS?
# → +COPS: 0,0,"China Telecom",7

# 6. 获取 IP 地址
AT+CGPADDR=1
# → +CGPADDR: 1,10.x.x.x (运营商内网 IP)

# 7. 信号强度
AT+CSQ
# → +CSQ: 20,99  (20 = -77dBm, 信号良好)
```

#### Phase 2: 外网连通性测试 (预计 2 分钟)

```bash
# Ping 项目服务器 (Tencent Cloud VPS)
AT+PING="43.163.5.90"
# → +PING: 43.163.5.90,<time>ms,<ttl>

# 或 Ping 公网 DNS
AT+PING="8.8.8.8"
```

#### Phase 3: GPS 定位 (预计 5-10 分钟, 首次冷启动)

```bash
# 1. 开启 GNSS 供电
AT+CGNSPWR=1
# → OK

# 2. 查询定位状态 (重复执行直到 fix=1)
AT+CGNSINF
# 期望: +CGNSINF: 1,1,20260607120000.000,22.123456,113.654321,...

# CGNSINF 字段说明:
# <mode>,<GPS:1/GLONASS:2/BD:4>,
# <fix:0=未定位,1=已定位>,<UTC时间>,
# <纬度>,<经度>,<海拔(米)>,<速度(km/h)>,
# <航向(度)>,<定位模式>,<卫星数>,<HDOP>,<VDOP>

# 3. 首次冷启动约 35 秒~2 分钟获取有效定位
#    热启动 (30 分钟内重新定位) 约 3~5 秒

# 4. 验证坐标在线地图
# 将 纬度,经度 复制到 Google Maps / 百度地图确认位置正确
```

#### Phase 4: 端到端验证 (预计 5 分钟)

```bash
# 组合验证: 4G 联网 + GPS 定位 + MQTT 上报
# (此步骤在 LuatOS 固件开发完成后进行)

# 预期数据流:
# 模组 GPS 定位 → JSON 封装 → 4G MQTT PUBLISH → 后端接收
```

### 5.3 GPS 信号质量参考

| HDOP 值 | 精度评估 | 说明 |
|---------|----------|------|
| <1.0 | 优秀 | 理想室外条件 |
| 1.0-2.0 | 良好 | 一般室外/晴天 |
| 2.0-5.0 | 一般 | 阴天/高楼附近 |
| >5.0 | 不可靠 | 室内/隧道, 不适合定位 |

### 5.4 常见问题

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| NET 灯不亮 | 未搜到网络 | 确认SIM卡/天线/APN, AT+CEREG? |
| GPS 长时间无 fix | 室内信号弱 | 移到室外空旷处, 等待 2 分钟 |
| AT 无响应 | 串口参数错误 | 确认波特率 115200, 8N1 |
| Ping 失败 | PDP 未激活或 APN 错误 | AT+CGACT? 确认, 重置 APN |
| AT+CPIN? 返回 ERROR | SIM 卡接触不良 | 重新插拔 SIM 卡 |
| 无法获取 IP | 欠费/套餐到期 | 联系运营商确认 SIM 卡状态 |

---

## 六、快速验证命令速查

```bash
# === 一键自动测试 ===
python3 ~/projects/keepsafe/scripts/test_at.py --full

# === 串口列表 ===
ls /dev/cu.*usb* /dev/cu.*wch*

# === 终端直连 ===
screen /dev/cu.usbserial-XXXX 115200
# 退出: Ctrl+A, K, Y

# === 关键 AT 快速序列 ===
AT                   # 通信OK?
AT+CPIN?             # SIM卡OK?
AT+CGMR              # 固件版本?
AT+CSQ               # 信号?
AT+CEREG?            # 注册?
AT+CGDCONT=1,"IP","ctnet"  # APN
AT+CGACT=1,1         # 激活PDP
AT+CGPADDR=1         # 获取IP
AT+CGNSPWR=1         # 开GPS
AT+CGNSINF           # 定位结果
```

---

## 七、下一步行动

1. [ ] 安装 CH340/CH343 驱动
2. [ ] 插入 SIM 卡 + 天线 + USB 供电
3. [ ] 运行 `test_at.py --full` 输出测试报告
4. [ ] 确认固件类型 (LuatOS-SoC / AT)
5. [ ] 4G 联网 + GPS 定位端到端验证
6. [ ] **DTU协议适配**: 确认topic映射方案 (A:后端适配 / B:固件配置)
7. [ ] 更新 HARDWARE.md 和 FIRMWARE-MIGRATION.md 中的 DTU 采购状态

---

**重要**: 本清单已适配 YED DTU3 (EC718P 内核, 非 EC618)。所有 Air780EG 相关操作请参考 v1.0 版本。

---

*本清单在开发板到货后逐项勾选执行, 完成全部验证后方可进入下一阶段。*

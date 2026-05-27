# KeepSafe 项目健康状况扫描报告

> **扫描时间:** 2026-05-22
> **扫描范围:** 全栈项目 — 后端 / iOS / Android / 微信小程序 / 固件 / 硬件 / 3D外壳
> **后端运行状态:** ✅ localhost:8000 运行中 (health check 通过)
> **ESP32-S3 开发板:** ✅ 已连接 (/dev/cu.usbmodem595B0960681)

---

## 1. 模块健康状况

| 模块 | 状态 | 完成度 | 风险 | 下一步 |
|------|------|--------|------|--------|
| 后端 API | ✅ 健康 | 95% | 低 | 部署到公网 VPS |
| iOS App | 🟡 有风险 | 70% | 中 | Xcode 真机调试 |
| Android App | 🟡 有风险 | 70% | 中 | Android Studio 真机调试 |
| 微信小程序 | 🟡 有风险 | 60% | 中 | 等 AppID + 腾讯地图插件 |
| 固件 (ESP32-S3) | 🔴 阻塞 | 30% | 高 | 需 VPS 编译 (GitHub 子模块网络限制) |
| 硬件 (PCB/电路) | 🔴 阻塞 | 10% | 高 | 需 VPS + PCB 打样 |
| 3D 外壳 | 🔴 阻塞 | 15% | 中 | Blender/OpenSCAD 脚本已写，需验证运行 |

### 1.1 后端 API (✅ 健康, 95%)

**问题:** 无重大问题。已知待办:
- EMQX MQTT 未连接 (当前 `mqtt_connected: false` — 本地无 EMQX，部署到 VPS 后连接)
- FCM 凭据文件 `./credentials/firebase-service-account.json` 不存在 (推送功能暂不可用)
- APNs 凭据文件 `./credentials/apns-key.p8` 不存在 (iOS 推送暂不可用)
- Redis 未运行 (本地 dev_mode 用 fakeredis 替代，暂不影响)

**代码质量:** 优秀。FastAPI + SQLAlchemy 2.0 async + 完整 CRUD 路由。包含:
- 用户注册/登录 (JWT)
- 设备绑定/解绑
- 位置查询 (Redis + DB 双缓存)
- 状态查询
- 历史轨迹
- SOS 事件
- 告警管理 (分页/标记已读)
- 围栏 CRUD
- MQTT 消息处理 (5 种 topic)
- LBS 基站定位解析 (OpenCellID)
- FCM + APNs 推送 (凭据缺失)
- Web 聊天 v2 页面 (运行中 http://192.168.110.34:8000/chat/v2)

### 1.2 iOS App (🟡 有风险, 70%)

**问题:**
- 无 `.xcodeproj` 项目文件 — 需要从源码创建 Xcode 项目
- `Info.plist` 缺失 — 缺少推送通知配置
- FCM GoogleService-Info.plist 缺失
- 未在真机调试过
- 所有 API 调用指向 `192.168.110.34:8000` (局域网地址，部署后需改为公网地址)

**代码结构:** 完整 (14 个 .swift 文件)
- `KeepSafeApp.swift` — App 入口 + AppDelegate (推送注册)
- `ContentView.swift` — TabView (地图/告警/设置)
- `Views/` — MapView, AlertListView, SettingsView, DeviceBindView
- `ViewModels/` — MapViewModel, AlertListViewModel, SettingsViewModel
- `Services/` — APIService (完整 API 调用), PushService
- `Models/` — Device, Alert, User (Pydantic 对应模型)
- API 路径已跟随后端统一修复 (见 API-FIX-REPORT.md)

### 1.3 Android App (🟡 有风险, 70%)

**问题:**
- `ApiService.kt` 中 `getProfile()`, `updateProfile()`, `getDevices()`, `getDeviceLocation()` 等返回类型使用 `ApiResponse<T>` 包装，但后端直接返回裸对象 — 序列化可能不匹配
- `getSosEvents()` 返回 `ApiResponse<List<*>>` — 类型不安全
- `bindDevice()` 返回 `ApiResponse<Unit>` — 应改为 `BindResponse`
- 缺少 FCM google-services.json
- 未在真机调试过

**代码结构:** 完整 (13 个 .kt 文件)
- Jetpack Compose + Retrofit + Navigation
- 3 个 Screen (Map, Alerts, Settings)
- NavGraph + KeepSafeNavHost
- KeepSafeRepository 数据层
- API 路径已统一修复

### 1.4 微信小程序 (🟡 有风险, 60%)

**问题:**
- **阻塞:** 等老板提供小程序 AppID (`project.config.json` 中为占位符)
- **阻塞:** 腾讯地图插件未配置 (`app.json` 中为 `{{PLACEHOLDER_TENCENT_MAP_PLUGIN_VERSION}}` 和 `{{PLACEHOLDER_TENCENT_MAP_PLUGIN_PROVIDER}}`)
- 围栏 API 请求体字段名与后端不匹配: MiniApp 用 `latitude`/`longitude`/`enable`，后端用 `lat`/`lng`/`enabled`
- 无登录页面 (直接在 `onLaunch` 检查 token)

**代码结构:** 完整 (3 个 tab 页 + 2 个组件)
- `pages/index/` — 地图主页面 (含设备标记、围栏、绑定)
- `pages/alerts/` — 告警列表
- `pages/profile/` — 个人设置
- `components/device-card/` — 设备卡片组件
- `components/fence-picker/` — 围栏选择器组件
- `utils/api.js` — API 封装 (完整)
- `utils/auth.js` — 认证工具
- `utils/map.js` — 地图工具

### 1.5 固件 ESP32-S3 (🔴 阻塞, 30%)

**问题:**
- **阻塞:** ESP-IDF cmake 在拉取 GitHub 子模块时因网络限制失败
- 无 `sdkconfig` 文件 (CMake 配置未完成)
- `config.h` 中多个 `{{PLACEHOLDER_*}}` 未替换 (设备 ID、APN、MQTT 地址)
- 固件文件完整但从未成功编译

**代码质量:** 良好 (8 个 .c + 8 个 .h, 共 ~2800 行)
- `main.c` — 状态机主循环 (STATIONARY/MOVING/SOS) + GPS 获取 + JSON 构建
- `mqtt.c` — 完整 MQTT over AT + PSM 电源管理 + 指数退避重连
- `gps.c` — GNGGA/GNRMC NMEA 解析器 (线程安全)
- `power.c` — 电源状态管理 + 动态位置上报频率
- `accel.c` — LIS3DH I2C 驱动 (低功耗模式)
- `sos.c` — SOS 按键 (长按3秒) + 低电量检测 + ADC
- `lbs.c` — 基站 ID 解析 (LAC/CellID)
- `led.c` — PWM LED 指示灯 (脉冲驱动省电)
- `config.h` — 完整硬件引脚定义 + 节电参数

### 1.6 硬件 PCB/电路 (🔴 阻塞, 10%)

**问题:**
- 硬件规范和采购清单已编写，但从未实际打样
- KiCad 工程文件不存在
- 实际 PCB 设计未开始
- 需要 VPS 才能进行 EDA 设计和文件传输

**已完成的文档:**
- `requirements/HARDWARE_SPEC.md` — 外观结构规格 (78×48×12mm)
- `requirements/HARDWARE-PURCHASE-LIST.md` — 采购清单
- 电池验证文档 `code/hardware/BATTERY_CHECK.md`

### 1.7 3D 外壳 (🔴 阻塞, 15%)

**问题:**
- Blender 脚本 `code/hardware/blender/keepsafe_enclosure.py` (412行) 已编写但未运行验证
- OpenSCAD 脚本 `keepsafe_body_v2.scad` (195行) 已更新但未渲染
- .stl 文件 `keepsafe_body_v2.stl` 存在 (旧版本)
- `keepsafe_internal_layout.scad` 内部布局文件存在
- Blender 和 OpenSCAD 工具链已安装但未验证输出
- 需要 VPS 传输 .stl 文件给 3D 打印服务

---

## 2. 阻塞项排序 (按优先级)

| # | 阻塞项 | 影响范围 | 需要老板介入 | 解决方式 |
|---|--------|---------|------------|---------|
| 1 | **ESP-IDF cmake GitHub 子模块下载失败** | 固件编译完全阻塞 | ✅ 是 — 需购买 VPS (海外) 绕过网络限制 | 在 VPS 上 `git clone --recursive` + 编译 |
| 2 | **无小程序 AppID** | 微信小程序无法真机调试/发布 | ✅ 是 — 老板提供 AppID | 小程序管理后台注册获取 AppID |
| 3 | **腾讯地图插件未配置** | 小程序地图功能不可用 | ✅ 是 — 需 AppID 才能申请插件 | 获取 AppID 后在微信公共平台申请 |
| 4 | **无 VPS (海外)** | 固件编译、Telegram Bot、公网部署全阻塞 | ✅ 是 — 需要老板购买 | 推荐: 阿里云国际/HK VPS |
| 5 | **FCM/APNs 凭据文件缺失** | 推送通知完全不可用 | ✅ 是 — 需 Firebase/Apple 开发者账号 | 创建 Firebase 项目 + Apple Developer |
| 6 | **后端部署到公网** | 移动端只能在局域网使用 | — | VPS 上 docker-compose 部署 |
| 7 | **iOS 无 Xcode 项目文件** | iOS App 无法编译调试 | — | 从源码创建 Xcode 项目或使用 xcodegen |
| 8 | **Android Retrofit 类型不匹配** | Android 端 API 调用可能解析失败 | — | 修改 `ApiResponse<T>` 为直接模型匹配 |
| 9 | **围栏 API 字段名不统一** | 小程序围栏功能不通 | — | 统一使用 `lat`/`lng`/`enabled` |
| 10 | **3D 外壳脚本未验证** | 无法送打印 | — | 本地运行 Blender/OpenSCAD 验证输出 |

---

## 3. 团队工作分配 (12 个角色)

| 角色 | 人员当前状态 | 应负责的工作 |
|------|------------|------------|
| **老板 / 产品负责人** | ✅ 活跃 (聊天中) | 提供 AppID、购买 VPS、确认硬件规格、打样审批 |
| **PM** | ✅ 活跃 (当前角色) | 项目健康扫描、任务排期、阻塞项跟踪、风险监控 |
| **后端工程师** | ✅ 活跃 (AI Agent) | 后端已接近完成；下一步 VPS 部署 + Docker + Telegram Bot |
| **iOS 工程师** | 🟡 需启动 | 创建 Xcode 项目、真机调试、推送集成、发布准备 |
| **Android 工程师** | 🟡 需启动 | 修复 Retrofit 类型、真机调试、FCM 集成、发布准备 |
| **小程序工程师** | 🟡 等待资源 | 等 AppID 后配置腾讯地图、联调接口、发布体验版 |
| **固件工程师 (嵌入端)** | 🔴 等待 VPS | 在 VPS 上编译固件、烧录到 ESP32-S3、调试通信 |
| **硬件工程师 (PCB)** | 🔴 等待 VPS | PCB 原理图设计、布局布线、出 Gerber 文件打样 |
| **3D 设计师** | 🟡 需验证 | 运行 Blender/OpenSCAD 脚本验证外壳、导出 .stl |
| **测试工程师 (QA)** | 🟡 需启动 | 端到端测试、API 集成测试、固件 QA 固件 |
| **运维工程师** | 🔴 等待 VPS | VPS Linux 环境搭建、Docker 化部署、域名+SSL |
| **文档工程师** | ✅ 活跃 (AI Agent) | 技术文档、部署手册、API 文档 |

---

## 4. 下一步行动 (接下来 7 天排期)

### Day 1-2: 获取资源 (老板 + PM)

| 任务 | 负责人 | 详情 |
|------|--------|------|
| 购买 VPS | 老板 | 推荐: 阿里云国际 HK 轻量级 (2C4G 约 ¥34/月)；或搬瓦工/RAKsmart |
| 获取小程序 AppID | 老板 | 微信小程序管理后台注册 |
| 申请腾讯地图插件 | 老板 | 获取 AppID 后在微信公共平台申请 |
| 创建 Firebase 项目 | 老板/PM | Firebase Console 创建项目，下载 google-services.json 和 service account |
| 创建 Apple Developer 账号 | 老板 | 如果是发布到 App Store 需要 ($99/年) |

### Day 3-4: VPS 环境搭建 (PM + 后端 + 运维)

| 任务 | 详情 |
|------|------|
| VPS 基础配置 | Ubuntu 22.04/24.04, docker + docker-compose |
| ESP-IDF 编译环境 | `git clone --recursive -b v5.2.2 https://github.com/espressif/esp-idf.git` + install.sh |
| Git clone 项目 | `git clone` 本项目到 VPS |
| 后端容器化 | 写 Dockerfile + docker-compose.yml (FastAPI + Postgres + Redis + EMQX) |
| 域名 + SSL | 配置域名指向 VPS，Let's Encrypt 证书 |

### Day 3-4: 固件编译烧录 (固件工程师)

| 任务 | 详情 |
|------|------|
| 替换 config.h 占位符 | 填入实际 DEVICE_ID、MQTT_HOST、APN_NAME |
| ESP-IDF 编译 | `idf.py set-target esp32s3 && idf.py build` |
| 烧录到开发板 | `idf.py -p /dev/cu.usbmodem595B0960681 flash monitor` |
| 验证 MQTT 通信 | 查看设备上线数据是否出现在后端 API |

### Day 4-5: 移动端联调

| 任务 | 详情 |
|------|------|
| iOS 真机调试 | Xcode 创建项目、连接真机、测试注册/登录/地图 |
| Android 真机调试 | Android Studio 修复 Retrofit 类型、真机测试 |
| 小程序配置 | 填入 AppID、配置腾讯地图插件、联调全部接口 |
| 修复围栏字段 | 小程序 `latitude/longitude/enable` → `lat/lng/enabled` |

### Day 5-6: 推送集成

| 任务 | 详情 |
|------|------|
| FCM 配置 | 放入 google-services.json (Android) + service account (后端) |
| APNs 配置 | 放入 apns-key.p8 + 配置 topic |
| 推送测试 | 从后端触发推送，验证 Android/iOS 收到 |

### Day 6-7: 3D 外壳 + 硬件

| 任务 | 详情 |
|------|------|
| 验证 Blender 脚本 | 本地运行 `blender --python keepsafe_enclosure.py` 导出 .stl |
| 验证 OpenSCAD 脚本 | 本地渲染 `keepsafe_body_v2.scad` 导出 .stl |
| 3D 打印报价 | 提交 .stl 给 JLCPCB/嘉立创 3D 打印 |
| 硬件打样 | 如 PCB 设计就绪，出 Gerber 打样 |

---

## 5. 风险评估

| 风险 | 概率 | 影响 | 缓解方案 |
|------|------|------|---------|
| **ESP-IDF 编译失败** (子模块/GitHub 访问) | 高 | 高 | VPS (海外) 编译；或使用国内镜像 `git clone https://gitee.com/EspressifSystems/esp-idf.git` |
| **小程序 AppID 审批延迟** | 中 | 中 | 建议老板提前注册；可以先在开发者工具用测试 AppID |
| **3D 外壳不符合预期** | 中 | 中 | 先 FDM 打样低成本验证；确认后再走 SLS 或 CNC |
| **PCB 打样延迟** | 高 | 高 | 第一版用面包板+杜邦线验证电路，并行做 PCB |
| **推送通知不通过** (Apple/Google 审核) | 中 | 中 | 先用 polling 方案作为 fallback |
| **电池续航不达标** (< 7 天) | 中 | 高 | config.h 中 PSM + 深睡已优化 (~25 µA)；实际需实测调整上报频率 |
| **Github 子模块在国内同步超时** | 高 | 中 | 使用 `GIT_SSL_NO_VERIFY` + `GIT_TERMINAL_PROMPT=0` 或代理 |

---

## 6. 代码扫描发现的具体问题

### 6.1 后端

| 问题 | 文件 | 严重程度 | 建议 |
|------|------|---------|------|
| FCM 凭据文件缺失 | `app/config.py:57` | 中 | 创建 Firebase 项目并下载 service account |
| APNs 凭据文件缺失 | `app/config.py:60` | 中 | 获取 Apple Developer P8 密钥 |
| EMQX 未连接 (本地无 EMQX) | `app/mqtt_client.py:51` | 低 | 正常，部署到 VPS 后解决 |
| OpenCellID API Key 为占位符 | `app/config.py:66` | 中 | 注册 OpenCellID 或改为百度 LBS |
| JWT Secret 为占位符 | `app/config.py:80` | 高 | 生产环境必须更换为强随机密钥 |
| Redis 未运行 | `app/redis_cache.py:26` | 低 | dev_mode 下 fakeredis 自动处理 |

### 6.2 固件

| 问题 | 文件 | 严重程度 | 建议 |
|------|------|---------|------|
| DEVICE_ID 占位符 | `main/config.h:16` | 高 | 替换为实际设备 ID |
| MQTT Broker 占位符 | `main/config.h:60` | 高 | 部署 EMQX 后填入地址 |
| APN 占位符 | `main/config.h:56` | 高 | 填入运营商 APN (如 cmnbiot) |
| 无 sdkconfig | `code/firmware/` | 高 | 需 `idf.py set-target esp32s3` 生成 |

### 6.3 Android

| 问题 | 文件 | 严重程度 | 建议 |
|------|------|---------|------|
| `getProfile()` 返回 `ApiResponse<UserProfile>` | `ApiService.kt:36` | 中 | 后端直接返回 `UserProfile`，去掉包装 |
| `getDevices()` 返回 `ApiResponse<List<Device>>` | `ApiService.kt:47` | 中 | 同上 |
| `getDeviceLocation()` 返回 `ApiResponse<LocationData>` | `ApiService.kt:52` | 中 | 同上 |
| `getSosEvents()` 用 `List<*>` | `ApiService.kt:66` | 中 | 改为 `List<SosEvent>` |
| `bindDevice()` 返回 `ApiResponse<Unit>` | `ApiService.kt:71` | 中 | 改为 `BindResponse` |

### 6.4 小程序

| 问题 | 文件 | 严重程度 | 建议 |
|------|------|---------|------|
| 围栏字段名不匹配 | `utils/api.js` 或页面代码 | 中 | `latitude/longitude/enable` → `lat/lng/enabled` |
| 腾讯地图插件 AppID 占位符 | `app.json:42-43` | 高 | 获取 AppID 后替换 |

### 6.5 3D 外壳

| 问题 | 文件 | 严重程度 | 建议 |
|------|------|---------|------|
| Blender 脚本未运行过 | `code/hardware/blender/keepsafe_enclosure.py` | 中 | 运行 `blender --python keepsafe_enclosure.py` 验证输出 |
| 尺寸存在不一致 | HARDWARE_SPEC.md vs scad | 中 | 规格书说 R8mm，scad 注释说修正为 R4mm |

---

## 7. 总结

**项目当前状态:** 后端基本完工，三个移动端代码就绪但需联调，固件/硬件/3D 被 VPS 和 AppID 阻塞。

**关键行动项 (按紧急程度):**
1. **今天:** 老板购买 VPS → 解阻塞固件编译 + 公网部署
2. **今天:** 老板提供小程序 AppID → 解阻塞小程序开发
3. **Day 1-2:** VPS 上搭建 ESP-IDF + Docker 环境
4. **Day 2-3:** 编译固件并烧录到 ESP32-S3 开发板
5. **Day 3-5:** 三端联调 (iOS/Android/小程序) + 推送集成
6. **Day 5-7:** 3D 外壳验证 + 硬件打样准备

**完成度概览:**
| 类别 | 进度 |
|------|------|
| 后端 API | 95% ✅ |
| 移动端 (iOS/Android/小程序) | 60-70% 🟡 |
| 固件 (代码已完成, 待编译) | 30% (代码 90%, 编译 0%) 🔴 |
| 硬件/3D (规格已完成, 待打样) | 10-15% 🔴 |
| 部署/运维 | 0% 🔴 |
| **整体项目** | **~45%** 🟡 |

---

*报告由 AI PM Agent 自动生成。请老板审阅阻塞项并尽快决策。*

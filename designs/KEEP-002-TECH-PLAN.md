# KEEP-002 技术方案 — iOS / Android / 微信小程序

> 项目：KeepSafe 防丢器
> 版本：v1.0
> 状态：待审批

---

## 一、API 接口概览

后端已有基础（Base URL: `http://localhost:8000/api/v1`）：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/auth/device` | POST | 设备注册/绑定 | ✅ 已有 |
| `/auth/device/acl` | GET | 设备 ACL 查询 | ✅ 已有 |
| `/devices/{id}/location` | GET | 设备最新位置 | ✅ 已有 |
| `/devices/{id}/status` | GET | 设备状态（电量/连接） | ✅ 已有 |
| `/devices/{id}/history` | GET | 历史轨迹 | ✅ 已有 |
| `/devices/{id}/sos/events` | GET | SOS 事件列表 | ✅ 已有 |
| `/devices/bind` | POST | 绑定设备 | ✅ 已有 |
| `/devices/{id}/bind` | DELETE | 解绑设备 | ✅ 已有 |

### 需补充的接口（KEEP-002 开发时同步实现）

| 端点 | 方法 | 说明 | 优先级 |
|------|------|------|--------|
| `/auth/register` | POST | 用户注册 | P0 |
| `/auth/login` | POST | 用户登录（JWT） | P0 |
| `/devices/{id}/fence` | GET/POST/PUT/DELETE | 围栏 CRUD | P0 |
| `/alerts` | GET | 告警列表 | P0 |
| `/alerts/{id}/ack` | POST | 确认告警 | P0 |
| `/share/device/{id}` | POST | 生成共享链接 | P1 |
| `/share/join` | POST | 通过链接加入 | P1 |
| `/users/profile` | GET/PUT | 用户资料 | P1 |

---

## 二、iOS App（Swift + SwiftUI）

### 最低支持
- iOS 16+
- 设备：iPhone 11 起

### 架构
```
MVVM + Coordinator（导航）
├── Models（数据模型）
├── Services（网络/MQTT/推送）
│   ├── APIService（REST 请求）
│   ├── MQTTService（实时位置更新）
│   └── PushService（APNs 注册）
├── ViewModels（业务逻辑）
└── Views（SwiftUI 页面）
```

### 页面结构
```
TabView（底部 3 Tab）
├── 首页（地图）
│   ├── 设备位置标注
│   ├── 围栏区域绘制
│   ├── SOS 全屏告警弹窗
│   └── 底部设备状态卡片（电量/连接/运动状态）
├── 告警
│   ├── 告警列表（SOS/围栏进出/低电量）
│   └── 告警详情
└── 设置
    ├── 设备管理（绑定/解绑）
    ├── 用户资料
    ├── 围栏设置
    └── 位置共享管理
```

### 地图
- MapKit（iOS 原生，无需额外 Key）
- 标注：设备位置、围栏多边形、SOS 位置

### 推送
- APNs（通过后端 push/apns.py）
- 接收：SOS 告警、围栏告警、低电量

---

## 三、Android App（Kotlin + Jetpack Compose）

### 最低支持
- Android 12+（API 31）
- 架构建议使用：`~/.npm-global/bin/node`

### 架构
```
MVVM + Jetpack Navigation
├── data
│   ├── api（Retrofit）
│   ├── model（数据类）
│   └── repository（仓库层）
├── domain（usecase）
├── ui
│   ├── map（地图页）
│   ├── alert（告警页）
│   ├── settings（设置页）
│   └── components（通用组件）
└── di（Hilt 依赖注入）
```

### 页面结构（同 iOS 对齐）
```
BottomNavigation（3 Tab）
├── 地图首页
├── 告警列表
└── 设置页
```

### 地图
- Google Maps（API Key 需申请）
- 或改用 高德地图（国内兼容性更好）

### 推送
- FCM（Firebase Cloud Messaging）

---

## 四、微信小程序

### 定位
轻量级监护端，核心功能：
- 查看设备位置
- 接收 SOS/围栏告警
- 设置围栏
- 分享位置给家人

### 技术要点

| 项目 | 说明 |
|------|------|
| 框架 | 原生微信小程序 |
| 地图 | 腾讯地图插件（微信原生支持） |
| 登录 | 微信一键登录 |
| 通知 | 微信服务订阅通知 |
| 分享 | 微信分享卡片 |
| 包体积 | 严格控制 < 2MB |

### 页面结构
```
TabBar（3 Tab）
├── 首页地图（设备位置 + 围栏）
├── 消息（告警通知）
└── 我的（设备管理 + 设置）
```

### 小程序特有功能
- 通过微信分享位置给家人
- 服务订阅通知代替 Push（SOS/围栏）
- 微信登录免注册流程

---

## 五、推送方案对比

| 平台 | 方案 | 备注 |
|------|------|------|
| iOS | APNs | 需开发者账号 + p8 证书 |
| Android | FCM | 免费，需 Firebase 项目 |
| 微信小程序 | 订阅通知 | 一次订阅、7天内可多次推送 |

---

## 六、开发建议顺序

### MVP（第 1 轮，2 周）
1. 后端补充认证 + 围栏 API（搭配三端）
2. iOS：地图首页 + 设备位置 + SOS 告警
3. Android：同 iOS 功能对齐
4. 小程序：地图首页 + 告警接收

### 第 2 轮（第 3-4 周）
5. 历史轨迹回放（三端）
6. 围栏设置（三端）
7. 位置共享

### 第 3 轮（第 5-6 周）
8. 多设备管理
9. 运动状态展示
10. 性能优化 + 离线缓存

---

## 七、技术风险

| 风险 | 等级 | 应对 |
|------|------|------|
| Google Maps 国内访问不稳定 | 中 | 高德地图备选 |
| 小程序包体积超限 | 中 | 分包加载，地图插件不计入 2MB |
| 微信订阅通知模板审核 | 低 | 提前准备 SOS/围栏模板 |
| APNs 证书管理 | 低 | CI 自动续期提醒 |

# KeepSafe 小程序-后端 API 对齐检查

> 版本: v1.0
> 日期: 2026-06-11
> 后端: FastAPI /api/v1 (Swagger: http://43.163.5.90:8000/docs)

---

## 一、概览

| 项目 | 文件位置 | 状态 |
|------|----------|------|
| 后端 API | code/backend/app/api/*.py | 完整 (6 个路由模块) |
| 小程序 | src/miniapp/ | 部分实现 (2/6 页面) |

---

## 二、小程序页面状态

app.json 声明 6 个页面：

| 页面 | 路由 | JS | WXML | WXSS | 状态 |
|------|------|-----|------|------|------|
| index | pages/index/index | ✅ | ✅ | ✅ | 已实现 (mock数据) |
| sos | pages/sos/sos | ✅ | ✅ | ✅ | 已实现 (mock数据) |
| device | pages/device/device | ❌ | ❌ | ❌ | **缺失** |
| fence | pages/fence/fence | ❌ | ❌ | ❌ | **缺失** |
| login | pages/login/login | ❌ | ❌ | ❌ | **缺失** |
| bind | pages/bind/bind | ❌ | ❌ | ❌ | **缺失** |

---

## 三、API 端点对齐检查

### 3.1 登录页 (pages/login/login) — 缺失

对应后端 API:
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/users/login | 邮箱+密码登录, 返回 JWT token |

小程序需要实现:
- 邮箱/密码输入框
- 调用 login API → 存储 token (wx.setStorageSync)
- 登录成功后跳转 index 页
- 错误处理 (401 密码错误)

---

### 3.2 首页 (pages/index/index) — 已实现但有 TODO

对应后端 API:
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/users/me/devices | 获取设备列表 (含位置/电量) |
| GET | /api/v1/alerts/ | 获取告警列表 |

当前状态:
- ❌ 使用硬编码 mock 数据 (mockList)
- ❌ 未调用后端 API
- ❌ 未存储/使用 JWT token
- ❌ 没有鉴权 header

需要修改:
```javascript
// 当前: 硬编码 mock
const mockList = [
  { id: 1, name: '👴 爷爷', ... }
]

// 应该: 调用后端 API
wx.request({
  url: `${API_BASE}/api/v1/users/me/devices`,
  header: { Authorization: `Bearer ${token}` },
  success: (res) => { this.setData({ deviceList: res.data }) }
})
```

---

### 3.3 设备详情 (pages/device/device) — 缺失

对应后端 API:
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/devices/{id}/status | 设备状态 (在线/电量/信号) |
| GET | /api/v1/devices/{id}/location | 最新位置 (经纬度/速度) |
| GET | /api/v1/devices/{id}/history | 位置历史轨迹 |
| GET | /api/v1/devices/{id}/sos/events | SOS 事件列表 |

需要实现:
- 设备状态卡片 (在线/离线/电量/信号)
- 地图显示当前位置
- 位置历史轨迹回放
- SOS 事件列表
- 导航按钮

---

### 3.4 围栏管理 (pages/fence/fence) — 缺失

对应后端 API:
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/devices/{id}/fences | 围栏列表 |
| POST | /api/v1/devices/{id}/fences | 创建围栏 (圆形/多边形) |
| GET | /api/v1/devices/{id}/fences/{fid} | 单个围栏详情 |
| PUT | /api/v1/devices/{id}/fences/{fid} | 更新围栏 |
| DELETE | /api/v1/devices/{id}/fences/{fid} | 删除围栏 |

需要实现:
- 围栏列表 (名称/类型/半径/开关)
- 创建圆形围栏 (地图选点 + 半径)
- 创建多边形围栏 (地图绘制)
- 开关切换 (enabled)
- 删除确认

---

### 3.5 SOS 告警 (pages/sos/sos) — 已实现但有 TODO

对应后端 API:
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/devices/{id}/sos/events | SOS 事件 (当前页数据来源) |
| GET | /api/v1/devices/{id}/location | 获取 SOS 位置 |

当前状态:
- ❌ 使用硬编码 location (lat: 39.9042, lng: 116.4074)
- ❌ 未从后端获取 SOS 数据
- ❌ 电话号码硬编码 (13800138000)
- ✅ UI 交互逻辑完整

需要修改:
- 接收后端推送的 SOS 数据 (MQTT/WebSocket)
- 或轮询 /api/v1/devices/{id}/sos/events
- 使用真实位置信息
- 支持真实电话号码 (从用户 profile phone 字段)

---

### 3.6 设备绑定 (pages/bind/bind) — 缺失

对应后端 API:
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/devices/bind | 绑定设备 (需 device_id + token) |

需要实现:
- 输入设备 ID (KS-XXXXXXXX)
- 输入设备 Token (出厂密钥)
- 调用 bind API
- 成功提示 + 跳转设备列表

---

## 四、全局对齐问题

### 4.1 Token 管理
- 小程序未实现 JWT token 存储和全局使用
- 需要在 app.js 中存储 token (wx.setStorageSync)
- 所有 API 请求需要携带 Authorization: Bearer {token}

### 4.2 API Base URL 配置
- 需要统一配置 API_BASE (开发: localhost:8000, 生产: 43.163.5.90)
- 建议在 app.js 中定义全局常量

### 4.3 实时推送
- 当前 sys 页使用 setInterval 30s 轮询
- 后端支持 MQTT 实时推送 (需 WebSocket 或轮询 API)
- 建议: 先用轮询方案 (/api/v1/devices/{id}/location), 后续升级 WebSocket

### 4.4 页面命名不一致
- DEPLOY.md (旧版) 说 5 页面: login, index, alerts, sos-detail, profile
- app.json 实际声明: login, index, device, fence, sos, bind
- 存在差异: DEPLOY.md 有 "alerts" 和 "profile" 但 app.json 没有
- app.json 有 "device", "fence", "bind" 但 DEPLOY.md 没有

**建议**: 统一为 app.json 声明的 6 页面, 并补齐代码

---

## 五、优先级

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P0 | 创建 login 页面 | 用户入口, 无此页无法使用 |
| P0 | 实现 API 调用层 | token 管理 + 统一请求封装 |
| P1 | 重构 index 页面 | 替换 mock 数据为真实 API |
| P1 | 创建 bind 页面 | 设备绑定入口 |
| P2 | 创建 device 页面 | 设备详情 + 轨迹 |
| P2 | 创建 fence 页面 | 围栏管理 |
| P2 | 完善 sos 页面 | 对接真实数据 |

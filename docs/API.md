# KeepSafe Backend API 文档

> 版本: v1.1.0  
> Base URL: `http://43.163.5.90:8000`  
> API Prefix: `/api/v1`  
> Swagger UI: `http://43.163.5.90:8000/docs`

---

## 鉴权

所有 `/api/v1/*` 端点（除 `/health`, `/docs`, `/api/v1/users/register`, `/api/v1/users/login`, `/api/v1/auth/*` 外）需要 Bearer Token:

```
Authorization: Bearer <token>
```

Token 通过 `/api/v1/users/login` 获取，有效期由 `JWT_EXPIRE_MINUTES` 环境变量控制（默认 1440 分钟 = 24 小时）。

---

## 端点清单

### 1. 系统

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/health` | 否 | 健康检查 |
| GET | `/docs` | 否 | Swagger UI |

**GET /health** 响应:
```json
{
  "status": "ok",
  "service": "keepsafe-backend",
  "version": "1.1.0",
  "mqtt_connected": false
}
```

---

### 2. 用户认证 (Users)

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/v1/users/register` | 否 | 用户注册 |
| POST | `/api/v1/users/login` | 否 | 用户登录（返回 token） |
| GET | `/api/v1/users/profile` | 是 | 获取当前用户信息 |
| PUT | `/api/v1/users/profile` | 是 | 更新用户信息 |
| GET | `/api/v1/users/me/devices` | 是 | 获取我的设备列表 |
| POST | `/api/v1/users/me/push-token` | 是 | 注册推送 Token |

**POST /users/register** — 请求体:
```json
{
  "email": "user@example.com",
  "password": "mypassword",
  "nickname": "可选昵称"
}
```
- `email`: 必须包含 @ 和 .
- `password`: 至少 6 位
- 响应 201: `{"message": "User registered successfully"}`
- 响应 409: 邮箱已注册

**POST /users/login** — 请求体:
```json
{
  "email": "test@keepsafe.com",
  "password": "test123456"
}
```
- 响应 200:
```json
{
  "access_token": "eyJhbG...",
  "token_type": "bearer",
  "user_id": "test-uuid-001"
}
```

**GET /users/profile** — 响应:
```json
{
  "user_id": "test-uuid-001",
  "email": "test@keepsafe.com",
  "nickname": "Test",
  "avatar_url": null,
  "phone": null,
  "created_at": "2026-01-01T00:00:00Z"
}
```

**PUT /users/profile** — 请求体 (所有字段可选):
```json
{
  "nickname": "新昵称",
  "avatar_url": "https://...",
  "phone": "+861****8000"
}
```

**GET /users/me/devices** — 响应:
```json
[
  {
    "device_id": "KS-00000001",
    "nickname": "My Device",
    "bound_at": "2026-01-01T00:00:00Z",
    "is_active": true,
    "last_seen": "2026-06-08T12:00:00Z"
  }
]
```

**POST /users/me/push-token** — 请求体:
```json
{
  "platform": "ios",
  "token": "fcm-token-abc123"
}
```
- `platform`: `"ios"` 或 `"android"`
- 响应 400: 无效平台

---

### 3. 设备 (Devices)

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/v1/devices/{device_id}/status` | 是 | 获取设备状态 |
| GET | `/api/v1/devices/{device_id}/location` | 是 | 获取最新位置 |
| GET | `/api/v1/devices/{device_id}/history` | 是 | 获取位置历史 |
| GET | `/api/v1/devices/{device_id}/sos/events` | 是 | 获取 SOS 事件 |
| POST | `/api/v1/devices/bind` | 是 | 绑定设备 |
| DELETE | `/api/v1/devices/{device_id}/bind` | 是 | 解绑设备 |

**GET /devices/{id}/status** — 响应:
```json
{
  "device_id": "KS-00000001",
  "online": true,
  "battery": 85,
  "charging": false,
  "rssi": -65,
  "last_seen": "2026-06-08T12:00:00Z",
  "lat": 31.23,
  "lng": 121.47
}
```

**GET /devices/{id}/location** — 响应:
```json
{
  "device_id": "KS-00000001",
  "ts": "2026-06-08T12:00:00Z",
  "lat": 31.23,
  "lng": 121.47,
  "alt": 10.5,
  "speed": 2.5,
  "heading": 180.0,
  "accuracy": 5.0,
  "satellites": 12,
  "fix_type": 1,
  "cell_id": "46000-12345-67890",
  "battery": 85,
  "charging": false,
  "rssi": -65,
  "fw_version": "1.0.0"
}
```

**GET /devices/{id}/history** — 查询参数:
- `from` (datetime, 可选): 起始时间，默认当天 00:00
- `to` (datetime, 可选): 结束时间，默认当前
- `limit` (int, 1-1000): 最大返回条数，默认 100

**POST /devices/bind** — 请求体:
```json
{
  "user_id": "test-uuid-001",
  "device_id": "KS-00000001",
  "token": "device-secret-token",
  "nickname": "可选昵称"
}
```
- `token` 必须与设备的 `device_token` 匹配
- 如果设备不存在，会自动注册
- 响应 200: `{"success": true, "message": "Device bound successfully"}`
- 响应 403: `user_id` 与当前用户不匹配，或 token 不正确

**DELETE /devices/{id}/bind** — 响应:
```json
{"success": true, "message": "Device unbound successfully"}
```

---

### 4. 围栏 (Fences)

支持两种围栏类型: **圆形 (circle)** 和 **多边形 (polygon)**。

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/v1/devices/{device_id}/fences` | 是 | 获取围栏列表 |
| POST | `/api/v1/devices/{device_id}/fences` | 是 | 创建围栏 |
| GET | `/api/v1/devices/{device_id}/fences/{fence_id}` | 是 | 获取单个围栏 |
| PUT | `/api/v1/devices/{device_id}/fences/{fence_id}` | 是 | 更新围栏 |
| DELETE | `/api/v1/devices/{device_id}/fences/{fence_id}` | 是 | 删除围栏 |

**GET /devices/{id}/fences** — 响应:
```json
{
  "fences": [
    {
      "id": 1,
      "device_id": "KS-00000001",
      "name": "Home",
      "fence_type": "circle",
      "lat": 31.23,
      "lng": 121.47,
      "radius": 500,
      "vertices": null,
      "enabled": true,
      "created_at": "2026-06-08T12:00:00Z",
      "updated_at": "2026-06-08T12:00:00Z"
    }
  ],
  "total": 1
}
```

#### 4.1 圆形围栏 (Circle)

**POST /devices/{id}/fences** — 请求体:
```json
{
  "name": "Home",
  "fence_type": "circle",
  "lat": 31.23,
  "lng": 121.47,
  "radius": 500,
  "enabled": true
}
```
- `fence_type`: `"circle"` (默认)
- `lat` / `lng`: 圆心坐标，范围 [-90,90] / [-180,180]
- `radius`: 围栏半径（米），必须 > 0

#### 4.2 多边形围栏 (Polygon)

**POST /devices/{id}/fences** — 请求体:
```json
{
  "name": "School Zone",
  "fence_type": "polygon",
  "vertices": [
    {"lat": 31.2000, "lng": 121.4500},
    {"lat": 31.2200, "lng": 121.4500},
    {"lat": 31.2200, "lng": 121.4900},
    {"lat": 31.2000, "lng": 121.4900}
  ],
  "enabled": true
}
```
- `fence_type`: `"polygon"`
- `vertices`: 至少 3 个顶点，最多 100 个顶点
- 每个顶点 lat 范围 [-90,90], lng 范围 [-180,180]
- 不允许连续的重复顶点（退化边）

**PUT /devices/{id}/fences/{fid}** — 请求体 (所有字段可选):
```json
{
  "name": "Home Updated",
  "fence_type": "polygon",
  "radius": 1000,
  "vertices": [
    {"lat": 31.20, "lng": 121.40},
    {"lat": 31.22, "lng": 121.40},
    {"lat": 31.22, "lng": 121.44}
  ],
  "enabled": false
}
```
- 支持类型切换 (circle ↔ polygon)，切换后会忽略旧类型的字段
- 更新 polygon vertices 同样受 3-100 个顶点约束

---

### 5. 告警 (Alerts)

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/v1/alerts/` | 是 | 获取告警列表（分页） |
| PUT | `/api/v1/alerts/{alert_id}/read` | 是 | 标记单条已读 |
| PUT | `/api/v1/alerts/read-all` | 是 | 全部标记已读 |

**GET /alerts/** — 查询参数:
- `page` (int, 默认 1): 页码
- `page_size` (int, 1-100, 默认 20): 每页条数
- `alert_type` (str, 可选): 按类型筛选 (`sos`, `fence`, `geofence_enter`, `geofence_exit`, `low_battery`, `offline`)
- `is_read` (bool, 可选): 按已读/未读筛选

响应:
```json
{
  "items": [
    {
      "id": 1,
      "device_id": "KS-00000001",
      "ts": "2026-06-08T12:00:00Z",
      "alert_type": "geofence_enter",
      "payload": {"fence_id": 1, "fence_name": "Home", "event": "enter", "lat": 31.23, "lng": 121.47},
      "is_read": false
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

告警类型说明:
| alert_type | 触发条件 |
|-----------|---------|
| `sos` | 设备触发 SOS 紧急按钮 |
| `geofence_enter` | 设备进入围栏区域 |
| `geofence_exit` | 设备离开围栏区域 |
| `low_battery` | 电池电量低于阈值 (20%) |
| `offline` | 设备超过 5 分钟未上报 (1h 去重) |

---

### 6. 设备分享 (Device Sharing)

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/v1/devices/{device_id}/share` | 是 | 分享设备给其他用户 |
| GET | `/api/v1/devices/{device_id}/shares` | 是 | 查看设备分享列表 |
| DELETE | `/api/v1/devices/{device_id}/share/{share_id}` | 是 | 撤销分享 |
| GET | `/api/v1/devices/shared-with-me` | 是 | 查看分享给我的设备 |

**POST /devices/{id}/share** — 请求体:
```json
{
  "shared_with_email": "friend@example.com",
  "permissions": "view"
}
```
- `shared_with_email`: 目标用户邮箱（不能是自己）
- `permissions`: `"view"` (默认) 或 `"control"`
- 如果已存在活跃分享，会更新权限 (upsert)
- 响应 201:
```json
{
  "id": 1,
  "device_id": "KS-00000001",
  "owner_user_id": "test-uuid-001",
  "shared_with_user_id": "friend-uuid-002",
  "permissions": "view",
  "is_active": true,
  "shared_at": "2026-06-08T12:00:00Z",
  "revoked_at": null
}
```
- 响应 400: 分享给自己、权限无效
- 响应 404: 目标用户不存在

**GET /devices/{id}/shares** — 响应:
```json
{
  "shares": [
    {
      "id": 1,
      "device_id": "KS-00000001",
      "owner_user_id": "test-uuid-001",
      "shared_with_user_id": "friend-uuid-002",
      "permissions": "view",
      "is_active": true,
      "shared_at": "2026-06-08T12:00:00Z",
      "revoked_at": null
    }
  ],
  "total": 1
}
```
- 仅设备所有者可查看分享列表

**DELETE /devices/{id}/share/{share_id}** — 响应:
```json
{"message": "Share revoked successfully"}
```
- 撤销后 `is_active` 变为 `false`, `revoked_at` 记录时间
- 可重新分享同一用户（创建新的活跃分享）

**GET /devices/shared-with-me** — 响应:
```json
{
  "devices": [
    {
      "device_id": "KS-00000001",
      "device_nickname": "My Device",
      "owner_nickname": "Owner",
      "owner_email": "owner@example.com",
      "permissions": "view",
      "shared_at": "2026-06-08T12:00:00Z"
    }
  ],
  "total": 1
}
```

---

### 7. 设备认证 (Device Auth — EMQX 回调)

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/v1/auth/device` | 否 | EMQX 认证回调 |
| GET | `/api/v1/auth/device/acl` | 否 | EMQX ACL 回调 |

**POST /auth/device** — 请求体:
```json
{
  "device_id": "KS-00000001",
  "token": "device-token"
}
```
- 响应: `{"result": "allow"}` 或 `{"result": "deny"}`

**GET /auth/device/acl** — 查询参数:
- `device_id`: 设备 ID
- `topic`: MQTT topic (格式: `keepsafe/v1/{device_id}/...`)
- `action`: `"publish"` 或 `"subscribe"`

只有 device_id 与 topic 中的设备 ID 一致时才返回 `allow`。

---

## 错误码

| 状态码 | 说明 |
|--------|------|
| 200/201 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证或 token 无效 |
| 403 | 无权访问（设备不属于当前用户） |
| 404 | 资源不存在 |
| 409 | 冲突（如重复注册） |
| 422 | 请求体验证失败 |
| 500 | 服务器内部错误 |

---

## 数据模型字段约定

- 坐标: `lat` / `lng` (非 `latitude` / `longitude`)
- 启用状态: `enabled` (非 `enable`)
- 设备 Token: `device_token` / `token` (设备密钥，用于绑定校验)
- 告警类型: `alert_type` (非 `type`)
- 围栏类型: `fence_type`: `"circle"` | `"polygon"`
- 分享权限: `permissions`: `"view"` | `"control"`

---

## 测试

```bash
cd ~/projects/keepsafe/code/backend
source .venv/bin/activate
pytest tests/test_api.py -v
# 当前: 119 tests (2026-06-10)
# 覆盖: health/auth/devices/fences(alerts)/users/push/sharing/polygon/e2e
```

### E2E 完整流程测试

`TestE2EFullFlow::test_e2e_full_flow` 覆盖完整的用户旅程:

```
register → login → profile → bind device → my devices
  → create circle fence → create polygon fence → list fences
  → alerts accessible → mark all read → share device → revoke share
```

12 步顺序执行，验证所有主要 API 端点的端到端集成。

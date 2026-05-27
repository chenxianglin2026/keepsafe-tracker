# MiniApp 接入配置报告

> 生成时间: 2026-05-22
> 项目路径: ~/projects/keepsafe/code/miniapp/
> AppID: wx0b710cdc89537120
> 后端地址: http://192.168.110.34:8000/api/v1

---

## 1. AppID 配置

| 文件 | 状态 | 值 |
|------|------|-----|
| `project.config.json > appid` | ✅ 已填入 | `wx0b710cdc89537120` |
| `project.config.json > urlCheck` | ✅ 已设为 `false`（开发者工具不校验域名） | |
| `app.json` | ✅ 无需改动（全局配置不含 AppID 字段） | |

> `app.json` 中不包含 `appid` 字段，AppID 仅配置在 `project.config.json` 中，微信开发者工具会自动读取。

---

## 2. API Base URL 检查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| `utils/api.js` 中 `BASE_URL` | ✅ 正确 | `http://192.168.110.34:8000/api/v1` |
| `app.js` 中 `silentLogin` 请求地址 | ✅ 一致 | 同样使用 `http://192.168.110.34:8000/api/v1/users/profile` |
| 所有 API 路径前缀 | ✅ 一致 | 均以 `/api/v1` 开头后跟资源路径 |

**注意：** 当前后端运行在局域网地址 `192.168.110.34:8000`，微信小程序真机无法访问局域网地址。解决方案：

- **本地调试：** 在微信开发者工具中勾选「详情 → 本地设置 → 不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」
- **生产环境：** 将后端部署到公网 VPS，获取公网域名/IP，在「微信公众平台 → 开发 → 开发设置 → 服务器域名」配置 request 合法域名白名单
- **注意：** 小程序要求正式上线时必须使用 HTTPS，因此 VPS 部署时还需配置 SSL 证书

---

## 3. 微信登录流程检查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| `wx.login()` 调用 | ❌ **缺失** | 前端代码中**没有**任何 `wx.login()` 调用或微信登录相关逻辑 |
| `auth.js` 导出函数 | ❌ **仅邮箱登录** | 只实现了 `loginWithEmail()`, `register()`, `checkLogin()`, `getToken()`, `logout()` — 全部基于邮箱密码认证 |
| 后端微信登录接口 | ❌ **不存在** | 后端没有 `/api/v1/auth/wechat-login` 或类似接口 |

### 需要完成的工作

#### 3a. 后端新增微信登录接口

在 FastAPI 后端添加 `/api/v1/auth/wechat-login`，接收前端传来的 `code`，调用微信服务器换取 `openid`，返回 JWT token。

参考实现（在 `code/backend` 中找到 auth 相关文件后补充）：

```python
@router.post("/auth/wechat-login")
async def wechat_login(code: str, db: Session = Depends(get_db)):
    # 1. 调微信接口: GET https://api.weixin.qq.com/sns/jscode2session
    #    appid=wx0b710cdc89537120&secret=xxx&js_code={code}&grant_type=authorization_code
    # 2. 获取 openid / session_key
    # 3. 查找或创建用户
    # 4. 生成 JWT token 返回
```

#### 3b. 前端新增微信登录

在 `utils/auth.js` 中添加 `wechatLogin()` 函数：

```javascript
function wechatLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: (res) => {
        if (res.code) {
          api.post('/auth/wechat-login', { code: res.code })
            .then((result) => {
              const app = getApp()
              app.setAuth(result.access_token, result.user)
              resolve(result)
            })
            .catch(reject)
        } else {
          reject(new Error('微信登录失败：' + res.errMsg))
        }
      },
      fail: reject
    })
  })
}
```

同时建议将 `app.js` 的 `onLaunch` / `onShow` 中的静默登录流程改为优先尝试微信静默登录（`wx.login()` 静默获取 code），回退到 token 验证。

---

## 4. API 接口完整性检查

以下列出小程序源码中调用的所有 API 路径，与后端实际提供的接口做对照：

| 方法 | 路径 | 小程序端调用位置 | 后端状态 |
|------|------|------------------|----------|
| GET | `/users/profile` | `api.js:237`、`app.js:34` | ⚠️ 需确认 |
| PUT | `/users/profile` | `api.js:244` | ⚠️ 需确认 |
| POST | `/users/login` | `api.js:222` | ⚠️ 需确认 |
| POST | `/users/register` | `api.js:231` | ⚠️ 需确认 |
| GET | `/users/me/devices` | `api.js:95` | ⚠️ 需确认 |
| POST | `/users/me/push-token` | `api.js:252` | ⚠️ 需确认 |
| POST | `/devices/bind` | `api.js:105` | ⚠️ 需确认 |
| DELETE | `/devices/{id}/bind` | `api.js:118` | ⚠️ 需确认 |
| GET | `/devices/{id}/location` | `api.js:125` | ⚠️ 需确认 |
| GET | `/devices/{id}/status` | `api.js:132` | ⚠️ 需确认 |
| GET | `/devices/{id}/history` | `api.js:142` | ⚠️ 需确认 |
| GET | `/devices/{id}/sos/events` | `api.js:149` | ⚠️ 需确认 |
| GET | `/devices/{id}/fences` | `api.js:160` | ⚠️ 需确认 |
| POST | `/devices/{id}/fences` | `api.js:168` | ⚠️ 需确认 |
| PUT | `/devices/{id}/fences/{fid}` | `api.js:178` | ⚠️ 需确认 |
| DELETE | `/devices/{id}/fences/{fid}` | `api.js:186` | ⚠️ 需确认 |
| GET | `/alerts/` | `api.js:197` | ⚠️ 需确认 |
| PUT | `/alerts/{id}/read` | `api.js:204` | ⚠️ 需确认 |
| PUT | `/alerts/read-all` | `api.js:210` | ⚠️ 需确认 |
| **GET** | **`/devices/{id}/share-link` (或类似)** | **`index.js:362`** | ❌ **缺失** — 调用 `api.getShareLink()` 但该函数在 `api.js` 中未定义 |

**关键发现：** `api.getShareLink()` 在 `index.js:362` 被调用，但 `api.js` 中并未定义该函数。需要在 `api.js` 补充：

```javascript
api.getShareLink = (deviceId) => api.get(`/devices/${deviceId}/share-link`)
```

---

## 5. 腾讯地图 Key 配置

| 文件 | 占位符 | 状态 |
|------|--------|------|
| `app.json` 第 42 行 | `{{PLACEHOLDER_TENCENT_MAP_PLUGIN_VERSION}}` | ❌ 未替换 |
| `app.json` 第 43 行 | `{{PLACEHOLDER_TENCENT_MAP_PLUGIN_PROVIDER}}` | ❌ 未替换 |
| `fence-picker.js` 第 7 行 | `{{PLACEHOLDER_TENCENT_MAP_PLUGIN_KEY}}` | ❌ 未替换 |
| `project.config.json` 第 33 行 | `{{PLACEHOLDER_LIB_VERSION}}` | ❌ 未替换 |

### 需要完成的配置

前往 [腾讯位置服务](https://lbs.qq.com/) 完成以下操作：

1. 注册开发者账号，创建应用（关联此小程序 AppID: `wx0b710cdc89537120`）
2. 获取 **地图插件 Key**（用于 `fence-picker.js`）
3. 获取 **地图插件 ProviderID**（用于 `app.json` 的 `plugins` 配置）
4. 确认当前腾讯地图插件最新版本号（约 `1.3.0`，用于 `app.json`）

替换后的参考值：

```json
// app.json plugins 段
"plugins": {
  "mapPlugin": {
    "version": "1.3.0",
    "provider": "wx5bc2ac602a747594"  // 示例，实际需申请
  }
}
```

```javascript
// fence-picker.js 第 7 行
const plugin = requirePlugin('你的腾讯地图插件Key')
```

---

## 6. 配置项完整清单

| # | 配置项 | 当前值 | 目标值 | 优先级 |
|---|--------|--------|--------|--------|
| 1 | AppID | `wx0b710cdc89537120` ✅ | 已填入 | 已完成 |
| 2 | API Base URL | `http://192.168.110.34:8000/api/v1` | 生产环境改为 HTTPS 公网域名 | 部署时 |
| 3 | 腾讯地图插件 Key | 占位符 | 从腾讯位置服务获取 | 🔴 高 |
| 4 | 腾讯地图插件 ProviderID | 占位符 | 从腾讯位置服务获取 | 🔴 高 |
| 5 | 腾讯地图插件版本号 | 占位符 | 最新版（如 `1.3.0`） | 🔴 高 |
| 6 | 基础库版本 | 占位符 | `3.3.0` 或更高 | 🟡 中 |
| 7 | 微信登录（后端） | 缺失 | 新增 `/api/v1/auth/wechat-login` | 🟡 中 |
| 8 | 微信登录（前端） | 缺失 | 新增 `wechatLogin()` 函数 | 🟡 中 |
| 9 | `api.getShareLink()` | 缺失 | 补充函数定义 | 🟢 低 |
| 10 | 服务器域名白名单 | 未配置 | 生产环境需在微信后台配置 | 部署时 |

---

## 7. 本地调试指引

由于后端运行在局域网地址 `192.168.110.34:8000`，小程序无法直接访问，本地调试需要：

1. 打开微信开发者工具，导入 `code/miniapp/` 目录
2. 点击顶部「详情」→「本地设置」
3. 勾选 **「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」**
4. 确保后端服务已在 `192.168.110.34:8000` 正常运行
5. 编译运行即可进行接口调试

> ⚠️ 注意：真机预览/调试时，手机也需要能够访问 `192.168.110.34:8000`（需在同一局域网）。
> 如果无法访问，考虑使用内网穿透工具（如 ngrok, frp）临时暴露后端到公网地址。

---

## 8. 生产环境部署注意事项

当后端部署到 VPS 后：

1. **更新 `api.js` 和 `app.js` 中的 BASE_URL** 为生产环境公网地址（如 `https://api.keepsafe.com/api/v1`）
2. **配置微信小程序后台服务器白名单：**
   - 登录 [微信公众平台](https://mp.weixin.qq.com/)
   - 进入「开发 → 开发设置 → 服务器域名」
   - 添加 request 合法域名（生产环境公网域名）
   - 添加 socket 合法域名（如有 WebSocket 需求）
3. **配置 SSL 证书** — 小程序强制要求 HTTPS
4. **提交审核前** 确保所有占位符已替换，所有功能可正常使用
5. **审核通过后** 用户端即可正常使用

---

## 9. 文件变更摘要

| 文件 | 变更 |
|------|------|
| `project.config.json` | ✅ `appid` → `wx0b710cdc89537120` |
| `project.config.json` | ✅ `urlCheck` → `false`（本地调试不校验域名） |

**未修改但需要后续处理的文件：**

| 文件 | 需要操作 |
|------|---------|
| `app.json` | 替换腾讯地图插件 version/provider |
| `fence-picker.js` | 替换腾讯地图插件 Key |
| `project.config.json` | 替换 `libVersion` 占位符 |
| `utils/auth.js` | 新增微信登录函数 |
| `utils/api.js` | 新增 `getShareLink` 和微信登录 API 调用 |
| `app.js` | 优化静默登录流程，支持微信自动登录 |

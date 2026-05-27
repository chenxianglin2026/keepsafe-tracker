# KeepSafe 微信小程序 MVP

轻量级监护端微信小程序。

## 项目结构

```
miniapp/
├── app.json              # 全局配置（含腾讯地图插件注册）
├── app.js                # App 生命周期、登录逻辑
├── app.wxss              # 全局样式（深色主题）
├── project.config.json   # 项目配置（含占位符）
├── sitemap.json          # 搜索配置
├── pages/
│   ├── index/            # 首页地图（腾讯地图组件 + 设备标记 + 状态栏）
│   ├── alerts/           # 告警列表（SOS/围栏/低电量/离线）
│   └── profile/          # 我的（用户信息 + 设备管理 + 设置）
├── components/
│   ├── device-card/      # 设备状态卡片（在线/离线/电量/距离）
│   └── fence-picker/     # 围栏设置弹窗（半径/位置/启用）
├── utils/
│   ├── api.js            # REST API 封装（baseUrl: http://localhost:8000/api/v1）
│   ├── auth.js           # 微信登录 + Token 管理
│   └── map.js            # 腾讯地图工具函数（距离计算/时间格式化）
└── images/               # 占位图标（需替换为正式图标）
```

## 核心功能

1. **地图查看设备位置** - 腾讯地图插件，实时标记设备位置
2. **接收 SOS/围栏告警** - 告警列表页，支持筛选和标记已读
3. **设置围栏** - 围栏组件，支持选择位置和半径
4. **分享位置给家人** - 生成分享链接/卡片

## 配置占位符

部署前需替换以下占位符：

| 占位符 | 说明 |
|--------|------|
| `{{PLACEHOLDER_APP_ID}}` | 微信小程序 AppID |
| `{{PLACEHOLDER_LIB_VERSION}}` | 基础库版本（如 3.3.0） |
| `{{PLACEHOLDER_TENCENT_MAP_PLUGIN_VERSION}}` | 腾讯地图插件版本（如 1.3.0） |
| `{{PLACEHOLDER_TENCENT_MAP_PLUGIN_PROVIDER}}` | 腾讯地图插件 ProviderID |
| `{{PLACEHOLDER_TENCENT_MAP_PLUGIN_KEY}}` | 腾讯地图插件 Key（在 fence-picker.js 中） |

## API 地址

所有接口地址：`http://localhost:8000/api/v1`

## 包体积控制

- 使用腾讯地图插件（微信原生支持，不计入包体积）
- 最小化依赖，无第三方 npm 包
- 组件按需加载
- 图片资源仅使用占位符（67 bytes/个）

## 后端 API 需求

小程序依赖以下后端接口（REST API）：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/auth/wx-login` | POST | 微信登录（code → token） |
| `/auth/verify` | GET | Token 验证 |
| `/user/profile` | GET/PUT | 用户信息 |
| `/devices` | GET | 设备列表 |
| `/devices/bind` | POST | 绑定设备 |
| `/devices/{id}` | DELETE | 解绑设备 |
| `/devices/{id}/location` | GET | 设备最新位置 |
| `/devices/{id}/location/history` | GET | 位置历史 |
| `/devices/{id}/fences` | GET/POST | 围栏列表/创建 |
| `/devices/{id}/fences/{fid}` | PUT/DELETE | 更新/删除围栏 |
| `/alerts` | GET | 告警列表 |
| `/alerts/{id}/read` | PUT | 标记已读 |
| `/alerts/read-all` | PUT | 全部已读 |
| `/share` | POST | 生成分享链接 |

# 团队组建与角色配置（v1.2）

> 更新内容：新增 UI 工程师（ui-dev）、微信小程序开发（miniapp-dev）
> 更新日期：2026-05-09

---

## 一、团队架构（v1.2）

```
                   你（老板）
        提需求 · 审批方案 · 填密钥 · 看结果
                      │
           Hermes Agent（项目经理）
       方案 · 派单 · 跟进 · 验证 · 归档
                      │
        ┌─────────────┼─────────────┐
        │             │             │
    ┌───┴───┐   ┌────┴────┐   ┌───┴───┐
    │开发团队│   │质量团队 │   │基础团队│
    └───┬───┘   └────┬────┘   └───┬───┘
        │             │             │
  ┌─────┼─────┐   ┌──┴──┐     ┌───┴───┐
  │     │     │   │     │     │       │
 🏗    🔧    📐  🧪   👁     📚     ⚙️
Arch  Emb  Mech  QA  Reviewer Lib   PM
  💻    🎨    📱
 BE   UI/UX  iOS
  🤖    📱
 And  MiniApp
```

## 二、全部团队成员

| 代号 | 角色 | 职责 | 工具集 | 技能 |
|------|------|------|--------|------|
| `architect` | 🏗 架构师 | 技术方案、架构决策、技术选型评审 | file, terminal | writing-plans |
| `be-dev` | 💻 后端开发 | 后端 API、数据库、MQTT、推送 | file, terminal | tdd |
| `ios-dev` | 📱 iOS 开发 | Swift App、地图、定位权限 | file, terminal | tdd |
| `and-dev` | 🤖 安卓开发 | Kotlin App、地图、后台保活 | file, terminal | tdd |
| `emb-dev` | 🔧 嵌入式开发 | 固件、GPS/BLE/4G 驱动、低功耗 | file, terminal | - |
| `mech-dev` | 📐 结构工程师 | 3D 建模、内部堆叠、外壳设计、防水结构 | file, terminal | - |
| **`ui-dev`** | **🎨 UI 工程师** | **App 界面实现、交互设计、适老化设计** | file, terminal | - |
| **`miniapp-dev`** | **📱 小程序开发** | **微信小程序开发、微信登录/支付/通知** | file, terminal | - |
| `qa` | 🧪 测试工程师 | 功能/集成/压力测试 | file, terminal | - |
| `reviewer` | 👁 代码验证人 | 代码审查、安全审查 | file, search | requesting-code-review |
| `librarian` | 📚 资料管理员 | 知识库维护、方案归档 | file | - |

## 三、团队规模

| 类型 | 角色数 | 角色 |
|------|--------|------|
| 🏗 架构 | 1 人 | Architect |
| 💻 后端 | 1 人 | BE-Dev |
| 📱 前端 | **4 人** | iOS-Dev, And-Dev, **UI-Dev**, **MiniApp-Dev** |
| 🔧 硬件 | 2 人 | Emb-Dev, Mech-Dev |
| 🧪 质量 | 2 人 | QA, Reviewer |
| 📚 管理 | 2 人 | Librarian, PM（Hermes 兼）|
| **合计** | **12 人** | |

## 四、当前状态

| 项目 | 状态 |
|------|------|
| 团队配置 | ✅ 12 个角色（新增 UI 工程师 + 小程序开发）|
| KEEP-001 开发 | ✅ 后端 22 文件完成 / ✅ 固件 15 文件完成 / ⏳ 结构进行中 |
| 待启动 | ⏳ KEEP-002：App 端 + 小程序方案（需你提供外观图）|

# KeepSafe 项目重建报告

> 编制：Hermes（项目经理）
> 日期：2026年5月27日
> 状态：团队重建 + 资料梳理完成

---

## 一、项目概况

| 项目 | KeepSafe — 老人小孩防丢器 |
|------|--------------------------|
| 定位 | 40×30×10mm 迷你定位器，续航30天，售价¥199 |
| 目标用户 | 老人（挂绳/磁吸夹）+ 儿童（鞋带扣/腕带） |
| 核心功能 | 实时定位 + 电子围栏 + SOS双重求救 + 微信小程序 |
| 芯片方案 | 展锐8910（集成GPS+BLE+4G） |
| BOM成本 | ¥43（v3优化后） |
| 开发阶段 | Phase 0 MVP（计划2个月） |

## 二、文件资产清单

### 2.1 产品文档（tracker/）
| 文件 | 说明 |
|------|------|
| prd-final.md | 产品需求文档（304行），含硬件规格、功能列表、成本定价 |
| product-plan-v2.md | 产品规划v2（413行），老人/小孩双场景方案 |
| product-plan-v3.md | 深度优化v3（300行），芯片降本、续航翻倍、MVP策略 |
| phase0-tasks.md | Phase 0 可执行任务拆解（208行），含甘特图 |

### 2.2 项目管理（keepsafe/）
| 文件 | 说明 |
|------|------|
| TEAM_ARCH.md | 团队架构 v2.0（12个虚拟角色 + OpenClaw VPS Agent） |
| TEAM_SETUP.md | 团队组建配置 v1.2 |
| AI_DEV_MANAGEMENT.md | AI原生开发管理方案（7步流程） |
| PROJECT-HEALTH.md | 项目健康扫描（321行），含10项阻塞项 |
| decisions.md | 共享记忆库（决策记录、踩坑、术语表） |
| 任命开发总监.md | OpenClaw 被任命为开发总监（2026-05-20） |

### 2.3 源代码资产

| 模块 | 文件数 | 完成度 | 状态 |
|------|--------|--------|------|
| 后端 Python (FastAPI) | 27个 | 95% | ✅ 可运行（localhost:8000） |
| 后端 Node.js | — | 第二套 | src/backend/ 独立实现 |
| iOS Swift | 14个 | 70% | 🟡 缺 Xcode 项目文件、推送凭据 |
| Android Kotlin | 13个 | 70% | 🟡 Retrofit 类型需修复 |
| 固件 C (ESP32-S3) | 16个 | 90%代码 | 🔴 编译阻塞（ESP-IDF 子模块） |
| 微信小程序 JS | 9个 | 60% | 🟡 等 AppID + 腾讯地图插件 |
| 3D外壳 Blender | 1个(412行) | 未验证 | 🔴 脚本已写，未运行 |
| 3D外壳 OpenSCAD | 2个 | 未验证 | 🔴 已写，未渲染 |

### 2.4 设计/规格文档
| 文件 | 路径 |
|------|------|
| 结构需求规格书 | docs/结构需求规格书.md |
| 电子结构完整方案 | docs/电子与结构完整方案.md |
| 硬件采购清单 | requirements/HARDWARE-PURCHASE-LIST.md |
| 安全策略 | knowledge/sdlc/SECURITY_POLICY.md |
| API修复报告 | tests/API-FIX-REPORT.md |
| 小程序配置报告 | tests/MINIAPP-SETUP-REPORT.md |

---

## 三、当前阻塞项（按优先级）

| # | 阻塞项 | 影响 | 需要陈总 |
|---|--------|------|---------|
| 1 | **小程序 AppID** | 小程序无法真机调试 | ✅ 提供 |
| 2 | **腾讯地图插件 Key** | 小程序地图不可用 | ✅ 申请 |
| 3 | **固件编译环境** | ESP32固件从未编译 | 可本地解决 |
| 4 | **FCM/APNs 凭据** | 推送通知不可用 | ✅ Firebase/Apple账号 |
| 5 | **USB转TTL烧录线** | 固件无法烧录到ESP32 | ✅ 购买（¥5-10） |
| 6 | **后端部署到公网** | 移动端仅局域网可用 | — |
| 7 | **iOS Xcode项目** | iOS无法编译 | — |
| 8 | **Android类型修复** | API调用可能失败 | — |
| 9 | **围栏字段统一** | 小程序围栏不通 | — |
| 10 | **3D外壳验证** | 无法送打印 | — |

---

## 四、团队重建方案

### 4.1 新架构（适配当前能力）

```
                    陈总（老板）
                定方向 · 审批 · 提供资源
                        │
              Hermes（项目经理 + 主工程师）
         方案设计 · 代码开发 · 团队调度 · 质量把关
                        │
        ┌───────────────┼───────────────┐
        │               │               │
   delegate_task   delegate_task   delegate_task
   (子代理1)       (子代理2)       (子代理3)
   可并行委派       可并行委派       可并行委派
```

### 4.2 12个角色重新分配

| 角色 | 旧负责 | 新负责 | 说明 |
|------|--------|--------|------|
| Architect | 虚拟角色 | Hermes + delegate_task | 方案设计 |
| BE-Dev | 虚拟角色 | Hermes 直接 | 后端已完成95% |
| iOS-Dev | 虚拟角色 | delegate_task | 创建Xcode项目 |
| And-Dev | 虚拟角色 | delegate_task | 修复Retrofit类型 |
| MiniApp-Dev | 虚拟角色 | delegate_task | 配置+联调 |
| Emb-Dev | 虚拟角色 | delegate_task | 本地编译固件 |
| Mech-Dev | 虚拟角色 | delegate_task | 验证Blender/OpenSCAD |
| UI-Dev | 虚拟角色 | delegate_task | 适老化界面 |
| QA | 虚拟角色 | delegate_task | 测试验证 |
| Reviewer | 虚拟角色 | delegate_task | 代码审查 |
| Librarian | 虚拟角色 | Hermes 自动 | 文档归档 |
| OpenClaw | VPS Agent | ⚠️ 暂不可用 | 等VPS恢复 |

### 4.3 与原团队的主要变化

- **OpenClaw 暂不可用**：原VPS Agent（43.163.5.90）连接状态未知，固件编译改为本地执行
- **并行度降为3路**：原12虚拟角色可无限并行，现在 delegate_task 最多同时3个
- **Hermes 可以直接写代码**：原"三条铁律"规定PM不写代码，现在简化流程，小任务直接执行

---

## 五、防丢失备份方案（避免再次被删）

### 5.1 立即执行

1. **Git 初始化并推送远程**
   ```
   cd ~/projects/keepsafe
   git init
   git add .
   git commit -m "项目重建归档 - 2026-05-27"
   git remote add origin <陈总提供GitHub仓库地址>
   git push -u origin main
   ```

2. **关键配置文件备份**
   - 小程序 AppID、AppSecret → 单独加密存储
   - 腾讯地图 Key
   - FCM/APNs 凭据

### 5.2 长期保护

| 措施 | 说明 |
|------|------|
| Git 远程仓库 | 所有代码+文档推送到 GitHub 私有仓库 |
| 定期备份 | cronjob 每周自动 git push |
| 密钥隔离 | 密钥不进 Git，单独存 `~/.hermes/secrets/` |
| 文档规范 | 每次会议/决策必有 Markdown 记录 |
| 团队记忆 | decisions.md 持续更新，避免重复踩坑 |

---

## 六、建议下一步

1. **陈总提供**：小程序 AppID + 腾讯地图 Key（P0阻塞）
2. **本地执行**：验证 ESP-IDF 编译环境、验证 3D 外壳脚本
3. **并行开发**：iOS Xcode 项目创建 + Android Retrofit 修复 + 小程序配置
4. **推送集成**：Firebase 项目创建 + FCM/APNs 配置

---

> 项目整体完成度：约 **45%**
> 代码就绪，关键阻塞在外部资源（AppID、Key、凭据）
> 陈总提供资源后，2周内可完成 Phase 0 MVP

# KeepSafe 团队角色清单

> 版本: 3.0 | 总人数: 5人+4子代理

---

## 一、核心团队（5人）

### 陈总 — 老板
- 职责：定方向、提供资源(AppID/Key/资金)、审批方案、验收结果
- 不做：技术细节、过程管理
- 需要时提供：小程序AppID、腾讯地图Key、Firebase项目、Apple开发者账号、USB线

### OpenClaw — 项目总监
- 部署：VPS 43.163.5.90
- 职责：技术架构决策、代码审查、固件编译、后端部署、质量验收
- 工具：ESP-IDF、Docker、Git
- 调用方式：Hermes 通过 SSH 下发任务

### Hermes — 项目经理
- 部署：本地 Mac M5 Pro
- 职责：日常任务推进、团队调度、代码开发、测试验证、文档归档、汇报
- 工具：delegate_task(3路子代理)、terminal、file

### 子代理-开发 1
- 类型：delegate_task 按需委派
- 职责：后端开发 / 小程序开发 / iOS开发
- 工具集：terminal, file

### 子代理-开发 2
- 类型：delegate_task 按需委派
- 职责：Android开发 / 固件开发 / 3D设计
- 工具集：terminal, file

## 二、虚拟角色（按需激活）

| 角色 | 激活条件 | 委派方式 |
|------|---------|---------|
| 🔧 嵌入式工程师 | 固件修改 | delegate_task(子代理2) |
| 💻 后端工程师 | API修改 | delegate_task(子代理1) |
| 📱 前端工程师 | 小程序/App | delegate_task(子代理1) |
| 📐 3D设计师 | 外壳修改 | delegate_task(子代理2) |
| 🧪 测试工程师 | 功能验证 | delegate_task(子代理1或2) |
| 👁 代码审查 | PR审查 | OpenClaw 或 delegate_task |
| 📚 文档管理员 | 持续 | Hermes 自动 |

## 三、任务分派矩阵

| 任务类型 | 复杂度 | 执行者 |
|---------|--------|--------|
| 简单修改(1文件) | 低 | Hermes 直接 |
| 中等开发(3-5文件) | 中 | delegate_task 单子代理 |
| 复杂开发(5+文件) | 高 | delegate_task 多子代理并行 |
| 固件编译 | — | OpenClaw (VPS) |
| 后端部署 | — | OpenClaw (VPS) |
| 代码审查 | — | OpenClaw |
| 市场调研 | — | delegate_task 并行 |

## 四、不超负荷原则

- Hermes 同时维护 ≤ 2 个模块
- 每个子代理单次任务 ≤ 5 个文件
- OpenClaw 专注编译+部署+审查，不写业务代码
- 任何角色遇到阻塞立即上报，不硬扛

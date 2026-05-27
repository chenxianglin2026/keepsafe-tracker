# 内测推进报告

---

## 已完成 ✅

| # | 任务 | 负责人 | 产出 |
|---|------|--------|------|
| 1 | Docker 基础设施 | Architect | Dockerfile, docker-compose.yml, .dockerignore |
| 2 | 后端环境搭建 | BE-Dev | .venv 依赖安装完成、config 验证通过 |
| 3 | 数据库初始化 | BE-Dev | dbschema/init.sql（含 TimescaleDB）|
| 4 | 目录结构整理 | BE-Dev | credentials/ 目录、旧 init.sql 迁移 |

## 进行中 / 阻塞 ⏳

| # | 任务 | 负责人 | 阻因 |
|---|------|--------|------|
| 5 | ESP-IDF 工具链安装 | Emb-Dev | ❌ 需要 sudo 密码装 Homebrew |
| 6 | OpenSCAD + STL 渲染 | Mech-Dev | ❌ 需要 sudo 密码装 Homebrew |
| 7 | 后端启动验证 | QA | ❌ 需要你填 .env 密钥 |
| 8 | KEEP-002 App 开发 | iOS/And/MiniApp | ❌ 需要你的外观结构图 |

## 需要你配合

1. **sudo 密码** → 我装 Homebrew 和工具链
2. **填 .env** → 数据库/Redis/EMQX 密码
3. **外观结构图** → 启动三端 App 开发
4. **采购硬件** → ESP32-S3 + Air780E 烧录固件实测

## 文件清单

| 文件 | 路径 |
|------|------|
| 本周工作安排 | `requirements/WEEKLY-PLAN.md` |
| 内测推进方案 | `requirements/BETA-READINESS-PLAN.md` |
| 下一步行动 | `requirements/NEXT-STEPS.md` |
| Dockerfile | `code/backend/Dockerfile` |
| docker-compose.yml | `code/backend/docker-compose.yml` |
| 数据库初始化 | `code/backend/dbschema/init.sql` |

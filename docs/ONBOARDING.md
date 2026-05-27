# KeepSafe 团队重建手册

> **如果团队被删 / 上下文丢失 / 新人接手，按此手册操作。**

---

## 第一步：环境确认（5分钟）

```bash
# 确认 Mac 基础环境
python3 --version      # 应 ≥ 3.9
node --version         # 应 ≥ 22
git --version          # 应 ≥ 2.5
docker --version       # 应已安装

# 确认项目存在
ls ~/projects/keepsafe/code/
ls ~/projects/tracker/

# 确认 VPS 可连接
ssh -i ~/.ssh/keepsafe-v2 root@43.163.5.90 "echo OK"
```

## 第二步：启动后端（2分钟）

```bash
cd ~/projects/keepsafe/code/backend
.venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
curl http://localhost:8000/health
# 应返回: {"status":"ok","version":"1.1.0"}
```

## 第三步：插入测试数据

```bash
cd ~/projects/keepsafe/code/backend
.venv/bin/python3 seed_mock.py
# 插入: 2台设备(KS0001/KS0002), 3条告警
```

## 第四步：打开小程序

```
微信开发者工具 → 导入项目 → ~/projects/keepsafe/code/miniapp/
AppID: wxebce4c590760c9e3
```

## 第五步：建立团队

告诉 Hermes Agent：
```
"组建 KeepSafe 项目团队，OpenClaw 任项目总监"
```

## 项目速查

| 查什么 | 在哪 |
|--------|------|
| 项目架构 | docs/ARCHITECTURE.md |
| 开发流程 | docs/WORKFLOW.md |
| 角色分工 | docs/ROLES.md |
| 团队架构 | TEAM_ARCH_V3.md |
| 产品需求 | tracker/prd-final.md |
| 产品方案 | tracker/product-plan-v3.md |
| 任务清单 | tracker/phase0-tasks.md |
| 健康检查 | requirements/PROJECT-HEALTH.md |
| API路由 | code/backend/app/api/ |
| 共享决策 | shared-memory/decisions.md |

## 常见问题

**Q: 后端启动报错？**
A: 检查是否 dev_mode=True（config.py），确认 SQLite 文件存在。

**Q: 小程序连不上后端？**
A: 检查 api.js 中 BASE_URL 是否为 `http://localhost:8000/api/v1`。

**Q: VPS 连不上？**
A: 重新生成 SSH Key → 腾讯云控制台添加公钥。

**Q: 固件烧录失败？**
A: 先用 esptool flash-id 检查 Flash 大小（应该是16MB），用匹配参数烧录。

**Q: DeepSeek API 报 401？**
A: 聊天已改用本地回复，不受影响。如需恢复 AI，更新 ~/.hermes/.env 中的 DEEPSEEK_API_KEY。

## 测试账号

| 邮箱 | 密码 |
|------|------|
| test@keepsafe.com | test123456 |

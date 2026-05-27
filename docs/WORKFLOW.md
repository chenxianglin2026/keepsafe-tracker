# KeepSafe 开发流程规范

> 版本: 1.0 | 强制遵守 | 违规阻止合并

---

## 一、开发七步法

```
Step 1: 需求确认
  陈总提需求 → 一句话描述目标

Step 2: 方案设计
  Architect 或 OpenClaw 写技术方案 → designs/xxx.md

Step 3: 方案审批
  陈总点头 → 进入开发

Step 4: 任务拆派
  Hermes 拆解任务 → 分派给 OpenClaw 或子代理
  原则：一个人最多同时负责 2 个模块

Step 5: 开发执行
  子代理或 Hermes 直接编码
  必须遵循 TDD：先写测试 → 再写代码

Step 6: 代码审查
  Reviewer（独立于开发者）审查代码
  OpenClaw 做最终质量把关

Step 7: 归档汇报
  代码合入 → 更新文档 → 汇报陈总
```

## 二、角色分工红线

| 规则 | 说明 |
|------|------|
| 一人不兼多职 | 开发者和审查者必须是不同角色 |
| 方案先行 | 没方案不动工 |
| 测试先行 | 先写测试再写代码（TDD） |
| 审查必过 | 所有代码必须经过独立审查 |
| 文档同步 | 代码变更必须同步更新文档 |

## 三、模块负责人

| 模块 | 主负责 | 备份 |
|------|--------|------|
| 后端 API | Hermes | OpenClaw |
| 固件 | OpenClaw(VPS编译) | Hermes |
| 小程序 | Hermes(子代理) | — |
| iOS App | Hermes(子代理) | — |
| Android App | Hermes(子代理) | — |
| 3D外壳 | Hermes(子代理) | — |
| 硬件PCB | Hermes(子代理) | — |
| QA测试 | Hermes(子代理) | — |
| 代码审查 | OpenClaw | Hermes(子代理) |
| 文档管理 | Hermes | — |
| 汇报 | Hermes(cron自动) | — |

## 四、分支策略

```
main          ← 生产就绪代码
  └── develop ← 集成测试通过
        ├── feature/xxx  ← 新功能
        ├── fix/xxx      ← Bug修复
        └── release/xxx  ← 发布准备
```

## 五、Git 提交规范

```
<type>: <简短描述>

feat: 添加SOS蜂鸣器驱动
fix: 修复围栏字段名不匹配
docs: 更新团队架构文档
test: 添加设备绑定单元测试
review: 审查后端推送模块
```

## 六、密钥管理（红线）

- 所有密钥使用 `{{PLACEHOLDER}}` 占位
- 真实密钥存储在 `~/.hermes/secrets/` 下
- 密钥永不进入 Git 仓库
- .env 文件在 .gitignore 中
- 陈总的 AppSecret 永不在对话中透露

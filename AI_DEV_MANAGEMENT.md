# AI 原生开发管理方案 — KeepSafe 防丢器项目

> 你 = 老板 | 我（Hermes Agent）= 项目经理 | 子 Agent = 开发团队

---

## 一、核心理念

```
你（提需求 → 看结果）
  │
  ▼
我（PM）：写方案 → 派 Agent → 跟进度 → 验证 → 归档
  │
  ├── 🏗 Architect     → 技术方案设计
  ├── 💻 Backend-Dev   → 后端 API + 数据库
  ├── 📱 iOS-Dev       → Swift App
  ├── 🤖 Android-Dev   → Kotlin App
  ├── 🔧 Emb-Dev       → 定位器固件
  ├── 🧪 QA            → 功能 + 回归 + 压力测试
  ├── 👁 Reviewer      → 独立代码审查
  └── 📚 Librarian     → 知识库维护
```

**三条铁律：**
1. **我不直接写代码** — 所有开发通过 `delegate_task` 派给子 Agent
2. **代码必须被验证** — Reviewer Agent 独立审查，和开发 Agent 不同人
3. **方案先行** — 没方案不动工，方案你点头了再开发

---

## 二、工作流程（7 步）

```
Step 1: 你提需求（一句话）
    │
Step 2: 我写开发方案 → designs/
    │
Step 3: 你审批方案（你说 OK）
    │
Step 4: 我派 Agent 开发（并行/串行）
    │
Step 5: QA Agent 测试
    │
Step 6: Reviewer Agent 审查代码
    │
Step 7: 归档 + 给你最终结果
```

---

## 三、交付格式

```
─────────────────────────────────
  任务：{任务名}
  状态：✅ 已完成 / ❌ 失败
  产出：
    ├── code/backend/xxx.py
    ├── code/firmware/xxx.c
    └── code/ios/xxx.swift
  ⏱ 用时：Xh
  Review：✅ 通过（X issues fixed）
  归档：knowledge/designs/KF-xxx.md
─────────────────────────────────
```

---

## 四、项目资料库结构

```
~/projects/keepsafe/
├── designs/           ← 所有开发方案
├── code/              ← 源代码（Agent 产出）
│   ├── backend/
│   ├── firmware/
│   ├── ios/
│   └── android/
├── tests/             ← 测试报告
├── reviews/           ← Review 记录
├── knowledge/         ← 知识库
│   ├── ARCHITECTURE.md
│   ├── DECISIONS.md
│   ├── GLOSSARY.md
│   └── sdlc/          ← 管理制度
│       ├── DEVELOPMENT_PROCESS.md
│       ├── CODING_STANDARDS.md
│       ├── REVIEW_CHECKLIST.md
│       └── SECURITY_POLICY.md
└── templates/         ← 模板
    ├── dev_plan_template.md
    └── review_report.md
```

---

## 五、密钥管理

所有密钥/Token/Password 必须由你亲手填入，Agent 只能使用 `{{PLACEHOLDER}}`。
详见 `knowledge/sdlc/SECURITY_POLICY.md`

---

## 六、下一步

**请提供防丢器外观结构图**，我将基于它编写第一个开发方案。

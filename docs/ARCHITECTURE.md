# KeepSafe 项目架构文档

> 版本: 3.0 | 日期: 2026-05-27 | 负责人: Hermes

---

## 一、项目概述

| 项目 | KeepSafe — 老人小孩防丢定位器 |
|------|------------------------------|
| 定位 | 迷你定位器 + 监护人App + 微信小程序 |
| 硬件 | ESP32-S3 + 展锐8910 + GPS/北斗双模 |
| 尺寸 | 38×28×8mm / 15g / 续航30天 |
| 零售价 | ¥199（硬件）+ ¥9.9/月（服务） |
| 仓库 | `~/projects/keepsafe/` |

## 二、技术栈

```
┌─────────────────────────────────────────────────────┐
│                    用户端                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐      │
│  │ iOS App  │  │Android   │  │ 微信小程序     │      │
│  │ Swift    │  │ Kotlin   │  │ JavaScript    │      │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘      │
│       │             │               │               │
│       └─────────────┼───────────────┘               │
│                     │ REST API                      │
├─────────────────────┼───────────────────────────────┤
│                     ▼             后端服务           │
│  ┌──────────────────────────────────────────────┐   │
│  │  FastAPI (Python 3.11)                        │   │
│  │  SQLite(dev) / PostgreSQL(prod)               │   │
│  │  fakeredis(dev) / Redis(prod)                 │   │
│  │  EMQX MQTT 消息中间件                          │   │
│  │  FCM + APNs 推送                               │   │
│  └──────────────────────┬───────────────────────┘   │
│                         │ MQTT                      │
├─────────────────────────┼───────────────────────────┤
│                         ▼          硬件层            │
│  ┌──────────────────────────────────────────────┐   │
│  │  ESP32-S3 + 展锐8910 (4G Cat.1 + BLE + GPS)   │   │
│  │  SOS蜂鸣器 · LED · 振动马达 · 加速度计       │   │
│  │  300mAh电池 · USB-C充电 · IP65防水            │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## 三、项目目录结构

```
~/projects/keepsafe/
├── code/
│   ├── backend/          # FastAPI 后端 (27个.py文件, 95%完成)
│   │   ├── app/
│   │   │   ├── api/      # 路由: auth, devices, users, fences, alerts
│   │   │   ├── models/   # ORM 模型
│   │   │   ├── push/     # FCM + APNs 推送
│   │   │   ├── config.py # 配置(dev_mode=True用SQLite)
│   │   │   └── chat_agent.py # 手机聊天服务
│   │   └── .venv/        # Python 虚拟环境
│   ├── firmware/         # ESP32 固件 (16个.c/.h文件)
│   │   └── main/         # main, gps, mqtt, power, sos, accel, lbs, led
│   ├── ios/KeepSafe/     # iOS App (14个.swift文件)
│   ├── android/          # Android App (13个.kt文件)
│   ├── miniapp/          # 微信小程序 (5页面+2组件)
│   │   ├── pages/        # login, index, alerts, sos-detail, profile
│   │   ├── components/   # device-card, fence-picker
│   │   └── utils/        # api.js, auth.js, map.js
│   └── hardware/         # 3D外壳 (Blender + OpenSCAD)
├── docs/                 # 架构与流程文档
├── specs/                # 技术规格书
├── designs/              # 开发方案
├── reviews/              # 代码审查记录
├── tests/                # 测试报告
├── requirements/         # 需求文档
├── team/                 # 团队任命记录
├── knowledge/            # 知识库(SDL规范/安全策略)
├── shared-memory/        # 共享决策记录
├── meetings/             # 会议纪要
└── templates/            # 文档模板
```

## 四、关键配置

| 配置项 | 值 | 位置 |
|--------|-----|------|
| 后端端口 | 8000 | app/config.py |
| 开发模式 | SQLite (dev_mode=True) | app/config.py |
| 小程序 AppID | wxebce4c590760c9e3 | miniapp/project.config.json |
| VPS IP | 43.163.5.90 | SSH root@43.163.5.90 |
| VPS SSH Key | ~/.ssh/keepsafe-v2 | 本地 |
| 测试账号 | test@keepsafe.com / test123456 | 数据库 |

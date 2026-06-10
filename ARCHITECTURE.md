# KeepSafe 防丢器 - 项目架构

> 最后更新: 2026-06-09

## 技术栈

- 后端: Python FastAPI + PostgreSQL + Redis
- 消息: EMQX MQTT Broker
- 固件: ESP32-S3 (ESP-IDF C) → EC618 Air780EG (LuatOS)
- 前端: 微信小程序 (5 页面)
- 部署: Docker Compose (4 容器)
- VPS: 43.163.5.90:8000

## 目录结构

```
code/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI + 离线检测后台任务
│   │   ├── mqtt_client.py   # MQTT 客户端 (topic路由+字段归一化)
│   │   ├── db.py            # 数据模型
│   │   └── api/
│   │       ├── auth.py, devices.py, fences.py, alerts.py...
│   └── tests/test_api.py    # 45 测试
├── firmware/                # ESP32-S3 固件 (16 文件)
│   └── main/                # C 源码
├── firmware-ec618/          # EC618 新固件框架
│   ├── luatos/              # LuatOS 方案
│   │   ├── main.lua         # 主循环+网络监控+看门狗
│   │   ├── mqtt.lua         # MQTT 客户端 (指数退避+熔断)
│   │   ├── gps.lua          # GPS AT+CGNSINF 解析
│   │   └── config.lua       # 配置
│   ├── at-scripts/
│   │   └── mqtt_at.py       # AT 指令 MQTT (328行,支持--mock)
│   └── shared/              # 可复用模块文档
├── miniapp/                 # 微信小程序 (5 页面)
├── scripts/test_at.py       # AT 指令测试
└── docs/                    # 文档
    ├── FIRMWARE-MIGRATION.md
    └── BOARD-CHECKLIST.md
```

## Docker 容器

| 容器 | 端口 | 状态 |
|------|------|------|
| keepsafe-app | 8000 | healthy |
| keepsafe-emqx | 1883, 18083 | healthy |
| keepsafe-postgres | 5432 | healthy |
| keepsafe-redis | 6379 | healthy |

## 硬件

| 组件 | 型号 | 状态 |
|------|------|------|
| 主力固件 | ESP32-S3 | 运行中 |
| 新方案 | Air780EG EC618 | AT通信OK, SIM待激活 |
| SIM | 电信 ctnet | 待激活 |

## 核心约定

- 测试: test@keepsafe.com / test123456
- 固件烧录: USB-OTG 口 /dev/cu.usbmodem*
- 3D 建模: 暂停，交豆包
- 定位: lat/lng

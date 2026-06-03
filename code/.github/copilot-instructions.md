## Tech Stack
- 前端: 微信小程序 (5页) + iOS + Android
- 后端: Python FastAPI + PostgreSQL + Redis + EMQX MQTT
- 固件: ESP32-S3, C/C++ (ESP-IDF)
- 部署: Docker (keepsafe-app:8000, keepsafe-emqx:1883, keepsafe-postgres, keepsafe-redis)
- 推送: FCM + APNs
- VPS: Tencent Cloud 43.163.5.90, 新加坡一区
- 3D模型: ~/Desktop/keepsafe/3d-model/pbr/mesh_textured_pbr.obj (陈总唯一指定)
- 外观设计: 豆包(Doubao)处理, 非 AI 强项
## Rules
- 后端端口: 8000

- 数据库: PostgreSQL (Docker volume 自动持久化)

- SIM 卡电信 APN: ctnet

- 固件烧录: USB-OTG 口 (/dev/cu.usbmodem101), 非 UART 口

- esptool 写 flash --flash_size 16MB

- 后端字段: lat / lng / enabled (非 latitude / longitude / enable)

- 测试账号: test@keepsafe.com / test123456

- seed_mock.py 可插入模拟数据

- 代码: ~/projects/keepsafe/code/ (后端95%/小程序完整/iOS14文件/Android13文件/固件16文件)

- 文档: ~/projects/tracker/ (PRD + v1-v3)

- 尺寸: 38×28×10mm, 飞碟菱形椭圆造型

- 3D 渲染: 亮色材质 + 多光源, 暗色看不清

- 安全巡检: 每3h / 健康巡检: 每4h

- 团队手册: TEAM_HANDBOOK.md

## Style
- 简洁 commit

- 测试覆盖 ≥ 基线 (当前 27 tests)

- 所有 API 必须有鉴权

- 密码/密钥不写入源代码

- .env 不提交 Git

- 汇报: bullet points, 只用结果

## Instructions
- Always follow workspace rules.
- Keep responses concise.

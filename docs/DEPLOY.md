# KeepSafe — 部署手册

> 版本: v2.0
> 更新: 2026-06-11
> VPS: Tencent Cloud 43.163.5.90, 新加坡一区

---

## 一、系统架构

```
                   ┌─────────────┐
                   │ 微信小程序   │ (wxebce4c590760c9e3)
                   └──────┬──────┘
                          │ HTTPS
                   ┌──────▼──────┐
                   │  Nginx:443  │ → 反向代理
                   └──────┬──────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                  │
  ┌─────▼─────┐   ┌───────▼──────┐   ┌──────▼──────┐
  │keepsafe-app│   │keepsafe-emqx │   │keepsafe-    │
  │  :8000     │   │  :1883       │   │postgres     │
  │  FastAPI   │◄──┤  MQTT Broker │   │  :5432      │
  └─────┬─────┘   └──────▲──────┘   └─────────────┘
        │                │
  ┌─────▼─────┐   ┌──────┴──────┐
  │keepsafe-  │   │  ESP32-S3   │
  │redis:6379 │   │  EC618 4G   │
  └───────────┘   │  (设备端)    │
                  └─────────────┘
```

---

## 二、环境要求

| 组件 | 版本 | 用途 |
|------|------|------|
| Docker | 24.0+ | 容器编排 |
| Docker Compose | v2.20+ | 多容器管理 |
| Python | 3.11+ | 后端开发 |
| Node.js | 18+ | 微信小程序后端 |
| ESP-IDF | v5.4 | 固件编译 |
| Nginx | 1.24+ | 反向代理 + SSL |

---

## 三、VPS 部署

### 3.1 目录结构

```
~/keepsafe/
├── docker-compose.yml      # 容器编排
├── code/
│   └── backend/            # Python FastAPI
│       ├── .env.production # 生产环境变量
│       ├── Dockerfile
│       └── ...
├── nginx/
│   └── keepsafe.conf       # Nginx 配置
└── data/
    ├── postgres/           # PostgreSQL 数据卷
    └── redis/              # Redis 持久化
```

### 3.2 环境变量 (.env.production)

```bash
# ── 核心配置 ──
JWT_SECRET=your-256-bit-secret-key-here
JWT_EXPIRE_MINUTES=1440
DEV_MODE=false

# ── 数据库 ──
DATABASE_URL=postgresql+asyncpg://keepsafe:secure_password@keepsafe-postgres:5432/keepsafe
POSTGRES_USER=keepsafe
POSTGRES_PASSWORD=secure_password_here

# ── Redis ──
REDIS_URL=redis://keepsafe-redis:6379/0

# ── MQTT/EMQX ──
MQTT_BROKER_HOST=keepsafe-emqx
MQTT_BROKER_PORT=1883

# ── 推送通知 (可选, 不配置则推送静默失败) ──
FCM_CREDENTIALS_PATH=/app/firebase-credentials.json
APNS_KEY_PATH=/app/apns-key.p8
APNS_KEY_ID=ABC123DEFG
APNS_TEAM_ID=TEAM123456
APNS_TOPIC=com.keepsafe.app

# ── 微信小程序 ──
WECHAT_APPID=wxebce4c590760c9e3
WECHAT_SECRET=your-wechat-app-secret-here
```

### 3.3 Docker Compose 启动

```bash
cd ~/keepsafe/code

# 首次启动 (构建镜像)
docker compose up -d --build

# 日常启动/重启
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f backend
docker compose logs -f emqx

# 停止
docker compose down

# 完全清除 (含数据卷!)
docker compose down -v
```

### 3.4 Nginx 反向代理配置

```nginx
# /etc/nginx/sites-available/keepsafe
server {
    listen 80;
    server_name 43.163.5.90;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name 43.163.5.90;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # API 后端
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # Swagger 文档
    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

### 3.5 数据库管理

```bash
# 进入 PostgreSQL 容器
docker compose exec postgres psql -U keepsafe -d keepsafe

# 备份数据库
docker compose exec postgres pg_dump -U keepsafe keepsafe > backup-$(date +%Y%m%d).sql

# 恢复数据库
cat backup.sql | docker compose exec -T postgres psql -U keepsafe -d keepsafe

# 迁移 (Alembic)
docker compose exec backend alembic upgrade head
```

### 3.6 健康巡检

```bash
# 检查后端
curl http://localhost:8000/health
# → {"status":"ok","service":"keepsafe-backend","version":"1.1.0","mqtt_connected":true}

# 检查 EMQX
curl http://localhost:18083/api/v5/status
# (默认管理面板: http://43.163.5.90:18083, admin/public)

# 检查 Redis
docker compose exec redis redis-cli ping
# → PONG

# 检查 PostgreSQL
docker compose exec postgres pg_isready -U keepsafe
# → accepting connections
```

---

## 四、本地开发

### 4.1 后端

```bash
cd ~/projects/keepsafe/code/backend

# 创建虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 开发模式启动 (DEV_MODE=true, SQLite)
DEV_MODE=true uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 运行测试
pytest tests/test_api.py -v
# 当前: 133 tests
```

### 4.2 小程序

```bash
# 使用微信开发者工具打开
cd ~/projects/keepsafe/src/miniapp
# 项目配置: project.config.json
# AppID: wxebce4c590760c9e3
# API Base URL (开发): http://localhost:8000/api/v1
# API Base URL (生产): https://43.163.5.90/api/v1
```

### 4.3 固件

```bash
cd ~/projects/keepsafe/code/firmware
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/cu.usbmodem101 flash
```

---

## 五、固件烧录

### 硬件连接

- ESP32-S3: 使用 USB-OTG 口 (/dev/cu.usbmodem101), 非 UART 口
- Air780E 开发板: Type-C 口 (板载 CH340/CH343 串口芯片)

### 编译

```bash
# VPS 上编译 (Docker 内)
docker run --rm -v ~/projects/keepsafe/code/firmware:/project \
  espressif/idf:v5.4 \
  bash -c "idf.py set-target esp32s3 && idf.py build"
```

### 烧录

```bash
# 擦除
esptool.py --chip esp32s3 --port /dev/cu.usbmodem101 erase_flash

# 烧录 (4个分区)
esptool.py --chip esp32s3 --port /dev/cu.usbmodem101 --baud 921600 \
  --before default_reset --after hard_reset write_flash \
  --flash_mode dio --flash_size 16MB --flash_freq 80m \
  0x0 build/bootloader/bootloader.bin \
  0x8000 build/partition_table/partition-table.bin \
  0x10000 build/keepsafe.bin
```

### 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| Failed to connect | 串口错误 | 确认用 USB-OTG 口, 检查设备路径 |
| Invalid head of packet | 波特率不匹配 | 降速至 115200 |
| Flash size mismatch | Flash 大小错误 | 加 --flash_size 16MB |
| 设备未进入下载模式 | GPIO0 未拉低 | 按住 BOOT → RST → 松开 BOOT |

---

## 六、容器清单

| 容器 | 端口 | 说明 |
|------|------|------|
| keepsafe-app | 8000 | FastAPI 后端 |
| keepsafe-emqx | 1883, 8083(WS), 18083(Mgmt) | MQTT Broker |
| keepsafe-postgres | 5432 | 数据库 (volume: keepsafe_pgdata) |
| keepsafe-redis | 6379 | 缓存 (volume: keepsafe_redisdata) |

---

## 七、测试清单

| 测试类别 | 用例数 | 命令 |
|----------|--------|------|
| 后端 API | 133 | `pytest tests/test_api.py -v` |
| 固件 AT 指令 | 10+ | `python3 scripts/test_at.py --full` |
| MQTT 端到端 | 5 | `docker compose logs -f backend \| grep -i mqtt` |
| 硬件功能 | 8 | 串口 + 万用表 (见 docs/TEST.md) |

---

## 八、故障排查

### 后端启动失败
```bash
# 查看日志
docker compose logs backend --tail 50

# 检查端口占用
lsof -i :8000

# 重启容器
docker compose restart backend
```

### MQTT 无法连接
```bash
# 检查 EMQX 状态
docker compose logs emqx --tail 20

# 测试 MQTT 连接
mosquitto_pub -h localhost -p 1883 -t "keepsafe/v1/test/status" -m '{"status":"ok"}'

# 检查设备认证回调
curl -X POST http://localhost:8000/api/v1/auth/device \
  -H "Content-Type: application/json" \
  -d '{"device_id":"KS-00000001","token":"tok-001"}'
```

### 数据库连接失败
```bash
# 检查 PostgreSQL 容器
docker compose ps postgres
docker compose logs postgres --tail 10

# 手动连接测试
docker compose exec postgres psql -U keepsafe -c "SELECT 1"
```

---

## 九、备份策略

```bash
# 每日自动备份 (crontab)
0 3 * * * ~/keepsafe/scripts/backup.sh

# backup.sh 内容:
# docker compose exec postgres pg_dump -U keepsafe keepsafe > ~/backups/keepsafe-$(date +\%Y\%m\%d).sql
# find ~/backups -name "*.sql" -mtime +7 -delete  # 保留 7 天
```

---

## 十、BOM 成本

| 物料 | 单价 | 数量 |
|------|------|------|
| EC618 主控 | ¥28 | 1 |
| PCB | ¥6 | 1 |
| SMT 贴片 | ¥8 | 1 |
| 外壳 | ¥5 | 1 |
| 电池 | ¥8 | 1 |
| 天线 | ¥3 | 2 |
| **单板总成本** | **¥44** | |
| **成品总成本** | **¥61** | |

---

## 十一、API 文档

- Swagger UI: http://43.163.5.90:8000/docs
- API 详细文档: docs/API.md
- 测试指南: docs/TEST.md
- 架构文档: docs/ARCHITECTURE.md

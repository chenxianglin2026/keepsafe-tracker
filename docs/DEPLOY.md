# KeepSafe Backend VPS Docker Deployment Guide

## Overview

Deploy the KeepSafe backend stack to a TencentOS VPS (43.163.5.90) using Docker Compose.

**Stack:**
- FastAPI backend (app)
- TimescaleDB (PostgreSQL 15 + time-series extension)
- Redis 7
- EMQX 5 (MQTT broker)

## Prerequisites

### On VPS (43.163.5.90)
- Docker 26.1.3+ installed (confirmed)
- Docker Compose plugin: `docker compose` (not legacy `docker-compose`)
- If missing: `yum install -y docker-compose-plugin`

### On Local Machine
- SSH key-based access to VPS configured:
  ```
  ssh-copy-id root@43.163.5.90
  ```
- rsync installed (macOS has it by default)

## Quick Deploy

### 1. Prepare secrets

```bash
cd ~/projects/keepsafe/code/backend
cp .env.production .env
vim .env
```

Replace all `CHANGEME` values with real secrets:

| Variable | Description | How to Generate |
|----------|-------------|-----------------|
| JWT_SECRET | JWT signing key | `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| POSTGRES_PASSWORD | TimescaleDB superuser password | `python3 -c "import secrets; print(secrets.token_urlsafe(24))"` |
| DB_PASSWORD | App DB password (same as POSTGRES_PASSWORD) | Same value |
| REDIS_PASSWORD | Redis password | `python3 -c "import secrets; print(secrets.token_urlsafe(24))"` |
| EMQX_DASHBOARD_PASSWORD | EMQX web dashboard password | Choose a strong password |
| APNS_KEY_ID | Apple Push Notification key ID | From Apple Developer Portal |
| APNS_TEAM_ID | Apple Developer Team ID | From Apple Developer Portal |
| OPENCELLID_API_KEY | OpenCellID API key | https://opencellid.org |

### 2. Place credential files

```bash
mkdir -p credentials
# Copy your Firebase service account JSON
cp /path/to/firebase-service-account.json credentials/
# Copy your APNs auth key
cp /path/to/apns-key.p8 credentials/
```

Verify:
```bash
ls -la credentials/
# Should show:
#   firebase-service-account.json
#   apns-key.p8
```

### 3. Deploy

```bash
./deploy.sh
```

This will:
1. Verify SSH access to VPS
2. Check .env for placeholder values
3. Rsync code to /opt/keepsafe on VPS
4. Build Docker image on VPS
5. Start all services via docker compose
6. Wait for health checks
7. Smoke test the API

### 4. Verify

```bash
# Check API health
curl http://43.163.5.90:8000/health

# Check EMQX dashboard
open http://43.163.5.90:18083
# Login: admin / (your EMQX_DASHBOARD_PASSWORD)
```

## Manual Deployment (without deploy.sh)

### Step 1: Copy code to VPS

```bash
rsync -avz --delete \
    --exclude='.venv/' --exclude='__pycache__/' \
    --exclude='.git/' --exclude='*.db' \
    ~/projects/keepsafe/code/backend/ \
    root@43.163.5.90:/opt/keepsafe/
```

### Step 2: SSH into VPS and start

```bash
ssh root@43.163.5.90
cd /opt/keepsafe

# Build and start
docker compose pull postgres redis emqx
docker compose build app
docker compose up -d

# Check status
docker compose ps
docker compose logs -f app
```

## Service Ports

| Service | Port | Notes |
|---------|------|-------|
| FastAPI | 8000 | REST API + health check at /health |
| EMQX Dashboard | 18083 | Web UI |
| EMQX MQTT | 1883 | MQTT TCP (devices connect here) |
| PostgreSQL | 5432 | TimescaleDB |
| Redis | 6379 | Cache / pub-sub |

## Common Operations

### View logs

```bash
# All services
ssh root@43.163.5.90 'cd /opt/keepsafe && docker compose logs -f'

# App only
ssh root@43.163.5.90 'cd /opt/keepsafe && docker compose logs -f app'

# Last 100 lines
ssh root@43.163.5.90 'cd /opt/keepsafe && docker compose logs --tail=100 app'
```

### Restart a service

```bash
ssh root@43.163.5.90 'cd /opt/keepsafe && docker compose restart app'
```

### Update application

```bash
# Local: sync code
rsync -avz --delete \
    --exclude='.venv/' --exclude='__pycache__/' --exclude='.git/' \
    ~/projects/keepsafe/code/backend/ \
    root@43.163.5.90:/opt/keepsafe/

# VPS: rebuild and restart
ssh root@43.163.5.90 'cd /opt/keepsafe && docker compose up -d --build app'
```

### Stop all services

```bash
ssh root@43.163.5.90 'cd /opt/keepsafe && docker compose down'
```

### Full cleanup (remove volumes/data)

```bash
ssh root@43.163.5.90 'cd /opt/keepsafe && docker compose down -v'
```

## Monitoring

### Check container health

```bash
ssh root@43.163.5.90 'cd /opt/keepsafe && docker compose ps'
```

Expected output: all services show `healthy` or `running`.

### API health endpoint

```bash
curl http://43.163.5.90:8000/health
```

Expected response:
```json
{"status":"ok","service":"keepsafe-backend","version":"1.1.0","mqtt_connected":true}
```

### Resource usage

```bash
ssh root@43.163.5.90 'docker stats --no-stream'
```

## Firewall

The VPS firewall must allow these incoming ports:

```bash
# On VPS (TencentOS uses firewalld or iptables)
firewall-cmd --permanent --add-port=8000/tcp   # API
firewall-cmd --permanent --add-port=1883/tcp   # MQTT
firewall-cmd --permanent --add-port=18083/tcp  # EMQX Dashboard
firewall-cmd --reload
```

**Security note:** In production, restrict port 18083 (EMQX Dashboard) to your IP only. Consider using a VPN or SSH tunnel instead of exposing it publicly.

## Troubleshooting

### App won't start: "connection refused" to postgres

Wait for TimescaleDB to initialize. The first boot takes longer because of the TimescaleDB extension setup (hypertable creation in init.sql).

```bash
ssh root@43.163.5.90 'cd /opt/keepsafe && docker compose logs postgres'
```

### EMQX authentication not working

EMQX needs the app to be running to authenticate devices via HTTP. Check app logs:

```bash
ssh root@43.163.5.90 'cd /opt/keepsafe && docker compose logs app | grep auth'
```

### Build fails: missing requirements.txt

Make sure you're running from the backend project root where Dockerfile and requirements.txt exist.

### Permission denied on credentials/

The credentials directory is mounted read-only into the container. Make sure the files exist on the VPS at `/opt/keepsafe/credentials/`.

### TimescaleDB extension not found

The `timescale/timescaledb:2.17.2-pg15` image includes TimescaleDB pre-installed. If you changed the image, make sure it includes the TimescaleDB extension.

## Architecture Diagram

```
Internet
   |
   v
[VPS 43.163.5.90]
   |
   +-- :1883 --> EMQX (MQTT Broker) <-- devices connect here
   |                |
   |                +-- HTTP auth --> FastAPI (device auth, ACL)
   |
   +-- :8000 --> FastAPI (REST API)
   |                |
   |                +-- PostgreSQL (TimescaleDB)
   |                +-- Redis (cache, pub-sub)
   |                +-- FCM/APNs (push notifications)
   |
   +-- :18083 --> EMQX Dashboard (admin UI)
```

## Backup

### Database backup

```bash
ssh root@43.163.5.90 'docker exec keepsafe-postgres \
    pg_dump -U keepsafe keepsafe' > keepsafe_backup_$(date +%Y%m%d).sql
```

### Restore

```bash
cat keepsafe_backup_YYYYMMDD.sql | \
    ssh root@43.163.5.90 'docker exec -i keepsafe-postgres \
    psql -U keepsafe keepsafe'
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| APP_HOST | No | 0.0.0.0 | Bind address |
| APP_PORT | No | 8000 | Listen port |
| LOG_LEVEL | No | info | Logging level (debug/info/warning/error) |
| DEV_MODE | **Yes** | true | MUST be false for production |
| APP_VERSION | No | latest | Docker image tag |
| JWT_SECRET | **Yes** | - | JWT signing secret |
| POSTGRES_DB | No | keepsafe | Database name |
| POSTGRES_USER | No | keepsafe | Database user |
| POSTGRES_PASSWORD | **Yes** | - | Database password |
| DB_HOST | No | postgres | DB host (container name) |
| DB_PORT | No | 5432 | DB port |
| DB_NAME | No | keepsafe | DB name for app |
| DB_USER | No | keepsafe | DB user for app |
| DB_PASSWORD | **Yes** | - | DB password for app |
| REDIS_HOST | No | redis | Redis host |
| REDIS_PORT | No | 6379 | Redis port |
| REDIS_PASSWORD | **Yes** | - | Redis password |
| EMQX_HOST | No | emqx | EMQX host |
| EMQX_PORT | No | 1883 | MQTT port |
| EMQX_DASHBOARD_PASSWORD | **Yes** | - | EMQX admin password |
| FCM_CREDENTIALS_PATH | No | /app/credentials/... | Path to Firebase JSON |
| APNS_KEY_PATH | No | /app/credentials/... | Path to APNs .p8 key |
| APNS_KEY_ID | If using APNs | - | Apple key ID |
| APNS_TEAM_ID | If using APNs | - | Apple team ID |
| APNS_TOPIC | No | com.keepsafe.app | APNs bundle ID |
| OPENCELLID_API_KEY | If using LBS | - | OpenCellID API key |

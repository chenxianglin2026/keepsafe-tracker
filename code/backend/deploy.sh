#!/usr/bin/env bash
# ============================================================
# KeepSafe Backend - VPS Deployment Script
# ============================================================
# Deploys the backend to 43.163.5.90 using Docker Compose.
#
# Prerequisites:
#   1. SSH key access to VPS already configured
#   2. VPS has Docker 26.1.3+ and docker-compose plugin installed
#   3. .env file populated with real secrets (from .env.production)
#   4. credentials/ directory with FCM JSON and APNs key
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
# ============================================================
set -euo pipefail

# ──────────────────────────────────────────────
# Configuration - modify as needed
# ──────────────────────────────────────────────
VPS_HOST="43.163.5.90"
VPS_USER="root"
VPS_PATH="/opt/keepsafe"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ──────────────────────────────────────────────
# Colors
# ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ──────────────────────────────────────────────
# Pre-flight checks
# ──────────────────────────────────────────────

log_info "=== KeepSafe Backend Deployment ==="
log_info "VPS: ${VPS_USER}@${VPS_HOST}"
log_info "Project: ${PROJECT_DIR}"
echo ""

# Check .env exists
if [ ! -f "${PROJECT_DIR}/.env" ]; then
    log_error ".env file not found!"
    log_error "Copy .env.production to .env and fill in real secrets:"
    log_error "  cp .env.production .env"
    log_error "  vim .env  # replace all CHANGEME values"
    exit 1
fi

# Warn about default placeholders
if grep -q "CHANGEME" "${PROJECT_DIR}/.env" 2>/dev/null; then
    log_warn ".env still contains CHANGEME placeholders!"
    log_warn "Please replace ALL CHANGEME values with real secrets before deploying."
    echo ""
    read -rp "Continue anyway? [y/N] " answer
    if [ "${answer,,}" != "y" ]; then
        exit 1
    fi
fi

# Check credentials directory
if [ ! -d "${PROJECT_DIR}/credentials" ]; then
    log_warn "credentials/ directory not found. Creating empty one..."
    mkdir -p "${PROJECT_DIR}/credentials"
fi

# Check SSH connectivity
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${VPS_USER}@${VPS_HOST}" "echo ok" &>/dev/null; then
    log_error "Cannot SSH to ${VPS_USER}@${VPS_HOST}"
    log_error "Make sure SSH key is configured: ssh-copy-id ${VPS_USER}@${VPS_HOST}"
    exit 1
fi
log_ok "SSH connection to VPS verified"

# ──────────────────────────────────────────────
# Step 1: Prepare VPS directory
# ──────────────────────────────────────────────

log_info "Step 1: Preparing VPS directory ${VPS_PATH}..."

ssh "${VPS_USER}@${VPS_HOST}" << 'ENDSSH'
    mkdir -p /opt/keepsafe/credentials
    echo "Directory created"
ENDSSH

log_ok "VPS directory ready"

# ──────────────────────────────────────────────
# Step 2: Sync code to VPS (excluding large files)
# ──────────────────────────────────────────────

log_info "Step 2: Syncing code to VPS..."

rsync -avz --delete \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.git/' \
    --exclude='*.db' \
    --exclude='*.log' \
    --exclude='.DS_Store' \
    --exclude='.pytest_cache/' \
    "${PROJECT_DIR}/" \
    "${VPS_USER}@${VPS_HOST}:${VPS_PATH}/"

log_ok "Code synced to VPS"

# ──────────────────────────────────────────────
# Step 3: Build and start containers
# ──────────────────────────────────────────────

log_info "Step 3: Building and starting containers..."

ssh "${VPS_USER}@${VPS_HOST}" << ENDSSH
    cd ${VPS_PATH}

    # Ensure .env is readable
    chmod 600 .env 2>/dev/null || true

    # Pull base images first (faster, shows progress)
    echo ">>> Pulling base images..."
    docker compose pull postgres redis emqx 2>&1 || true

    # Build the app image
    echo ">>> Building app image..."
    docker compose build app

    # Start all services
    echo ">>> Starting services..."
    docker compose up -d

    echo ">>> Current status:"
    docker compose ps
ENDSSH

log_ok "Containers started"

# ──────────────────────────────────────────────
# Step 4: Wait for services to be healthy
# ──────────────────────────────────────────────

log_info "Step 4: Checking service health..."

MAX_WAIT=120
WAIT_INTERVAL=5
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check if all services are healthy
    HEALTHY_COUNT=$(ssh "${VPS_USER}@${VPS_HOST}" \
        "cd ${VPS_PATH} && docker compose ps --format json 2>/dev/null" \
        | python3 -c "
import sys, json
count = 0
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        s = json.loads(line)
        if s.get('Health') == 'healthy':
            count += 1
    except:
        pass
print(count)
" 2>/dev/null || echo "0")

    RUNNING_COUNT=$(ssh "${VPS_USER}@${VPS_HOST}" \
        "cd ${VPS_PATH} && docker compose ps --status running -q 2>/dev/null | wc -l" \
        | tr -d ' ')

    echo -ne "\rHealth check: ${HEALTHY_COUNT:-0} healthy / ${RUNNING_COUNT:-0} running (${ELAPSED}s/${MAX_WAIT}s)..."

    if [ "${HEALTHY_COUNT:-0}" -ge 4 ] && [ "${HEALTHY_COUNT:-0}" -eq "${RUNNING_COUNT:-0}" ]; then
        echo ""
        log_ok "All services healthy!"
        break
    fi

    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo ""
    log_warn "Timeout waiting for healthy state. Check logs:"
    log_warn "  ssh ${VPS_USER}@${VPS_HOST} 'cd ${VPS_PATH} && docker compose logs'"
fi

# ──────────────────────────────────────────────
# Step 5: Quick smoke test
# ──────────────────────────────────────────────

log_info "Step 5: Smoke testing API..."

HTTP_CODE=$(ssh "${VPS_USER}@${VPS_HOST}" \
    "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health 2>/dev/null" || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    HEALTH_BODY=$(ssh "${VPS_USER}@${VPS_HOST}" \
        "curl -s http://localhost:8000/health 2>/dev/null")
    log_ok "API health check passed: HTTP ${HTTP_CODE}"
    echo "    ${HEALTH_BODY}"
else
    log_error "API health check failed: HTTP ${HTTP_CODE}"
fi

# ──────────────────────────────────────────────
# Done
# ──────────────────────────────────────────────

echo ""
log_info "=== Deployment Complete ==="
echo ""
echo "  Services:"
echo "    API:       http://${VPS_HOST}:8000"
echo "    EMQX Dashboard: http://${VPS_HOST}:18083"
echo ""
echo "  Useful commands:"
echo "    ssh ${VPS_USER}@${VPS_HOST} 'cd ${VPS_PATH} && docker compose ps'"
echo "    ssh ${VPS_USER}@${VPS_HOST} 'cd ${VPS_PATH} && docker compose logs -f app'"
echo "    ssh ${VPS_USER}@${VPS_HOST} 'cd ${VPS_PATH} && docker compose restart app'"
echo ""

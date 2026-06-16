#!/usr/bin/env bash
# 启动 Cloudflare Tunnel

set -euo pipefail

CFWEB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${CFWEB_DIR}/bin/cloudflared"
CONFIG="${CFWEB_DIR}/config.yml"
PID_FILE="${CFWEB_DIR}/tmp/tunnel.pid"
LOG_FILE="${CFWEB_DIR}/logs/tunnel.log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[1;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[CFWEB]${NC} $*"; }
info() { echo -e "${GREEN}[CFWEB]${NC} $*"; }
warn() { echo -e "${YELLOW}[CFWEB]${NC} $*"; }
err() { echo -e "${RED}[CFWEB]${NC} $*" && exit 1; }

[[ -f "${BIN}" ]] || err "未找到 cloudflared: ${BIN}"
[[ -f "${CONFIG}" ]] || err "未找到配置文件: ${CONFIG}"

# 检查已有进程
if [[ -f "${PID_FILE}" ]]; then
    local_pid="$(cat "${PID_FILE}")"
    if kill -0 "${local_pid}" 2>/dev/null; then
        info "Tunnel 已在运行 (PID: ${local_pid})"
        exit 0
    else
        warn "发现无效 PID 文件，清理后重新启动..."
        rm -f "${PID_FILE}"
    fi
fi

log "启动 Cloudflare Tunnel..."
mkdir -p "$(dirname "${LOG_FILE}")"

nohup "${BIN}" tunnel --config "${CONFIG}" run >> "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"

sleep 3

if kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    info "Tunnel 启动成功 (PID: $(cat "${PID_FILE}"))"
    info "日志: ${LOG_FILE}"
else
    err "Tunnel 启动失败，请查看日志: ${LOG_FILE}"
fi

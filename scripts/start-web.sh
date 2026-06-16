#!/usr/bin/env bash
# 启动 CFWEB Web 管理平台

set -euo pipefail

CFWEB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="${CFWEB_DIR}/config.json"
PID_FILE="${CFWEB_DIR}/tmp/web.pid"
LOG_FILE="${CFWEB_DIR}/logs/web.log"

log() { printf '\033[1;34m[CFWEB-Web]\033[0m %s\n' "$*"; }
info() { printf '\033[1;32m[CFWEB-Web]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[CFWEB-Web]\033[0m %s\n' "$*" && exit 1; }

# 读取 Web 端口
if [[ -f "${CONFIG_FILE}" ]]; then
    WEB_PORT="$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}')).get('web', {}).get('port', 50000))")"
else
    WEB_PORT=50000
fi

# 检查已有进程
if [[ -f "${PID_FILE}" ]]; then
    pid="$(cat "${PID_FILE}")"
    if kill -0 "${pid}" 2>/dev/null; then
        info "Web 服务已在运行 (PID: ${pid}, 端口: ${WEB_PORT})"
        exit 0
    else
        log "发现无效 PID 文件，清理后重新启动..."
        rm -f "${PID_FILE}"
    fi
fi

log "启动 Web 管理平台 (端口: ${WEB_PORT})..."
mkdir -p "$(dirname "${LOG_FILE}")"

nohup python3 "${CFWEB_DIR}/web/server.py" >> "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"

sleep 2

if kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    info "Web 管理平台启动成功 (PID: $(cat "${PID_FILE}"))"
    info "访问地址: http://<服务器IP>:${WEB_PORT}"
    info "默认账号: admin"
    info "默认密码: admin"
else
    err "Web 管理平台启动失败，请查看日志: ${LOG_FILE}"
fi

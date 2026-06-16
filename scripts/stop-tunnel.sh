#!/usr/bin/env bash
# 停止 Cloudflare Tunnel

set -euo pipefail

CFWEB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="${CFWEB_DIR}/tmp/tunnel.pid"

if [[ -f "${PID_FILE}" ]]; then
    pid="$(cat "${PID_FILE}")"
    if kill -0 "${pid}" 2>/dev/null; then
        kill "${pid}"
        echo "[CFWEB] Tunnel 已停止 (PID: ${pid})"
    else
        echo "[CFWEB] Tunnel 未运行"
    fi
    rm -f "${PID_FILE}"
else
    echo "[CFWEB] 未找到 PID 文件"
fi

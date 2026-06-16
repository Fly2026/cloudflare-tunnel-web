#!/usr/bin/env bash
# 停止 CFWEB Web 管理平台

set -euo pipefail

CFWEB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="${CFWEB_DIR}/tmp/web.pid"

if [[ -f "${PID_FILE}" ]]; then
    pid="$(cat "${PID_FILE}")"
    if kill -0 "${pid}" 2>/dev/null; then
        kill "${pid}"
        echo "[CFWEB-Web] Web 管理平台已停止 (PID: ${pid})"
    else
        echo "[CFWEB-Web] Web 管理平台未运行"
    fi
    rm -f "${PID_FILE}"
else
    echo "[CFWEB-Web] 未找到 PID 文件"
fi

#!/usr/bin/env bash
# 查看 CFWEB 运行状态

CFWEB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="${CFWEB_DIR}/tmp/tunnel.pid"
LOG_FILE="${CFWEB_DIR}/logs/tunnel.log"
CONFIG_FILE="${CFWEB_DIR}/config.json"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== CFWEB 状态 ==="
echo "安装目录: ${CFWEB_DIR}"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    echo -e "运行状态: ${GREEN}运行中${NC} (PID: $(cat "${PID_FILE}"))"
else
    echo -e "运行状态: ${RED}未运行${NC}"
fi

echo ""
echo "已配置服务:"
if [[ -f "${CONFIG_FILE}" ]] && command -v jq >/dev/null 2>&1; then
    while IFS= read -r svc; do
        folder="$(echo "${svc}" | jq -r '.folder')"
        host="$(echo "${svc}" | jq -r '.host // "localhost"')"
        port="$(echo "${svc}" | jq -r '.port')"
        domain="$(jq -r '.domain' "${CONFIG_FILE}")"
        echo "  ${folder}.${domain} -> http://${host}:${port}"
    done < <(jq -c '.services[]' "${CONFIG_FILE}")
else
    echo "  无法读取配置"
fi

echo ""
echo "最近日志:"
if [[ -f "${LOG_FILE}" ]]; then
    tail -n 20 "${LOG_FILE}"
else
    echo "无日志文件"
fi

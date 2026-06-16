#!/usr/bin/env bash
# CFWEB 一键安装入口
# 用法: ./install.sh
# 在其他机器解压 tar.gz 后执行此脚本完成部署

set -euo pipefail

CFWEB_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="${CFWEB_DIR}/config.json"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[CFWEB]${NC} $*"; }
info() { echo -e "${GREEN}[CFWEB]${NC} $*"; }
warn() { echo -e "${YELLOW}[CFWEB]${NC} $*"; }
err() { echo -e "${RED}[CFWEB]${NC} $*" && exit 1; }

need_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        err "缺少命令: $1，请先安装"
    fi
}

log "CFWEB 一键安装脚本"
log "项目目录: ${CFWEB_DIR}"

# 检查依赖
for cmd in curl python3 jq; do
    need_cmd "${cmd}"
done

# 检查配置文件
if [[ ! -f "${CONFIG_FILE}" ]]; then
    err "未找到配置文件: ${CONFIG_FILE}"
    err "请复制 config.json.example 为 config.json 并填写配置"
fi

# 检查配置文件是否还是示例
if grep -q 'LTAIxxxxxxxxxxxx\|example.com\|xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' "${CONFIG_FILE}" 2>/dev/null; then
    warn "配置文件看起来还是示例内容，请确保已填入真实值"
fi

# 设置敏感文件权限
chmod 600 "${CONFIG_FILE}" 2>/dev/null || true

# 执行核心安装
bash "${CFWEB_DIR}/scripts/setup.sh"

# 启动 Web 管理平台
if [[ "${START_WEB:-0}" == "1" ]]; then
    info "正在启动 Web 管理平台..."
    bash "${CFWEB_DIR}/scripts/start-web.sh"
fi

info "=========================================="
info "CFWEB 安装完成！"
info "=========================================="
if [[ "${START_WEB:-0}" == "1" ]]; then
    web_port="$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}')).get('web', {}).get('port', 50000))")"
    echo "Web 管理平台: http://<服务器IP>:${web_port}"
    echo "默认账号: admin"
    echo "默认密码: admin"
    echo ""
fi
echo "管理命令:"
echo "  启动 tunnel: ${CFWEB_DIR}/scripts/start-tunnel.sh"
echo "  停止 tunnel: ${CFWEB_DIR}/scripts/stop-tunnel.sh"
echo "  启动 Web:    ${CFWEB_DIR}/scripts/start-web.sh"
echo "  停止 Web:    ${CFWEB_DIR}/scripts/stop-web.sh"
echo "  查看状态:    ${CFWEB_DIR}/scripts/status.sh"

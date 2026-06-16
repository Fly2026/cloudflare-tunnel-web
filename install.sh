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

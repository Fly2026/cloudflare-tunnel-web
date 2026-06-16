#!/usr/bin/env bash
# 打包 CFWEB 项目以便分发到其他机器

set -euo pipefail

CFWEB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(date +%Y%m%d_%H%M%S)"
OUTPUT="/tmp/cfweb-${VERSION}.tar.gz"

# 颜色输出
BLUE='\033[1;34m'
GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${BLUE}[CFWEB-Package]${NC} $*"; }
info() { echo -e "${GREEN}[CFWEB-Package]${NC} $*"; }

log "打包 CFWEB 项目..."

EXCLUDES=(
    --exclude='*.log'
    --exclude='tmp/*'
    --exclude='credentials/*.pem'
    --exclude='credentials/*.json'
    --exclude='config.yml'
    --exclude='config.json'
    --exclude='*.tar.gz'
    --exclude='.git'
    --exclude='__pycache__'
    --exclude='*.pyc'
    --exclude='*.pyo'
)

# 默认排除 cloudflared 二进制（架构可能不同），需要包含时设置 INCLUDE_CLOUDFLARED=1
if [[ "${INCLUDE_CLOUDFLARED:-0}" != "1" ]]; then
    EXCLUDES+=(--exclude='bin/cloudflared')
fi

cd "$(dirname "${CFWEB_DIR}")"

tar -czf "${OUTPUT}" "${EXCLUDES[@]}" "$(basename "${CFWEB_DIR}")"

info "打包完成: ${OUTPUT}"
echo ""
echo "分发到其他机器:"
echo "  scp ${OUTPUT} user@remote-host:/tmp/"
echo "  ssh user@remote-host 'cd /opt && tar -xzf /tmp/$(basename "${OUTPUT}") && cd CFWEB && cp config.json.example config.json && vim config.json && ./install.sh'"

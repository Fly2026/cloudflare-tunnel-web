#!/usr/bin/env bash
# 独立 cloudflared 下载脚本
# 用法:
#   ./download-cloudflared.sh                    # 自动选择最佳镜像
#   ./download-cloudflared.sh --output /path/bin  # 指定输出目录
#   CLOUDFLARED_MIRROR=https://your-mirror/ ./download-cloudflared.sh

set -euo pipefail

OUTDIR="${1:-}"
if [[ "$1" == "--output" ]]; then
    OUTDIR="$2"
fi
if [[ -z "${OUTDIR:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    OUTDIR="${SCRIPT_DIR}/../bin"
fi
mkdir -p "$OUTDIR"

case "$(uname -m)" in
    x86_64|amd64) ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *) echo "不支持的架构: $(uname -m)"; exit 1 ;;
esac

DEST="${OUTDIR}/cloudflared"
FILENAME="cloudflared-linux-${ARCH}"
OFFICIAL_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/${FILENAME}"

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[1;34m'; NC='\033[0m'
log()    { echo -e "${BLUE}[CF]${NC} $*"; }
info()   { echo -e "${GREEN}[CF]${NC} $*"; }
warn()   { echo -e "${YELLOW}[CF]${NC} $*"; }
err()    { echo -e "${RED}[CF]${NC} $*"; }

if [[ -f "$DEST" ]]; then
    info "cloudflared 已存在: $DEST"
    info "版本: $("$DEST" version 2>/dev/null || echo 'unknown')"
    exit 0
fi

log "下载 cloudflared (linux-${ARCH})..."

# 下载函数
try() {
    curl -fsSL --connect-timeout 10 --max-time 600 "$1" -o "$DEST" 2>/dev/null
}

# ── 1. 用户镜像 ──
if [[ -n "${CLOUDFLARED_MIRROR:-}" ]]; then
    log "  用户镜像: ${CLOUDFLARED_MIRROR}"
    if try "${CLOUDFLARED_MIRROR}/${FILENAME}"; then
        chmod +x "$DEST"
        info "成功（用户镜像）"
        exit 0
    fi
    warn "  不可用"
fi

# ── 2. 内置国内镜像 ──
MIRRORS=(
    "https://gh-proxy.com/${OFFICIAL_URL}"
    "https://ghproxy.net/${OFFICIAL_URL}"
    "https://mirror.ghproxy.com/${OFFICIAL_URL}"
    "https://github.moeyy.xyz/${OFFICIAL_URL}"
    "https://gh.ddlc.top/${OFFICIAL_URL}"
    "https://gh.con.sh/${OFFICIAL_URL}"
    "https://gh.api.99988866.xyz/${OFFICIAL_URL}"
    "https://download.fastgit.org/cloudflare/cloudflared/releases/latest/download/${FILENAME}"
    "https://gh2.yanqishui.work/${OFFICIAL_URL}"
)

for url in "${MIRRORS[@]}"; do
    log "  尝试: ${url%%/https*}..."
    if try "$url"; then
        chmod +x "$DEST"
        info "成功（国内镜像）"
        exit 0
    fi
    warn "  不可用"
done

# ── 3. 官方源 ──
log "  尝试官方源..."
if try "$OFFICIAL_URL"; then
    chmod +x "$DEST"
    info "成功（官方源）"
    exit 0
fi

# ── 4. DNS 绕过 ──
warn "  官方源失败，尝试 DNS 绕过..."
RESOLVED_IP=""
for dns in "8.8.8.8" "114.114.114.114" "223.5.5.5"; do
    RESOLVED_IP=$(dig @"$dns" +short release-assets.githubusercontent.com 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)
    [[ -n "$RESOLVED_IP" ]] && break
done

KNOWN_IPS=("185.199.108.133" "185.199.109.133" "185.199.110.133" "185.199.111.133")
IPLIST=()
[[ -n "$RESOLVED_IP" ]] && IPLIST+=("$RESOLVED_IP")
IPLIST+=("${KNOWN_IPS[@]}")

for ip in "${IPLIST[@]}"; do
    warn "  IP: $ip"
    if try "$OFFICIAL_URL" && curl -fsSL --connect-timeout 10 --max-time 600 \
        --resolve "release-assets.githubusercontent.com:443:$ip" \
        "$OFFICIAL_URL" -o "$DEST"; then
        chmod +x "$DEST"
        info "成功（DNS 绕过: $ip）"
        exit 0
    fi
done

# ── 失败 ──
err "所有下载源均不可用。"
err ""
err "手动下载方法："
err "  从浏览器下载: $OFFICIAL_URL"
err "  放到: $DEST"
err "  chmod +x $DEST"
err ""
err "或设置可用镜像: CLOUDFLARED_MIRROR=https://your-mirror/path"
exit 1
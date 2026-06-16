#!/usr/bin/env bash
# CFWEB 核心安装脚本
# 负责下载 cloudflared、登录、创建 tunnel、生成配置、配置 DNS、启动服务

set -euo pipefail

CFWEB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="${CFWEB_DIR}/config.json"
CONFIG_YAML="${CFWEB_DIR}/config.yml"
BIN_DIR="${CFWEB_DIR}/bin"
CRED_DIR="${CFWEB_DIR}/credentials"
LOG_DIR="${CFWEB_DIR}/logs"
TMP_DIR="${CFWEB_DIR}/tmp"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[CFWEB-Setup]${NC} $*"; }
info() { echo -e "${GREEN}[CFWEB-Setup]${NC} $*"; }
warn() { echo -e "${YELLOW}[CFWEB-Setup]${NC} $*"; }
err() { echo -e "${RED}[CFWEB-Setup]${NC} $*" && exit 1; }

# 读取配置
DOMAIN="$(jq -r '.domain' "${CONFIG_FILE}")"
TUNNEL_NAME="$(jq -r '.tunnel_name // "cfweb-tunnel"' "${CONFIG_FILE}")"
ALI_KEY="$(jq -r '.aliyun.access_key_id' "${CONFIG_FILE}")"
ALI_SECRET="$(jq -r '.aliyun.access_key_secret' "${CONFIG_FILE}")"
ALI_REGION="$(jq -r '.aliyun.region // "cn-hangzhou"' "${CONFIG_FILE}")"

ensure_dirs() {
    mkdir -p "${BIN_DIR}" "${CRED_DIR}" "${LOG_DIR}" "${TMP_DIR}"
    chmod 700 "${CRED_DIR}"
}

download_cloudflared() {
    local arch dest url
    case "$(uname -m)" in
        x86_64|amd64) arch="amd64" ;;
        aarch64|arm64) arch="arm64" ;;
        *) err "不支持的架构: $(uname -m)" ;;
    esac

    dest="${BIN_DIR}/cloudflared"
    if [[ -f "${dest}" ]]; then
        info "cloudflared 已存在: ${dest}"
        return 0
    fi

    url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}"
    log "下载 cloudflared (linux-${arch})..."
    curl -fL --progress-bar "${url}" -o "${dest}" || err "下载 cloudflared 失败"
    chmod +x "${dest}"
    info "cloudflared 下载完成"
}

cloudflared_login() {
    local cert_file="${CRED_DIR}/cert.pem"
    if [[ -f "${cert_file}" ]]; then
        info "cloudflared 已登录 (${cert_file})"
        return 0
    fi

    log "执行 cloudflared 登录..."
    log "如果当前机器没有浏览器，请将弹出的 URL 复制到本地浏览器完成授权。"
    "${BIN_DIR}/cloudflared" tunnel login --cred-file "${cert_file}" || err "cloudflared 登录失败"

    # 如果 cloudflared 仍把 cert.pem 写到默认位置，复制到我们的目录
    local default_cert="${HOME}/.cloudflared/cert.pem"
    if [[ ! -f "${cert_file}" && -f "${default_cert}" ]]; then
        cp "${default_cert}" "${cert_file}"
    fi

    [[ -f "${cert_file}" ]] || err "未找到登录凭证文件"
    chmod 600 "${cert_file}"
    info "cloudflared 登录成功"
}

create_tunnel() {
    local info_file="${CRED_DIR}/tunnel-info.json"
    local cred_file="${CRED_DIR}/cert.pem"
    local cloudflared_dir="${HOME}/.cloudflared"

    if [[ -f "${info_file}" ]]; then
        info "Tunnel 已存在: $(jq -r '.tunnel_name' "${info_file}")"
        return 0
    fi

    log "创建 Cloudflare Tunnel: ${TUNNEL_NAME}..."
    local output
    output="$(${BIN_DIR}/cloudflared tunnel create --cred-file "${cred_file}" "${TUNNEL_NAME}" 2>&1)" || {
        echo "${output}" >&2
        err "创建 tunnel 失败"
    }
    echo "${output}"

    # 从输出中提取 tunnel ID
    local tunnel_id=""
    if [[ "${output}" =~ cloudflared[[:space:]]has[[:space:]]generated[[:space:]]an[[:space:]]ID[[:space:]]for[[:space:]]your[[:space:]]tunnel:[[:space:]]+([a-f0-9\-]+) ]]; then
        tunnel_id="${BASH_REMATCH[1]}"
    fi

    # 如果输出解析失败，从 ~/.cloudflared 目录中查找刚生成的凭证文件
    if [[ -z "${tunnel_id}" ]]; then
        warn "未能从输出解析 tunnel ID，尝试从凭证文件推断..."
        tunnel_id="$(python3 - "$cloudflared_dir" <<'PY'
import json, os, sys
dir_path = sys.argv[1]
tunnel_id = None
latest_mtime = 0
for name in os.listdir(dir_path):
    if not name.endswith('.json'):
        continue
    path = os.path.join(dir_path, name)
    try:
        with open(path) as f:
            data = json.load(f)
        tid = data.get('TunnelID')
        if not tid:
            continue
        mtime = os.path.getmtime(path)
        if mtime > latest_mtime:
            latest_mtime = mtime
            tunnel_id = tid
    except Exception:
        continue
print(tunnel_id or '')
PY
        )"
    fi

    [[ -n "${tunnel_id}" ]] || err "无法获取 tunnel ID"

    # 复制 tunnel 凭证文件到项目目录
    local src_cred="${cloudflared_dir}/${tunnel_id}.json"
    # 有时文件名可能包含大写 UUID，cloudflared 实际生成的文件名与 TunnelID 一致
    if [[ ! -f "${src_cred}" ]]; then
        # 尝试查找包含该 TunnelID 的任何 json 文件
        src_cred="$(python3 - "$cloudflared_dir" "$tunnel_id" <<'PY'
import json, os, sys
dir_path, tid = sys.argv[1], sys.argv[2]
for name in os.listdir(dir_path):
    if not name.endswith('.json'):
        continue
    path = os.path.join(dir_path, name)
    try:
        with open(path) as f:
            data = json.load(f)
        if data.get('TunnelID') == tid:
            print(path)
            break
    except Exception:
        continue
PY
        )"
    fi

    [[ -f "${src_cred}" ]] || err "未找到 tunnel 凭证文件"

    local dst_cred="${CRED_DIR}/${tunnel_id}.json"
    cp "${src_cred}" "${dst_cred}"
    chmod 600 "${dst_cred}"

    # 保存 tunnel 信息
    cat > "${info_file}" <<EOF
{
  "tunnel_id": "${tunnel_id}",
  "tunnel_name": "${TUNNEL_NAME}"
}
EOF
    chmod 600 "${info_file}"
    info "Tunnel 创建成功: ${TUNNEL_NAME} (${tunnel_id})"
}

generate_config() {
    local tunnel_id info_file cred_file
    info_file="${CRED_DIR}/tunnel-info.json"
    tunnel_id="$(jq -r '.tunnel_id' "${info_file}")"
    cred_file="${CRED_DIR}/${tunnel_id}.json"

    log "生成 cloudflared 配置文件..."

    cat > "${CONFIG_YAML}" <<EOF
tunnel: ${tunnel_id}
credentials-file: ${cred_file}

ingress:
EOF

    local count=0
    while IFS= read -r svc; do
        local folder host port
        folder="$(echo "${svc}" | jq -r '.folder')"
        host="$(echo "${svc}" | jq -r '.host // "localhost"')"
        port="$(echo "${svc}" | jq -r '.port')"

        if [[ -z "${folder}" || -z "${port}" ]]; then
            warn "跳过无效服务配置: ${svc}"
            continue
        fi

        cat >> "${CONFIG_YAML}" <<EOF
  - hostname: ${folder}.${DOMAIN}
    service: http://${host}:${port}
EOF
        count=$((count + 1))
    done < <(jq -c '.services[]' "${CONFIG_FILE}")

    # 默认兜底规则
    cat >> "${CONFIG_YAML}" <<EOF
  - service: http_status:404
EOF

    [[ "${count}" -gt 0 ]] || err "config.json 中未配置有效服务"
    info "配置文件生成完成: ${CONFIG_YAML} (${count} 个服务)"
}

setup_alidns() {
    local tunnel_id cname_target
    tunnel_id="$(jq -r '.tunnel_id' "${CRED_DIR}/tunnel-info.json")"
    cname_target="${tunnel_id}.cfargotunnel.com"

    log "配置阿里云 DNS 解析 (CNAME 目标: ${cname_target})..."
    python3 "${CFWEB_DIR}/scripts/alidns.py" \
        --access-key "${ALI_KEY}" \
        --access-secret "${ALI_SECRET}" \
        --domain "${DOMAIN}" \
        --cname-target "${cname_target}" \
        --config "${CONFIG_FILE}" || err "阿里云 DNS 配置失败"
    info "阿里云 DNS 配置完成"
}

setup_systemd() {
    if [[ "${CREATE_SERVICE:-0}" != "1" ]]; then
        return 0
    fi

    log "创建 systemd 服务..."
    local service_file="/etc/systemd/system/cfweb.service"

    # 从模板生成，替换变量
    sed \
        -e "s|{{CFWEB_DIR}}|${CFWEB_DIR}|g" \
        -e "s|{{USER}}|${USER}|g" \
        "${CFWEB_DIR}/systemd/cfweb.service.template" \
        | sudo tee "${service_file}" > /dev/null

    sudo systemctl daemon-reload
    sudo systemctl enable cfweb
    info "systemd 服务已创建: cfweb"
}

start_tunnel() {
    log "启动 Cloudflare Tunnel..."
    bash "${CFWEB_DIR}/scripts/start-tunnel.sh" || err "启动 tunnel 失败"
}

main() {
    log "开始 CFWEB 安装..."
    log "项目目录: ${CFWEB_DIR}"

    [[ -f "${CONFIG_FILE}" ]] || err "未找到配置文件: ${CONFIG_FILE}"
    command -v jq >/dev/null 2>&1 || err "缺少 jq，请先安装"
    command -v python3 >/dev/null 2>&1 || err "缺少 python3，请先安装"
    command -v curl >/dev/null 2>&1 || err "缺少 curl，请先安装"

    ensure_dirs
    download_cloudflared
    cloudflared_login
    create_tunnel
    generate_config
    setup_alidns
    setup_systemd
    start_tunnel

    info "=========================================="
    info "CFWEB 安装完成！"
    info "=========================================="
    echo ""
    echo "公网访问地址:"
    while IFS= read -r svc; do
        local folder host port
        folder="$(echo "${svc}" | jq -r '.folder')"
        host="$(echo "${svc}" | jq -r '.host // "localhost"')"
        port="$(echo "${svc}" | jq -r '.port')"
        echo "  https://${folder}.${DOMAIN}  ->  http://${host}:${port}"
    done < <(jq -c '.services[]' "${CONFIG_FILE}")
    echo ""
    echo "管理命令:"
    echo "  启动: ${CFWEB_DIR}/scripts/start-tunnel.sh"
    echo "  停止: ${CFWEB_DIR}/scripts/stop-tunnel.sh"
    echo "  状态: ${CFWEB_DIR}/scripts/status.sh"
    if [[ "${CREATE_SERVICE:-0}" == "1" ]]; then
        echo "  systemd: sudo systemctl {start|stop|status} cfweb"
    fi
}

main "$@"

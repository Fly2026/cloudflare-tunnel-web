# CFWEB — 一键 Cloudflare Tunnel 内网穿透

CFWEB 是一个基于 [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) 的一键部署脚本系统，可将本地或内网服务通过子域名方式暴露到公网，并自动使用阿里云 RAM 用户配置 DNS CNAME 解析。

## 特性

- 子域名映射：`foldername.domain.tld` → `http://host:port`
- 支持本地服务与跨机器内网服务
- 自动下载 `cloudflared` 二进制
- 自动创建 Cloudflare Tunnel
- 自动调用阿里云 DNS API 添加/更新 CNAME 记录
- 一键打包，支持在其他机器解压后快速部署
- 可选 systemd 服务与开机自启

## 快速开始

### 1. 安装依赖

确保系统已安装 `bash`、`curl`、`jq`、`python3`。

### 2. 填写配置

```bash
cd /AAAA/CFWEB
cp config.json.example config.json
vim config.json
```

配置示例：

```json
{
  "domain": "example.com",
  "tunnel_name": "cfweb-tunnel",
  "aliyun": {
    "access_key_id": "LTAIxxxxxxxxxxxx",
    "access_key_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "region": "cn-hangzhou"
  },
  "services": [
    {
      "folder": "blog",
      "host": "localhost",
      "port": 3000,
      "description": "博客服务"
    },
    {
      "folder": "api",
      "host": "192.168.1.10",
      "port": 8080,
      "description": "内网 API 服务"
    }
  ]
}
```

字段说明：

| 字段 | 说明 |
|------|------|
| `domain` | 你的阿里云 DNS 托管域名 |
| `tunnel_name` | Cloudflare Tunnel 名称 |
| `aliyun.access_key_id` | 阿里云 RAM 用户 AccessKey ID |
| `aliyun.access_key_secret` | 阿里云 RAM 用户 AccessKey Secret |
| `aliyun.region` | 阿里云区域，默认 `cn-hangzhou` |
| `services` | 服务列表 |
| `services[].folder` | 子域名前缀，必须为英文/数字/连字符 |
| `services[].host` | 服务所在主机，默认 `localhost` |
| `services[].port` | 服务端口号 |

### 3. 一键安装

```bash
./install.sh
```

脚本会：

1. 下载 `cloudflared`
2. 引导你在浏览器中登录 Cloudflare 账号（无浏览器时请复制 URL 到本地浏览器）
3. 创建 Cloudflare Tunnel
4. 生成 `config.yml`
5. 调用阿里云 DNS API 添加 CNAME 记录
6. 启动 tunnel

### 4. 管理命令

```bash
# 启动
./scripts/start-tunnel.sh

# 停止
./scripts/stop-tunnel.sh

# 查看状态
./scripts/status.sh
```

### 5. 创建 systemd 服务（可选）

```bash
CREATE_SERVICE=1 ./install.sh
```

之后可通过 systemctl 管理：

```bash
sudo systemctl start cfweb
sudo systemctl stop cfweb
sudo systemctl status cfweb
sudo systemctl enable cfweb  # 开机自启
```

## 一键打包与跨机器部署

### 打包

```bash
./scripts/package.sh
```

会生成类似 `cfweb-20240616_143022.tar.gz` 的文件。

### 部署到新机器

```bash
# 复制包
scp cfweb-20240616_143022.tar.gz root@remote-host:/tmp/

# 在新机器上解压并安装
ssh root@remote-host "
  cd /opt && \
  tar -xzf /tmp/cfweb-20240616_143022.tar.gz && \
  cd CFWEB && \
  cp config.json.example config.json && \
  vim config.json && \
  ./install.sh
"
```

## 阿里云 RAM 权限

脚本需要 RAM 用户具有 DNS 管理权限。你可以：

- 授予 `AliyunDNSFullAccess`（简单）
- 或创建自定义最小权限策略，允许对指定域名执行 `AddDomainRecord`、`UpdateDomainRecord`、`DescribeDomainRecords`

## 注意事项

- `config.json` 包含阿里云 AccessKey Secret，请妥善保管，不要提交到公开仓库。
- `credentials/` 目录包含 Cloudflare 凭证文件，打包时会被排除，新机器需重新登录并创建 tunnel。
- DNS 解析生效可能需要几分钟时间，请耐心等待。

## 验证

```bash
# 检查 cloudflared
./bin/cloudflared version
./bin/cloudflared tunnel list

# 检查 DNS
dig blog.example.com CNAME +short

# 公网访问（DNS 生效后）
curl https://blog.example.com
```

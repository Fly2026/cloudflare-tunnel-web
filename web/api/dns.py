#!/usr/bin/env python3
"""CFWEB Web DNS 同步 API"""

import json
import os
import subprocess

from web import auth


def get_project_dir() -> str:
    return auth.get_project_dir()


def get_tunnel_id() -> str:
    """从 credentials/tunnel-info.json 读取 tunnel ID。"""
    info_file = os.path.join(get_project_dir(), "credentials", "tunnel-info.json")
    if not os.path.exists(info_file):
        return None
    try:
        with open(info_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tunnel_id")
    except Exception:
        return None


def sync_handler(query, body, headers):
    """POST /api/dns/sync"""
    config = auth.load_config()
    tunnel_id = get_tunnel_id()
    if not tunnel_id:
        return 400, {"success": False, "error": "未找到 tunnel ID，请先完成安装流程"}, {}

    domain = config.get("domain", "")
    ali_key = config.get("aliyun", {}).get("access_key_id", "")
    ali_secret = config.get("aliyun", {}).get("access_key_secret", "")
    if not domain or not ali_key or not ali_secret:
        return 400, {"success": False, "error": "域名或阿里云凭证未配置"}, {}

    cname_target = f"{tunnel_id}.cfargotunnel.com"
    config_path = auth.get_config_path()
    alidns_path = os.path.join(get_project_dir(), "scripts", "alidns.py")

    try:
        result = subprocess.run(
            [
                "python3", alidns_path,
                "--access-key", ali_key,
                "--access-secret", ali_secret,
                "--domain", domain,
                "--cname-target", cname_target,
                "--config", config_path,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=get_project_dir(),
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
        return 200 if success else 500, {
            "success": success,
            "message": "DNS 同步成功" if success else "DNS 同步失败",
            "output": output,
            "cname_target": cname_target,
        }, {}
    except subprocess.TimeoutExpired:
        return 500, {"success": False, "error": "DNS 同步超时"}, {}
    except Exception as e:
        return 500, {"success": False, "error": str(e)}, {}

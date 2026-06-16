#!/usr/bin/env python3
"""CFWEB Web 配置 API"""

import json
import os
import re

from web import auth

CONFIG_PATH = auth.get_config_path()


def load_config() -> dict:
    """加载 config.json。"""
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict) -> None:
    """保存 config.json 并设置权限。"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    os.chmod(CONFIG_PATH, 0o600)


def validate_config(config: dict) -> tuple:
    """验证配置是否合法，返回 (is_valid, error_message)。"""
    domain = config.get("domain", "").strip()
    if not domain:
        return False, "domain 不能为空"

    services = config.get("services", [])
    if not isinstance(services, list):
        return False, "services 必须是数组"

    folder_pattern = re.compile(r"^[a-zA-Z0-9-]+$")
    for i, svc in enumerate(services):
        folder = svc.get("folder", "").strip()
        if not folder:
            return False, f"第 {i+1} 个服务 folder 不能为空"
        if not folder_pattern.match(folder):
            return False, f"第 {i+1} 个服务 folder 只能包含英文、数字、连字符"
        port = svc.get("port")
        try:
            port = int(port)
            if not (1 <= port <= 65535):
                raise ValueError
        except (TypeError, ValueError):
            return False, f"第 {i+1} 个服务 port 必须是 1-65535 的整数"

    # 阿里云凭证基础校验
    aliyun = config.get("aliyun", {})
    if aliyun:
        secret = aliyun.get("access_key_secret", "")
        if secret and len(secret) < 20:
            return False, "阿里云 AccessKey Secret 长度异常，请检查是否复制完整（正常为 30 位）"

    return True, ""


def validate_services(services: list) -> tuple:
    """单独验证 services 数组。"""
    if not isinstance(services, list):
        return False, "services 必须是数组"
    folder_pattern = re.compile(r"^[a-zA-Z0-9-]+$")
    for i, svc in enumerate(services):
        folder = svc.get("folder", "").strip()
        if not folder:
            return False, f"第 {i+1} 个服务 folder 不能为空"
        if not folder_pattern.match(folder):
            return False, f"第 {i+1} 个服务 folder 只能包含英文、数字、连字符"
        port = svc.get("port")
        try:
            port = int(port)
            if not (1 <= port <= 65535):
                raise ValueError
        except (TypeError, ValueError):
            return False, f"第 {i+1} 个服务 port 必须是 1-65535 的整数"
    return True, ""


def mask_secret(secret: str) -> str:
    """对敏感字段进行脱敏。"""
    if not secret or len(secret) <= 8:
        return "****"
    return secret[:4] + "****" + secret[-4:]


def sanitize_config(config: dict) -> dict:
    """返回给前端的配置，敏感字段脱敏。"""
    result = json.loads(json.dumps(config))
    if "aliyun" in result and "access_key_secret" in result["aliyun"]:
        result["aliyun"]["access_key_secret"] = mask_secret(result["aliyun"]["access_key_secret"])
    if "web" in result and "password_hash" in result["web"]:
        result["web"]["password_hash"] = mask_secret(result["web"]["password_hash"])
    return result


def get_config_handler(query, body, headers):
    """GET /api/config"""
    config = load_config()
    auth.ensure_default_auth(config)
    return 200, {"success": True, "config": sanitize_config(config)}, {}


def post_config_handler(query, body, headers):
    """POST /api/config"""
    new_config = body.get("config", {})
    valid, error = validate_config(new_config)
    if not valid:
        return 400, {"success": False, "error": error}, {}

    # 保护 web 认证配置：如果前端没传或脱敏，保留原值
    old_config = load_config()
    if "web" not in new_config and "web" in old_config:
        new_config["web"] = old_config["web"]
    elif "web" in new_config:
        old_web = old_config.get("web", {})
        new_web = new_config["web"]
        # 如果前端提交了新密码明文，重新哈希
        if "password" in new_web and new_web["password"]:
            new_web["password_hash"] = auth.hash_password(new_web.pop("password"))
        # 如果密码哈希被脱敏，保留原值
        elif "password_hash" in new_web and "****" in new_web["password_hash"]:
            new_web["password_hash"] = old_web.get("password_hash", auth.hash_password("admin"))
        # 如果端口缺失，保留原值
        if "port" not in new_web and "port" in old_web:
            new_web["port"] = old_web["port"]
        # 如果用户名缺失，保留原值
        if "username" not in new_web and "username" in old_web:
            new_web["username"] = old_web["username"]

    save_config(new_config)
    return 200, {"success": True, "config": sanitize_config(new_config)}, {}


def get_services_handler(query, body, headers):
    """GET /api/config/services"""
    config = load_config()
    return 200, {"success": True, "services": config.get("services", [])}, {}


def post_services_handler(query, body, headers):
    """POST /api/config/services"""
    services = body.get("services", [])
    valid, error = validate_services(services)
    if not valid:
        return 400, {"success": False, "error": error}, {}
    config = load_config()
    config["services"] = services
    save_config(config)
    return 200, {"success": True, "services": services}, {}

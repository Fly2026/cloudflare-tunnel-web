#!/usr/bin/env python3
"""CFWEB Web 管理平台认证模块"""

import hashlib
import json
import os
import secrets
import time
from pathlib import Path

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"
SESSION_TIMEOUT = 3600  # 1 小时


def hash_password(password: str) -> str:
    """对密码进行 SHA256 哈希，返回 sha256:hex 格式。"""
    h = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return f"sha256:{h}"


def verify_password(password: str, hashed: str) -> bool:
    """验证密码是否匹配哈希值。"""
    if not hashed:
        return False
    if ":" in hashed:
        _, stored_hash = hashed.split(":", 1)
    else:
        stored_hash = hashed
    return hashlib.sha256(password.encode("utf-8")).hexdigest() == stored_hash


def get_project_dir() -> str:
    """获取项目根目录。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config_path() -> str:
    """获取 config.json 路径。"""
    return os.path.join(get_project_dir(), "config.json")


def load_config() -> dict:
    """加载 config.json，不存在时返回空字典。"""
    path = get_config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: dict) -> None:
    """保存 config.json。"""
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    os.chmod(path, 0o600)


def get_auth_config(config: dict = None) -> dict:
    """获取 Web 认证配置，不存在时使用默认值。"""
    if config is None:
        config = load_config()
    web_cfg = config.get("web", {})
    return {
        "username": web_cfg.get("username", DEFAULT_USERNAME),
        "password_hash": web_cfg.get("password_hash", hash_password(DEFAULT_PASSWORD)),
    }


def ensure_default_auth(config: dict = None) -> None:
    """如果 config.json 中缺少 web 认证配置，写入默认配置。"""
    if config is None:
        config = load_config()
    if "web" not in config:
        config["web"] = {}
    web_cfg = config["web"]
    changed = False
    if "username" not in web_cfg:
        web_cfg["username"] = DEFAULT_USERNAME
        changed = True
    if "password_hash" not in web_cfg:
        web_cfg["password_hash"] = hash_password(DEFAULT_PASSWORD)
        changed = True
    if "port" not in web_cfg:
        web_cfg["port"] = 50000
        changed = True
    if changed:
        save_config(config)


class SessionManager:
    """简单的内存 Session 管理器。"""

    def __init__(self):
        self.sessions = {}

    def create_session(self) -> str:
        """创建新 session，返回 token。"""
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {"expires": time.time() + SESSION_TIMEOUT}
        return token

    def verify_session(self, token: str) -> bool:
        """验证 session 是否有效。"""
        if not token or token not in self.sessions:
            return False
        sess = self.sessions[token]
        if sess["expires"] < time.time():
            del self.sessions[token]
            return False
        return True

    def destroy_session(self, token: str) -> None:
        """销毁 session。"""
        self.sessions.pop(token, None)

    def refresh_session(self, token: str) -> bool:
        """刷新 session 过期时间。"""
        if not self.verify_session(token):
            return False
        self.sessions[token]["expires"] = time.time() + SESSION_TIMEOUT
        return True


def parse_cookie(cookie_header: str) -> dict:
    """解析 Cookie 头。"""
    cookies = {}
    if not cookie_header:
        return cookies
    for part in cookie_header.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            cookies[key.strip()] = value.strip()
    return cookies


# API handlers

def login_handler(query, body, headers):
    """处理 /api/auth/login 登录请求。"""
    username = body.get("username", "")
    password = body.get("password", "")
    cfg = load_config()
    auth_cfg = get_auth_config(cfg)

    if username != auth_cfg["username"]:
        return 401, {"success": False, "error": "用户名或密码错误"}, {}
    if not verify_password(password, auth_cfg["password_hash"]):
        return 401, {"success": False, "error": "用户名或密码错误"}, {}

    token = session_manager.create_session()
    return 200, {"success": True, "message": "登录成功"}, {
        "Set-Cookie": f"cfweb_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TIMEOUT}"
    }


def logout_handler(query, body, headers):
    """处理 /api/auth/logout 登出请求。"""
    cookies = parse_cookie(headers.get("Cookie", ""))
    token = cookies.get("cfweb_session", "")
    session_manager.destroy_session(token)
    return 200, {"success": True, "message": "已退出登录"}, {
        "Set-Cookie": "cfweb_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
    }


def status_handler(query, body, headers):
    """处理 /api/auth/status 认证状态请求。"""
    cookies = parse_cookie(headers.get("Cookie", ""))
    token = cookies.get("cfweb_session", "")
    return 200, {"success": True, "authenticated": session_manager.verify_session(token)}, {}


# 全局 session 管理器实例
session_manager = SessionManager()

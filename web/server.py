#!/usr/bin/env python3
"""CFWEB Web 管理平台 HTTP 服务器

基于 Python3 标准库 http.server 实现，零外部依赖。
"""

import json
import mimetypes
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

# 确保项目根目录在路径中
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from web import auth
from web.api import config as config_api
from web.api import tunnel as tunnel_api
from web.api import dns as dns_api
from web.api import setup as setup_api
from web.api import logs as logs_api
from web.api import package as package_api


# 静态文件目录
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# API 路由表：method + path -> handler function
API_ROUTES = {
    ("POST", "/api/auth/login"): auth.login_handler,
    ("POST", "/api/auth/logout"): auth.logout_handler,
    ("GET", "/api/auth/status"): auth.status_handler,
    ("GET", "/api/config"): config_api.get_config_handler,
    ("POST", "/api/config"): config_api.post_config_handler,
    ("GET", "/api/config/services"): config_api.get_services_handler,
    ("POST", "/api/config/services"): config_api.post_services_handler,
    ("GET", "/api/tunnel/status"): tunnel_api.status_handler,
    ("POST", "/api/tunnel/start"): tunnel_api.start_handler,
    ("POST", "/api/tunnel/stop"): tunnel_api.stop_handler,
    ("POST", "/api/tunnel/restart"): tunnel_api.restart_handler,
    ("POST", "/api/dns/sync"): dns_api.sync_handler,
    ("POST", "/api/setup/install"): setup_api.install_handler,
    ("GET", "/api/setup/progress"): setup_api.progress_handler,
    ("GET", "/api/logs/tunnel"): logs_api.get_logs_handler,
    ("GET", "/api/logs/stream"): logs_api.stream_logs_handler,
    ("POST", "/api/package/create"): package_api.create_handler,
}


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """支持多线程的 HTTP 服务器。"""
    daemon_threads = True
    allow_reuse_address = True


class CFWEBHandler(BaseHTTPRequestHandler):
    """请求处理器。"""

    def log_message(self, format, *args):
        """自定义日志，写入 stderr。"""
        sys.stderr.write(f"[CFWEB-Web] {self.address_string()} - {format % args}\n")

    def _send_cors_headers(self):
        """发送 CORS 响应头。"""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status: int, data: dict, extra_headers: dict = None):
        """发送 JSON 响应。"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors_headers()
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_error(self, status: int, message: str):
        """发送错误响应。"""
        self._send_json(status, {"success": False, "error": message})

    def _parse_body(self) -> dict:
        """解析 JSON 请求体。"""
        content_length = self.headers.get("Content-Length")
        if not content_length:
            return {}
        try:
            length = int(content_length)
            body = self.rfile.read(length).decode("utf-8")
            return json.loads(body) if body else {}
        except Exception:
            return {}

    def _parse_query(self) -> dict:
        """解析 URL 查询参数。"""
        parsed = urllib.parse.urlparse(self.path)
        return urllib.parse.parse_qs(parsed.query)

    def _get_path(self) -> str:
        """获取不带查询参数的路径。"""
        return urllib.parse.urlparse(self.path).path

    def _is_public_path(self, path: str) -> bool:
        """判断是否为无需认证的公开路径。"""
        public_prefixes = (
            "/static/",
            "/login",
            "/api/auth/login",
            "/api/auth/status",
        )
        return any(path == p or path.startswith(p) for p in public_prefixes)

    def _check_auth(self) -> bool:
        """检查当前请求是否已认证。"""
        cookies = auth.parse_cookie(self.headers.get("Cookie", ""))
        token = cookies.get("cfweb_session", "")
        return auth.session_manager.verify_session(token)

    def _serve_static(self, path: str):
        """服务静态文件。"""
        # 根路径返回 index.html
        if path == "/" or path == "/index.html":
            file_path = os.path.join(STATIC_DIR, "index.html")
        else:
            # 去掉 /static/ 前缀
            if path.startswith("/static/"):
                rel_path = path[len("/static/"):]
            else:
                rel_path = path.lstrip("/")
            file_path = os.path.join(STATIC_DIR, rel_path)

        # 防止目录遍历
        file_path = os.path.normpath(file_path)
        if not file_path.startswith(os.path.normpath(STATIC_DIR)):
            self._send_error(403, "Forbidden")
            return

        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            # SPA 路由：返回 index.html，由前端处理
            file_path = os.path.join(STATIC_DIR, "index.html")

        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self._send_cors_headers()
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._send_error(500, f"Failed to read file: {e}")

    def _handle_api(self, method: str):
        """处理 API 请求。"""
        path = self._get_path()
        query = self._parse_query()
        body = self._parse_body()

        # 公开 API 不需要认证
        if not self._is_public_path(path):
            if not self._check_auth():
                self._send_error(401, "Unauthorized")
                return

        handler = API_ROUTES.get((method, path))
        if not handler:
            self._send_error(404, "API not found")
            return

        try:
            result = handler(query, body, self.headers)
            # handler 返回 (status, data, headers)
            if isinstance(result, tuple):
                if len(result) == 3:
                    status, data, headers = result
                else:
                    status, data = result
                    headers = {}
            else:
                # SSE 处理：handler 自己写响应
                return

            # 处理 SSE 流（handler 返回 generator）
            if hasattr(data, "__iter__") and not isinstance(data, (dict, list, str)):
                self.send_response(status)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self._send_cors_headers()
                for k, v in headers.items():
                    self.send_header(k, v)
                self.end_headers()
                try:
                    for chunk in data:
                        self.wfile.write(chunk.encode("utf-8"))
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return

            self._send_json(status, data, headers)
        except Exception as e:
            self._send_error(500, f"Internal error: {e}")

    def do_OPTIONS(self):
        """处理 CORS 预检请求。"""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """处理 GET 请求。"""
        path = self._get_path()
        if path.startswith("/api/"):
            self._handle_api("GET")
        else:
            self._serve_static(path)

    def do_POST(self):
        """处理 POST 请求。"""
        path = self._get_path()
        if path.startswith("/api/"):
            self._handle_api("POST")
        else:
            self._send_error(405, "Method not allowed")


def get_web_port() -> int:
    """从 config.json 读取 Web 端口，默认 50000。"""
    config = auth.load_config()
    return config.get("web", {}).get("port", 50000)


def main():
    """主函数。"""
    # 确保默认认证配置存在
    auth.ensure_default_auth()

    port = get_web_port()
    server = ThreadedHTTPServer(("0.0.0.0", port), CFWEBHandler)
    print(f"[CFWEB-Web] 服务器启动于 http://0.0.0.0:{port}")
    print(f"[CFWEB-Web] 默认账号: admin, 默认密码: admin")
    print(f"[CFWEB-Web] 按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[CFWEB-Web] 正在停止...")
        server.shutdown()


if __name__ == "__main__":
    main()

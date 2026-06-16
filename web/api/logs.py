#!/usr/bin/env python3
"""CFWEB Web 日志 API"""

import os
import time

from web import auth


def get_log_file(log_type: str) -> str:
    """根据日志类型返回日志文件路径。"""
    if log_type == "tunnel":
        return os.path.join(auth.get_project_dir(), "logs", "tunnel.log")
    elif log_type == "setup":
        return os.path.join(auth.get_project_dir(), "logs", "setup.log")
    elif log_type == "web":
        return os.path.join(auth.get_project_dir(), "logs", "web.log")
    return os.path.join(auth.get_project_dir(), "logs", "tunnel.log")


def get_logs_handler(query, body, headers):
    """GET /api/logs/tunnel?lines=100&type=tunnel"""
    log_type = query.get("type", ["tunnel"])[0]
    lines = int(query.get("lines", ["100"])[0])
    log_file = get_log_file(log_type)

    if not os.path.exists(log_file):
        return 200, {"success": True, "log": "", "lines": 0}, {}

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        tail_lines = all_lines[-lines:] if lines > 0 else all_lines
        return 200, {
            "success": True,
            "log": "".join(tail_lines),
            "lines": len(tail_lines),
        }, {}
    except Exception as e:
        return 500, {"success": False, "error": str(e)}, {}


def stream_logs_handler(query, body, headers):
    """GET /api/logs/stream?type=tunnel (SSE)"""
    log_type = query.get("type", ["tunnel"])[0]
    log_file = get_log_file(log_type)

    accept = headers.get("Accept", "")
    if "text/event-stream" not in accept:
        # 非 SSE 请求返回最近 100 行
        return get_logs_handler({"type": [log_type], "lines": ["100"]}, {}, headers)

    def event_stream():
        # 先发送现有内容
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                existing = f.read()
            for line in existing.splitlines(keepends=True):
                yield f"data: {line.rstrip()}\n\n"

        last_size = os.path.getsize(log_file) if os.path.exists(log_file) else 0
        while True:
            try:
                if not os.path.exists(log_file):
                    time.sleep(0.5)
                    continue
                current_size = os.path.getsize(log_file)
                if current_size > last_size:
                    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_size)
                        new_data = f.read()
                    last_size = current_size
                    for line in new_data.splitlines(keepends=True):
                        yield f"data: {line.rstrip()}\n\n"
                time.sleep(0.5)
            except Exception as e:
                yield f"data: [ERROR:{e}]\n\n"
                time.sleep(1)

    return 200, event_stream(), {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

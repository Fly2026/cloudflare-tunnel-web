#!/usr/bin/env python3
"""CFWEB Web 安装部署 API"""

import json
import os
import subprocess
import time

from web import auth


class SetupManager:
    """管理安装进程。"""

    def __init__(self):
        self.process = None
        self.log_file = os.path.join(auth.get_project_dir(), "logs", "setup.log")
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        log_dir = os.path.dirname(self.log_file)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def is_running(self) -> bool:
        if self.process is None:
            return False
        if self.process.poll() is None:
            return True
        return False

    def start(self) -> bool:
        """启动安装流程。"""
        if self.is_running():
            return False

        # 清空日志
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("")

        setup_script = os.path.join(auth.get_project_dir(), "scripts", "setup.sh")
        self.process = subprocess.Popen(
            ["bash", setup_script],
            stdout=open(self.log_file, "w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            cwd=auth.get_project_dir(),
        )
        return True

    def get_log_tail(self, lines: int = 50) -> str:
        """获取日志尾部。"""
        if not os.path.exists(self.log_file):
            return ""
        try:
            with open(self.log_file, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            return "".join(all_lines[-lines:])
        except Exception:
            return ""

    def tail_log(self):
        """生成器：持续产生 SSE 数据。"""
        if not os.path.exists(self.log_file):
            # 等待日志文件创建
            for _ in range(10):
                if os.path.exists(self.log_file):
                    break
                time.sleep(0.5)

        last_size = 0
        while True:
            try:
                current_size = os.path.getsize(self.log_file)
                if current_size > last_size:
                    with open(self.log_file, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_size)
                        new_data = f.read()
                    last_size = current_size
                    for line in new_data.splitlines(keepends=True):
                        yield f"data: {line.rstrip()}\n\n"
                elif self.process and self.process.poll() is not None:
                    # 进程已结束
                    yield f"data: [SETUP_EXIT:{self.process.returncode}]\n\n"
                    break
                time.sleep(0.5)
            except Exception as e:
                yield f"data: [ERROR:{e}]\n\n"
                time.sleep(1)


# 全局安装管理器
setup_manager = SetupManager()


def install_handler(query, body, headers):
    """POST /api/setup/install"""
    if setup_manager.is_running():
        return 409, {"success": False, "error": "安装流程已在运行中"}, {}

    # 检查 config.json 是否还是示例
    config = auth.load_config()
    config_str = json.dumps(config)
    if "LTAIxxxxxxxxxxxx" in config_str or "example.com" in config_str or "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" in config_str:
        return 400, {"success": False, "error": "config.json 看起来还是示例内容，请先填写真实配置"}, {}

    if not setup_manager.start():
        return 500, {"success": False, "error": "启动安装流程失败"}, {}

    return 200, {"success": True, "message": "安装流程已启动"}, {}


def progress_handler(query, body, headers):
    """GET /api/setup/progress (SSE)"""
    lines = int(query.get("lines", ["50"])[0])
    # 如果是普通轮询请求（没有 Accept: text/event-stream），返回尾部日志
    accept = headers.get("Accept", "")
    if "text/event-stream" not in accept:
        return 200, {"success": True, "running": setup_manager.is_running(), "log": setup_manager.get_log_tail(lines)}, {}

    # SSE 流
    def event_stream():
        yield "data: [SETUP_STARTED]\n\n"
        for chunk in setup_manager.tail_log():
            yield chunk

    return 200, event_stream(), {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

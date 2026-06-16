#!/usr/bin/env python3
"""CFWEB Web tunnel 控制 API"""

import os
import subprocess
import time

from web import auth


def get_project_dir() -> str:
    return auth.get_project_dir()


def get_pid_file() -> str:
    return os.path.join(get_project_dir(), "tmp", "tunnel.pid")


def get_log_file() -> str:
    return os.path.join(get_project_dir(), "logs", "tunnel.log")


def is_running() -> bool:
    """检查 tunnel 是否在运行。"""
    pid_file = get_pid_file()
    if not os.path.exists(pid_file):
        return False
    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, OSError, ProcessLookupError):
        return False


def get_pid() -> int:
    """获取 tunnel PID。"""
    pid_file = get_pid_file()
    if not os.path.exists(pid_file):
        return None
    try:
        with open(pid_file, "r") as f:
            return int(f.read().strip())
    except ValueError:
        return None


def get_uptime_seconds() -> int:
    """获取 tunnel 运行时长（秒）。"""
    pid = get_pid()
    if not pid:
        return 0
    try:
        stat_file = f"/proc/{pid}/stat"
        if os.path.exists(stat_file):
            with open(stat_file, "r") as f:
                parts = f.read().split()
            # starttime 是第 22 个字段（从1开始计数）
            starttime = int(parts[21])
            # 获取系统启动时间
            with open("/proc/stat", "r") as f:
                for line in f:
                    if line.startswith("btime"):
                        btime = int(line.split()[1])
                        break
            boot_time = btime
            clock_ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
            start_time = boot_time + starttime / clock_ticks
            return int(time.time() - start_time)
    except Exception:
        pass
    return 0


def run_script(script_name: str) -> tuple:
    """调用 scripts 目录下的脚本，返回 (success, output)。"""
    script_path = os.path.join(get_project_dir(), "scripts", script_name)
    try:
        result = subprocess.run(
            ["bash", script_path],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=get_project_dir(),
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "操作超时"
    except Exception as e:
        return False, str(e)


def status_handler(query, body, headers):
    """GET /api/tunnel/status"""
    running = is_running()
    pid = get_pid() if running else None
    uptime = get_uptime_seconds() if running else 0
    return 200, {
        "success": True,
        "running": running,
        "pid": pid,
        "uptime_seconds": uptime,
    }, {}


def start_handler(query, body, headers):
    """POST /api/tunnel/start"""
    if is_running():
        return 200, {"success": True, "message": "Tunnel 已在运行"}, {}
    success, output = run_script("start-tunnel.sh")
    return 200 if success else 500, {
        "success": success,
        "message": "Tunnel 启动成功" if success else "Tunnel 启动失败",
        "output": output,
    }, {}


def stop_handler(query, body, headers):
    """POST /api/tunnel/stop"""
    if not is_running():
        return 200, {"success": True, "message": "Tunnel 未运行"}, {}
    success, output = run_script("stop-tunnel.sh")
    return 200 if success else 500, {
        "success": success,
        "message": "Tunnel 已停止" if success else "Tunnel 停止失败",
        "output": output,
    }, {}


def restart_handler(query, body, headers):
    """POST /api/tunnel/restart"""
    results = []
    if is_running():
        success, output = run_script("stop-tunnel.sh")
        results.append({"step": "stop", "success": success, "output": output})
        time.sleep(1)
    else:
        results.append({"step": "stop", "success": True, "output": "Tunnel 未运行"})

    success, output = run_script("start-tunnel.sh")
    results.append({"step": "start", "success": success, "output": output})

    all_success = all(r["success"] for r in results)
    return 200 if all_success else 500, {
        "success": all_success,
        "message": "Tunnel 重启成功" if all_success else "Tunnel 重启失败",
        "results": results,
    }, {}

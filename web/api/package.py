#!/usr/bin/env python3
"""CFWEB Web 打包 API"""

import os
import subprocess

from web import auth


def create_handler(query, body, headers):
    """POST /api/package/create"""
    package_script = os.path.join(auth.get_project_dir(), "scripts", "package.sh")
    try:
        result = subprocess.run(
            ["bash", package_script],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=auth.get_project_dir(),
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0

        # 从输出中提取 tar.gz 路径
        package_path = None
        for line in output.splitlines():
            if "打包完成:" in line:
                package_path = line.split("打包完成:", 1)[1].strip()
                break
            if line.endswith(".tar.gz") and "/tmp/" in line:
                package_path = line.strip()
                break

        return 200 if success else 500, {
            "success": success,
            "message": "打包成功" if success else "打包失败",
            "package_path": package_path,
            "output": output,
        }, {}
    except subprocess.TimeoutExpired:
        return 500, {"success": False, "error": "打包超时"}, {}
    except Exception as e:
        return 500, {"success": False, "error": str(e)}, {}

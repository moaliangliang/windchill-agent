"""SSH 连接工具 — 跨平台（Windows/Mac/Linux）"""
import io
import os
from typing import Optional, Tuple

from .config import settings


def _get_ssh_client():
    """获取 paramiko SSH 客户端（延迟导入，避免未安装时启动报错）"""
    import paramiko
    return paramiko.SSHClient()


def run_ssh(host: str = "", user: str = "", password: str = "",
            key_file: str = "", port: int = 22, command: str = "",
            timeout: int = 30) -> Tuple[bool, str]:
    """通过 SSH 执行远程命令"""
    host = host or settings.windchill_ssh_host
    user = user or settings.windchill_ssh_user
    password = password or settings.windchill_ssh_password
    key_file = key_file or settings.windchill_ssh_key
    port = port or settings.windchill_ssh_port

    if not host or not user:
        return False, "❌ SSH 未配置（需要 WINDCHILL_SSH_HOST/USER）"
    if not command:
        return False, "❌ 需要 command 参数"

    try:
        ssh = _get_ssh_client()
        ssh.set_missing_host_key_policy(__import__('paramiko').AutoAddPolicy())

        connect_kwargs = {"hostname": host, "username": user, "port": port, "timeout": timeout}
        if password:
            connect_kwargs["password"] = password
        if key_file and os.path.exists(os.path.expanduser(key_file)):
            connect_kwargs["key_filename"] = os.path.expanduser(key_file)

        ssh.connect(**connect_kwargs)
        _, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="ignore").strip()
        error = stderr.read().decode("utf-8", errors="ignore").strip()
        ssh.close()

        if exit_code != 0 and not output:
            return False, error or f"退出码: {exit_code}"
        return True, output
    except ImportError:
        return False, "❌ 需要 paramiko 库: pip install paramiko"
    except Exception as e:
        return False, f"❌ SSH 失败: {e}"

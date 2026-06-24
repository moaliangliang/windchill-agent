"""配置管理 — 从 .env 文件或环境变量读取

支持的配置项:

Windchill REST API:
  WINDCHILL_HOST           Windchill 服务器地址 (必填)
  WINDCHILL_HTTP_PORT      Windchill HTTP 端口 (默认 7380)
  WINDCHILL_ODATA_USER     OData API 用户名 (默认 wcadmin)
  WINDCHILL_ODATA_PASSWORD OData API 密码 (必填)

SSH (MethodServer/Oracle 管理):
  WINDCHILL_SSH_HOST       SSH 服务器地址
  WINDCHILL_SSH_PORT       SSH 端口 (22)
  WINDCHILL_SSH_USER       SSH 用户名
  WINDCHILL_SSH_PASSWORD   SSH 密码
  WINDCHILL_SSH_KEY        SSH 私钥路径
  WINDCHILL_HOME           Windchill 安装目录 (/opt/Windchill)

Oracle 数据库:
  ORACLE_HOST              Oracle 服务器地址
  ORACLE_PORT              Oracle 端口 (1521)
  ORACLE_SID               Oracle SID
  ORACLE_USER              Oracle 用户
  ORACLE_PASSWORD          Oracle 密码
  ORACLE_HOME              Oracle 安装目录

企业微信通知:
  WECOM_WEBHOOK_URL        企业微信机器人 Webhook
  WECOM_CORP_ID            企业微信 CorpID
  WECOM_AGENT_ID           企业微信 AgentID
  WECOM_CORP_SECRET        企业微信 Secret

配置加载优先级: 环境变量 > .env 文件
"""
import os
from pathlib import Path
from typing import Optional


class Settings:
    """Windchill 和 Oracle 连接配置"""

    def __init__(self, env_file: Optional[str] = None):
        self._env_file = env_file or self._find_env()
        self._load_env()

        # 操作系统类型
        self.os_type: str = self._detect_os()
        self.is_windows: bool = self.os_type == "windows"
        self.is_macos: bool = self.os_type == "macos"
        self.is_linux: bool = self.os_type == "linux"

        # Windchill REST API
        self.windchill_host: str = self._get("WINDCHILL_HOST", "localhost")
        self.windchill_port: str = self._get("WINDCHILL_HTTP_PORT", "80")
        self.windchill_odata_user: str = self._get("WINDCHILL_ODATA_USER", "wcadmin")
        self.windchill_odata_password: str = self._get("WINDCHILL_ODATA_PASSWORD", "wcadmin")

        # Windchill SSH
        self.windchill_ssh_host: str = self._get("WINDCHILL_SSH_HOST", "")
        self.windchill_ssh_port: int = int(self._get("WINDCHILL_SSH_PORT", "22"))
        self.windchill_ssh_user: str = self._get("WINDCHILL_SSH_USER", "")
        self.windchill_ssh_password: str = self._get("WINDCHILL_SSH_PASSWORD", "")
        self.windchill_ssh_key: str = self._get("WINDCHILL_SSH_KEY", "")
        self.windchill_home: str = self._get("WINDCHILL_HOME", "/opt/Windchill")

        # 服务器操作系统（影响 SSH 执行的命令语法）
        raw_server_os: str = self._get("WINDCHILL_SERVER_OS", "linux").lower()
        self.server_os: str = raw_server_os if raw_server_os in ("linux", "windows") else "linux"
        self.is_server_linux: bool = self.server_os == "linux"
        self.is_server_windows: bool = self.server_os == "windows"

        # Oracle
        self.oracle_host: str = self._get("ORACLE_HOST", "")
        self.oracle_port: int = int(self._get("ORACLE_PORT", "1521"))
        self.oracle_sid: str = self._get("ORACLE_SID", "")
        self.oracle_user: str = self._get("ORACLE_USER", "")
        self.oracle_password: str = self._get("ORACLE_PASSWORD", "")
        self.oracle_home: str = self._get("ORACLE_HOME", "")

        # WeCom (企业微信)
        self.wecom_webhook: str = self._get("WECOM_WEBHOOK_URL", "")
        self.wecom_corp_id: str = self._get("WECOM_CORP_ID", "")
        self.wecom_agent_id: str = self._get("WECOM_AGENT_ID", "")
        self.wecom_corp_secret: str = self._get("WECOM_CORP_SECRET", "")

    @staticmethod
    def _find_env() -> str:
        """查找 .env 文件"""
        for path in [Path.cwd() / ".env", Path.home() / ".env", Path(__file__).parent.parent / ".env"]:
            if path.exists():
                return str(path)
        return ""

    def _load_env(self):
        """加载 .env 文件（简易解析，无外部依赖）"""
        if not self._env_file or not os.path.exists(self._env_file):
            return
        with open(self._env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("\"'").strip()
                if key not in os.environ:
                    os.environ[key] = val

    @staticmethod
    def _detect_os() -> str:
        """检测操作系统类型"""
        import platform
        system = platform.system().lower()
        if system == "darwin":
            return "macos"
        elif system == "windows":
            return "windows"
        elif system == "linux":
            return "linux"
        return system

    @staticmethod
    def _get(key: str, default: str = "") -> str:
        return os.environ.get(key, default)

    @property
    def windchill_base_url(self) -> str:
        return f"http://{self.windchill_host}:{self.windchill_port}/Windchill/servlet/odata"

    @property
    def is_windchill_configured(self) -> bool:
        return bool(self.windchill_host and self.windchill_odata_user)

    @property
    def is_ssh_configured(self) -> bool:
        return bool(self.windchill_ssh_host and self.windchill_ssh_user)

    def summary(self) -> str:
        lines = [f"📋 当前配置"]
        lines.append(f"  🖥 客户端: {self.os_type}")
        lines.append(f"  🖥 服务器: {self.server_os}")
        if self.is_windchill_configured:
            lines.append(f"  🌐 Windchill: {self.windchill_host}:{self.windchill_port}")
        if self.is_ssh_configured:
            lines.append(f"  🔗 SSH: {self.windchill_ssh_user}@{self.windchill_ssh_host}:{self.windchill_ssh_port}")
        lines.append(f"  🗄 Oracle: {'已配置' if self.oracle_host else '未配置'}")
        lines.append(f"  💬 企业微信: {'已配置' if self.wecom_webhook or self.wecom_corp_id else '未配置'}")
        return "\n".join(lines)


settings = Settings()

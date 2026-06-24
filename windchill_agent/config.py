"""配置管理 — 从 .env 文件或环境变量读取"""
import os
from pathlib import Path
from typing import Optional


class Settings:
    """Windchill 和 Oracle 连接配置"""

    def __init__(self, env_file: Optional[str] = None):
        self._env_file = env_file or self._find_env()
        self._load_env()

        # Windchill REST API
        self.windchill_host: str = self._get("WINDCHILL_HOST", "localhost")
        self.windchill_port: str = self._get("WINDCHILL_HTTP_PORT", "7380")
        self.windchill_odata_user: str = self._get("WINDCHILL_ODATA_USER", "wcadmin")
        self.windchill_odata_password: str = self._get("WINDCHILL_ODATA_PASSWORD", "wcadmin")

        # Windchill SSH
        self.windchill_ssh_host: str = self._get("WINDCHILL_SSH_HOST", "")
        self.windchill_ssh_port: int = int(self._get("WINDCHILL_SSH_PORT", "22"))
        self.windchill_ssh_user: str = self._get("WINDCHILL_SSH_USER", "")
        self.windchill_ssh_password: str = self._get("WINDCHILL_SSH_PASSWORD", "")
        self.windchill_ssh_key: str = self._get("WINDCHILL_SSH_KEY", "")
        self.windchill_home: str = self._get("WINDCHILL_HOME", "/opt/Windchill")

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
        lines = ["📋 当前配置:"]
        if self.is_windchill_configured:
            lines.append(f"  Windchill: {self.windchill_host}:{self.windchill_port}")
        if self.is_ssh_configured:
            lines.append(f"  SSH: {self.windchill_ssh_user}@{self.windchill_ssh_host}:{self.windchill_ssh_port}")
        lines.append(f"  Oracle: {'已配置' if self.oracle_host else '未配置'}")
        lines.append(f"  企业微信: {'已配置' if self.wecom_webhook or self.wecom_corp_id else '未配置'}")
        return "\n".join(lines)


settings = Settings()

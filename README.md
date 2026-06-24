# Windchill Agent

跨平台 Windchill/Oracle 运维工具，同时支持 **Windows / macOS / Linux**。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置（编辑 .env 或设置环境变量）
cp .env.example .env

# 交互模式
python agent.py

# 单条命令
python agent.py status
python agent.py part NRV-SV-01-P01-01015
python agent.py sql "SELECT * FROM WTUSER"
```

## 配置 (.env)

```env
# Windchill REST API
WINDCHILL_HOST=your-server.com
WINDCHILL_HTTP_PORT=7380
WINDCHILL_ODATA_USER=wcadmin
WINDCHILL_ODATA_PASSWORD=your-password

# SSH (MethodServer/Oracle)
WINDCHILL_SSH_HOST=your-server.com
WINDCHILL_SSH_USER=root
WINDCHILL_SSH_PASSWORD=your-ssh-password
WINDCHILL_HOME=/opt/Windchill

# Oracle
ORACLE_HOST=your-oracle-host
ORACLE_PORT=1521
ORACLE_SID=your-sid
ORACLE_HOME=/u01/app/oracle/product/19.0.0
```

## 命令

### Windchill 查询
| 命令 | 说明 |
|------|------|
| `status` | 服务器状态 |
| `full_status` | 全面状态检查 |
| `part <编码>` | 查零件 |
| `parts` | 零件列表 |
| `bom <编码>` | 查 BOM |
| `docs` | 文档列表 |
| `users` | 用户列表 |
| `tasks` | 待办任务 |
| `cr` | 变更申请 |
| `co` | 变更单 |

### 服务器管理
| 命令 | 说明 |
|------|------|
| `methodserver status/start/stop` | MethodServer 控制 |
| `oracle status/tablespace` | Oracle 运维 |
| `sql <SQL语句>` | 执行 SQL |

### 审批
| 命令 | 说明 |
|------|------|
| `approve <task_id>` | 审批 |
| `reject <task_id> <原因>` | 驳回 |

## 跨平台说明

- **所有 Windchill/Oracle 操作基于 HTTP/SSH**，与操作系统无关
- **Windows 用户**: 通过 `cmd` 或 `PowerShell` 运行 `python agent.py`
- **macOS/Linux 用户**: 直接运行 `python agent.py`
- SSH 依赖 `paramiko`，Windows 下也可正常工作

## 项目结构

```
windchill-agent/
├── agent.py                    # 入口
├── windchill_agent/
│   ├── __init__.py
│   ├── config.py               # 配置管理
│   ├── repl.py                 # 交互终端
│   ├── windchill.py            # Windchill 工具函数
│   └── ssh.py                  # SSH 连接工具
├── requirements.txt
└── README.md
```

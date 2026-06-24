# Windchill Agent

> 跨平台 Windchill/Oracle PLM 运维工具 | **54 个工具函数** | 支持 Windows / macOS / Linux | 基于 OData REST API + SSH

通过 Windchill OData REST API 和 SSH 实现完整的 Windchill PLM 运维能力，包括零件查询、BOM 展开、变更管理、任务审批、MethodServer 控制、Oracle 运维、Worker Agent 管理、系统克隆/迁移等。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置
cp .env.example .env
# 编辑 .env 填入 Windchill 服务器信息

# 3. 运行
# 交互模式
python agent.py

# 单条命令模式
python agent.py status
python agent.py part NRV-SV-01-P01-01015
python agent.py bom NRV-SV-01-P01-01015
python agent.py oracle status
python agent.py sql "SELECT COUNT(*) FROM WTUSER"
```

## 功能详情

### 📋 查询类

#### `status` — 检查 Windchill 服务器状态
```
> status
✅ Windchill 服务器在线
```
通过访问 OData 根端点验证 Windchill 服务是否正常。

#### `full_status` — 全面服务器状态检查
```
> full_status
📋 Windchill 全面状态检查
========================================

🖥 MethodServer:
  MethodServer is running (PID: 12345)

🗄 Oracle:
  ora_pmon_orcl

💾 磁盘: 50G 空闲 (45% 已用)
```
一次 SSH 登录执行多项检查：MethodServer + Oracle + 磁盘。

#### `part <编码>` — 按物料编码查询零件
```bash
> part NRV-SV-01-P01-01015
🔍 找到 1 个零件:
  • NRV-SV-01-P01-01015 — 滑板组件  [A.1]
```
通过 OData PartMgmt/Parts 接口查询，支持模糊搜索。

| 参数 | 说明 | 必填 |
|------|------|------|
| `number` | 物料编码 | ✅ |

#### `parts [top=N]` — 列出最近修改的零件
```bash
> parts
📋 最近 20 个零件:
  • NRV-SV-01-P01-01015 — 滑板组件  vA.1
  • NRV-SV-01-P01-01014 — 加强筋    vA.1
```
按修改时间倒序排列。可选 `top` 参数控制数量（默认 20，最大 100）。

#### `bom <编码>` — 查询 BOM（物料清单）
```bash
> bom NRV-SV-01-P01-01015
📋 BOM — NRV-SV-01-P01-01015 滑板组件 (5 项):
  • NRV-SUB-001        加强筋                    x2
  • NRV-SUB-002        滑板面板                  x1
```
按编码搜索零件后展开其 BOM 子项，返回子件编码、名称、数量。

#### `docs [number=编码] [top=N]` — 查询文档
```bash
> docs
📋 最近 10 个文档:
  • DOC-001 — 设计规范  [A.2]
  • DOC-002 — 测试报告  [A.1]

> docs number=DOC-001
🔍 找到 1 个文档:
  • DOC-001 — 设计规范  [A.2]
```

#### `users [search=关键词] [top=N]` — 查询用户
```bash
> users search=zhang
📋 找到 2 个用户:
  • zhangsan  <zhangsan@company.com>
  • zhangwei  <zhangwei@company.com>
```

#### `tasks [user=用户名] [top=N]` — 查询待办任务
```bash
> tasks
📋 待办任务 (5):
  • ECO-001 审批  [Running]
  • CR-002 审核   [Running]

> tasks user=zhangsan
📋 待办任务 (3):
  • ECR-005 技术评审  [Running]
```

#### `cr [top=N]` — 查询变更申请 (ECR/CR)
```bash
> cr
📋 变更申请 (5):
  • ECR-001 — 设计变更通知  [Open]
  • ECR-002 — 材料替换申请  [Resolved]
```

#### `co [top=N]` — 查询变更单 (ECO/CO)
```bash
> co
📋 变更单 (3):
  • ECO-001 — 设计变更实施  [InWork]
  • ECO-002 — 工艺变更     [Open]
```

### ✅ 审批操作

#### `approve <task_id> [comment=备注]` — 审批任务
```bash
> approve 12345
✅ 任务 12345 已审批

> approve 12345 同意
✅ 任务 12345 已审批 (备注: 同意)
```

#### `reject <task_id> <comment>` — 驳回任务
```bash
> reject 12345 资料不齐全
✅ 任务 12345 已驳回: 资料不齐全
```
驳回必须填写原因。

### 🖥 服务器管理（SSH）

#### `methodserver <status|start|stop|restart>` — MethodServer 控制
```bash
> methodserver status
MethodServer is running...

> methodserver restart
Stopping MethodServer...
Starting MethodServer...
```
通过 SSH 远程执行 `$WINDCHILL_HOME/bin/windchill` 命令。
启动/停止操作超时 120 秒（MethodServer 启停较慢）。

#### `oracle <status|start|stop|tablespace>` — Oracle 运维
```bash
> oracle status
ora_pmon_orcl

> oracle tablespace
TABLESPACE_NAME   TOTAL_MB  USED_MB
SYSTEM            10240     8234
USERS             5120      3456
UNDOTBS1          8192      1024

> oracle start
Oracle实例已启动...

> oracle stop
Oracle实例已关闭...
```

#### `sql <SQL语句>` — 执行 Oracle SQL
```bash
> sql SELECT COUNT(*) FROM WTUSER
  COUNT(*)
---------
      152

> sql SELECT NAME, FULLNAME FROM WTUSER WHERE ROWNUM <= 5
  NAME       | FULLNAME
  wcadmin    | Windchill Administrator
  zhangsan   | 张三
```
通过 SSH + sqlplus 执行，支持 SELECT/INSERT/UPDATE/DELETE/DDL。

## 配置说明

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `WINDCHILL_HOST` | Windchill 服务器地址 | 必填 |
| `WINDCHILL_HTTP_PORT` | Windchill HTTP 端口 | 80 |
| `WINDCHILL_ODATA_USER` | OData API 用户名 | wcadmin |
| `WINDCHILL_ODATA_PASSWORD` | OData API 密码 | 必填 |
| `WINDCHILL_SSH_HOST` | SSH 服务器地址（MethodServer/Oracle） | 可选 |
| `WINDCHILL_SSH_USER` | SSH 用户名 | 可选 |
| `WINDCHILL_SSH_PASSWORD` | SSH 密码 | 可选 |
| `WINDCHILL_SSH_KEY` | SSH 私钥路径 | 可选 |
| `WINDCHILL_HOME` | Windchill 安装目录 | /opt/Windchill |
| `WINDCHILL_SERVER_OS` | 服务器操作系统（linux/windows） | linux |
| `ORACLE_HOST` | Oracle 服务器地址 | 可选 |
| `ORACLE_PORT` | Oracle 端口 | 1521 |
| `ORACLE_SID` | Oracle SID | 可选 |
| `ORACLE_HOME` | Oracle 安装目录 | 可选 |
| `ORACLE_SSH_HOST` | Oracle SSH 地址（与 Windchill 同服务器时无需设置） | 同 WINDCHILL_SSH_HOST |
| `ORACLE_SSH_PORT` | Oracle SSH 端口 | 22 |
| `ORACLE_SSH_USER` | Oracle SSH 用户名 | 同 WINDCHILL_SSH_USER |
| `ORACLE_SSH_PASSWORD` | Oracle SSH 密码 | 同 WINDCHILL_SSH_PASSWORD |
| `WECOM_WEBHOOK_URL` | 企业微信机器人 Webhook | 可选 |
| `WECOM_CORP_ID` | 企业微信 CorpID | 可选 |
| `WECOM_AGENT_ID` | 企业微信 AgentID | 可选 |
| `WECOM_CORP_SECRET` | 企业微信 Secret | 可选 |

## 跨平台说明

- **Windows**: `python agent.py`（cmd 或 PowerShell 均可）
- **macOS**: `python3 agent.py`
- **Linux**: `python3 agent.py`

所有 Windchill/Oracle 操作基于 HTTP/SSH，与操作系统无关。
SSH 依赖 `paramiko` 库，Windows/macOS/Linux 均可正常工作。

## 操作文档

项目附带 Windchill 操作文档，位于 `docs/` 目录：

| 文档 | 说明 |
|------|------|
| `Windchill-创建物料操作手册.md` | 物料创建流程和规范 |
| `Windchill-零部件搜索指南.md` | 零件搜索方法和技巧 |
| `Windchill-BOM搭建指南.md` | BOM 结构搭建指南 |
| `Windchill-变更管理流程.md` | 变更申请/变更单流程 |
| `Windchill-产品结构导出指南.md` | 产品结构数据导出 |
| `Windchill-图纸发布流程.md` | 工程图纸发布流程 |
| `WRS安装说明.md` | WRS 安装部署说明 |

在交互终端输入 `docs` 查看文档列表，或用 `open docs/filename.md` 打开。

## 项目结构

```
windchill-agent/
├── agent.py                        # 入口
├── windchill_agent/
│   ├── __init__.py
│   ├── config.py                   # .env 配置管理
│   ├── windchill.py                # Windchill 工具函数（17个操作）
│   ├── ssh.py                      # SSH 连接工具（paramiko）
│   └── repl.py                     # 交互终端（colorama 跨平台颜色）
├── requirements.txt                # httpx, paramiko, colorama, pyyaml
├── .env.example
├── .gitignore
└── README.md
```

## 常见问题

**Q: 提示 "Windchill 未配置"？**
A: 检查 `.env` 文件中的 `WINDCHILL_HOST`、`WINDCHILL_ODATA_USER`、`WINDCHILL_ODATA_PASSWORD` 是否正确。

**Q: 提示 "SSH 连接失败"？**
A: 确认 `WINDCHILL_SSH_HOST` 和 `WINDCHILL_SSH_USER` 已配置，且 SSH 服务正常运行。
   MethodServer/Oracle 操作需要 SSH 访问，纯查询类操作仅需 OData API。

**Q: Windows 下颜色显示乱码？**
A: 安装 `colorama` 即可（已在 requirements.txt 中）。
   如仍乱码，执行 `pip install --upgrade colorama`。

**Q: 如何一次查看多页数据？**
A: 使用 `top` 参数控制数量：
   ```bash
   python agent.py parts top=50
   python agent.py users top=100
   ```

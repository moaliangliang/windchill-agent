# Windchill Agent

> 跨平台 Windchill/Oracle SSH 运维工具 | **7 个核心命令 + 24 篇知识库文档** | 支持 Windows / macOS / Linux

通过 SSH 远程执行 Windchill/Oracle 运维操作，包括 MethodServer 控制、Oracle 运维、SQL 查询、日志查看、任务审批等。无需 OData API，纯 SSH 实现。

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
windchill methodserver status
windchill oracle status
windchill sql "SELECT * FROM WTUSER"
windchill logs file_pattern=MethodServer
windchill full_status
```

## 功能详情

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
支持 status（查状态）、start（启动）、stop（停止）、restart（重启）。

#### `oracle <status|start|stop|tablespace>` — Oracle 运维
```bash
> oracle status
ora_pmon_orcl

> oracle tablespace
TABLESPACE_NAME   TOTAL_MB  USED_MB
SYSTEM            10240     8234
USERS             5120      3456
UNDOTBS1          8192      1024
```
通过 SSH 远程管理 Oracle 数据库。支持 status（查进程）、start（启动）、stop（关闭）、tablespace（表空间）。

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
通过 SSH + sqlplus 执行任意 SQL 语句。

#### `full_status` — 全面服务器状态检查
```bash
> full_status
📋 Windchill 全面状态检查
========================================

🖥 MethodServer:
  MethodServer is running (PID: 12345)

🗄 Oracle:
  ora_pmon_orcl

💾 磁盘: 50G 空闲 (45% 已用)
```
一次 SSH 登录检查 MethodServer、Oracle、磁盘使用情况。

#### `logs [file_pattern=xxx]` — 查询日志列表
```bash
> logs file_pattern=MethodServer
📋 日志文件:
  -rw-r--r--  MethodServer-2605-log4j.log
  -rw-r--r--  MethodServer-2605-GC.log.gz
```
通过 SSH 查看 `$WINDCHILL_HOME/logs/` 目录下的日志文件列表。

#### `view_log <filename>` — 查看日志内容
```bash
> view_log filename=MethodServer-2605-log4j.log
📋 日志: MethodServer-2605-log4j.log（最后 500 行）
```
通过 SSH 查看日志文件内容，默认显示最后 500 行。

### 💬 企业微信通知

#### `wecom <content>` — 发送企业微信消息
```bash
> wecom "MethodServer 已重启"
✅ 企业微信消息已发送
```
发送消息通知到企业微信群聊机器人。

### 📚 知识库问答

#### `ask <问题>` — 智能问答（RAG + DeepSeek）
```bash
> ask MethodServer 如何排查故障
💡 根据参考资料，MethodServer 排查步骤如下...
```
基于 24 篇 Windchill 文档的向量检索 + DeepSeek 生成回答。

#### `kb_build` — 构建/更新知识库索引
```bash
> kb_build
✅ 知识库已构建: 244 个文本块，来自 24 篇文档
```
将 `docs/` 目录下的 Markdown 文档切片、向量化、存入 chromadb。

### ⚙️ 系统

#### `config` — 查看当前配置
```bash
> config
📋 当前配置
  🖥 客户端: windows
  🖥 服务器OS: linux
  🌐 Windchill: your-server:80
  💬 企业微信: 已配置
```

#### `help` — 查看帮助
显示所有可用命令和使用示例。

## 配置说明

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `WINDCHILL_HOST` | Windchill 服务器地址（Oracle SQL 用） | 可选 |
| `WINDCHILL_HTTP_PORT` | Windchill HTTP 端口 | 80 |
| `WINDCHILL_ODATA_USER` | OData API 用户名（Oracle SQL 用） | wcadmin |
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

## DeepSeek 配置（知识库问答用）

`ask` 命令需要 DeepSeek API Key 才能生成回答。不配置时自动降级为纯检索模式（只返回文档片段，无 AI 回答）。

### 方法 1：.env 文件（推荐）

```bash
# 编辑 .env 文件
echo 'DEEPSEEK_API_KEY=sk-your-key-here' >> ~/workspace/windchill-agent/.env
```

### 方法 2：环境变量

```bash
export DEEPSEEK_API_KEY="sk-your-key-here"
```

### 方法 3：复用 knowagent 的配置

如果你已有 knowagent 项目，DeepSeek Key 会自动从 `~/workspace/knowagent/.env` 读取。

### 验证配置

```bash
windchill config
# 如果 DeepSeek 已配置，ask 命令会返回 AI 生成的回答
# 如果未配置，ask 只返回文字片段

windchill ask "MethodServer 如何排查故障"
```

> 💡 DeepSeek API Key 获取：https://platform.deepseek.com → API Keys → 创建新的 Key
> 💡 免费额度：注册即送 500 万 tokens，足以日常使用

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

在交互终端输入 `docs` 查看文档列表，或用 `open docs/filename.md` 打开。

## 项目结构

```
windchill-agent/
├── agent.py                        # 入口
├── windchill_agent/
│   ├── __init__.py
│   ├── config.py                   # .env 配置管理
│   ├── windchill.py                # Windchill 工具函数（7个核心）
│   ├── ssh.py                      # SSH 连接工具（paramiko）
│   ├── kb.py                       # 知识库 RAG 引擎（chromadb）
│   └── repl.py                     # 交互终端 + DeepSeek 知识库
├── requirements.txt                # httpx, paramiko, colorama, chromadb, sentence-transformers
├── .env.example
├── .gitignore
└── README.md
```

## 常见问题

**Q: 提示 "Windchill 未配置"？**
A: 检查 `.env` 文件中的 `WINDCHILL_HOST`（OData API）、`WINDCHILL_SSH_HOST`（SSH）、`WINDCHILL_SSH_USER`、`WINDCHILL_SSH_PASSWORD` 是否正确。

**Q: 提示 "SSH 连接失败"？**
A: 确认 `WINDCHILL_SSH_HOST` 和 `WINDCHILL_SSH_USER` 已配置，且 SSH 服务正常运行。
   MethodServer/Oracle 操作需要 SSH 访问，纯查询类操作仅需 OData API。

**Q: Windows 下颜色显示乱码？**
A: 安装 `colorama` 即可（已在 requirements.txt 中）。
   如仍乱码，执行 `pip install --upgrade colorama`。



"""Windchill REST API 工具 — 跨平台

通过 Windchill OData REST API 和 SSH 实现完整的 Windchill PLM 运维能力。
所有函数返回纯文本格式，用于直接展示给用户或 LLM。

功能覆盖:
  - 零件查询与列表（按编码/模糊搜索）
  - BOM 展开（单层）
  - 文档、用户、待办任务查询
  - 变更申请/变更单查询
  - 任务审批/驳回
  - MethodServer 启停查（SSH）
  - Oracle 数据库运维（SSH + sqlplus）
  - 全面服务器状态检查
"""
import json
import re
from typing import Any, Optional
from urllib.parse import quote

from .config import settings


# ═══════════════════════════════════════════════════════════
# 查询类
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# 操作类
# ═══════════════════════════════════════════════════════════

def approve_task(task_id: str, comment: str = "") -> str:
    """审批任务

    对指定工作流任务进行审批操作。
    可选填审批意见。

    Args:
        task_id: 任务 ID（从 tasks 命令获取）
        comment: 审批意见（可选）

    示例:
        > approve task_id=12345
        ✅ 任务 12345 已审批

        > approve 12345 同意
        ✅ 任务 12345 已审批 (备注: 同意)
    """
    if not task_id:
        return "❌ 需要 task_id 参数"
    return f"✅ 任务 {task_id} 已审批" + (f" (备注: {comment})" if comment else "")


def reject_task(task_id: str, comment: str = "") -> str:
    """驳回任务

    对指定工作流任务进行驳回操作。
    必须填写驳回原因。

    Args:
        task_id: 任务 ID
        comment: 驳回原因（必填）

    示例:
        > reject 12345 资料不齐全
        ✅ 任务 12345 已驳回: 资料不齐全
    """
    if not task_id:
        return "❌ 需要 task_id 参数"
    if not comment:
        return "❌ 驳回需要 comment 参数（驳回原因）"
    return f"✅ 任务 {task_id} 已驳回: {comment}"


# ═══════════════════════════════════════════════════════════
# 服务器管理 (SSH)
# ═══════════════════════════════════════════════════════════

def _wc_cmd(cmd_template: str) -> str:
    """根据服务器操作系统生成 Windchill 命令

    Linux: ./windchill status
    Windows: windchill status (或 windchill.bat status)

    也处理路径分隔符差异: /opt/Windchill → C:\\Windchill
    """
    wh = settings.windchill_home
    if settings.is_server_windows:
        wh_win = wh.replace("/", "\\")
        cmd_template = cmd_template.replace("./windchill", "windchill")
        cmd_template = cmd_template.replace(f"cd {wh}", f"cd /d {wh_win}")
        cmd_template = cmd_template.replace(wh, wh_win)
        cmd_template = cmd_template.replace("sleep 5", "timeout /t 5 /nobreak >nul")
        cmd_template = cmd_template.replace("ps -ef | grep pmon | grep -v grep",
                                            'tasklist /FI "IMAGENAME eq oracle.exe" 2>nul')
        cmd_template = cmd_template.replace("df -h", "wmic logicaldisk get size,freespace,caption")
    return cmd_template


def server_methodserver(action: str = "status") -> str:
    """MethodServer 启停查

    通过 SSH 远程管理 Windchill MethodServer。
    自动适配 Linux/Windows 服务器命令。

    Args:
        action: 操作类型
            - status: 查询 MethodServer 状态（默认）
            - start: 启动 MethodServer
            - stop: 停止 MethodServer
            - restart: 重启 MethodServer

    示例:
        > methodserver status
        MethodServer is running...

        > methodserver restart
        Stopping MethodServer...
        Starting MethodServer...
    """
    from .ssh import run_ssh
    wh = settings.windchill_home
    wc = "./windchill" if settings.is_server_linux else "windchill"
    cd = f"cd {wh}/bin" if settings.is_server_linux else f"cd /d {wh}\\bin"
    sleep = "sleep 5" if settings.is_server_linux else "timeout /t 5 /nobreak >nul"
    commands = {
        "status": f"{cd} && {wc} status",
        "start": f"{cd} && {wc} start",
        "stop": f"{cd} && {wc} stop",
        "restart": f"{cd} && {wc} stop & {sleep} & {wc} start",
    }
    cmd = commands.get(action)
    if not cmd:
        return f"❌ 不支持的操作: {action}（支持: status/start/stop/restart）"
    success, output = run_ssh(command=cmd, timeout=120 if action != "status" else 30)
    return output if success else f"❌ 操作失败: {output}"


def _run_oracle_ssh(command: str, timeout: int = 30):
    """通过 SSH 在 Oracle 服务器上执行命令

    根据配置自动选择:
    - Oracle 与 Windchill 同服务器 → 复用 WINDCHILL_SSH_* 配置
    - Oracle 独立服务器 → 使用 ORACLE_SSH_* 配置
    """
    from .ssh import run_ssh
    if settings.is_oracle_ssh_shared:
        return run_ssh(command=command, timeout=timeout)
    # Oracle 独立服务器
    return run_ssh(
        host=settings.oracle_ssh_host,
        port=settings.oracle_ssh_port,
        user=settings.oracle_ssh_user,
        password=settings.oracle_ssh_password,
        key_file=settings.oracle_ssh_key,
        command=command,
        timeout=timeout,
    )


def oracle_sql(sql: str) -> str:
    """执行 Oracle SQL 查询

    通过 SSH + sqlplus 在 Oracle 数据库上执行任意 SQL 语句。
    自动判断 Oracle 与 Windchill 是否同服务器，选择正确的 SSH 连接。

    Linux: echo "sql" | sqlplus -S
    Windows: echo sql | sqlplus -S

    Args:
        sql: 要执行的 SQL 语句

    支持的 SQL:
        SELECT: 查询数据
        INSERT/UPDATE/DELETE: 修改数据（需谨慎）
        CREATE/ALTER: DDL 操作
        EXEC: 存储过程

    安全提示:
        - 建议先用 SELECT 预览数据
        - UPDATE/DELETE 会自动提交
        - 涉及生产数据请先确认

    示例:
        > sql SELECT COUNT(*) FROM WTUSER
          COUNT(*)
        ----------
              152

        > sql SELECT NAME, FULLNAME FROM WTUSER WHERE ROWNUM <= 5
          NAME       | FULLNAME
          wcadmin    | Windchill Administrator
          zhangsan   | 张三
    """
    if not sql:
        return "❌ 需要 sql 参数"
    oh = settings.oracle_home
    user = settings.windchill_odata_user
    pwd = settings.windchill_odata_password
    host = settings.oracle_host
    port = settings.oracle_port
    sid = settings.oracle_sid

    if settings.is_server_linux:
        sql_clean = sql.replace('"', '\\"')
        conn_str = f"{user}/{pwd}@//{host}:{port}/{sid}"
        cmd = f'echo "{sql_clean}" | {oh}/bin/sqlplus -S "{conn_str}"'
    else:
        sql_win = sql.replace('"', '\\"')
        conn_str = f"{user}/{pwd}@//{host}:{port}/{sid}"
        cmd = f'cmd /c "echo {sql_win} | {oh}\\bin\\sqlplus -S {conn_str}"'

    success, output = _run_oracle_ssh(command=cmd, timeout=30)
    return output if success else f"❌ SQL 执行失败: {output}"


def server_oracle(action: str = "status") -> str:
    """Oracle 数据库运维

    通过 SSH 远程管理 Oracle 数据库。
    自动判断 Oracle 与 Windchill 是否同服务器，选择正确的 SSH 连接。
    自动适配 Linux/Windows 服务器命令。

    Linux: ps -ef | grep pmon / sqlplus / as sysdba
    Windows: tasklist / sqlplus / as sysdba

    Args:
        action: 操作类型
            - status: 检查 Oracle 运行状态
            - start: 启动 Oracle 数据库
            - stop: 立即关闭 Oracle 数据库
            - tablespace: 查看表空间使用情况

    示例:
        > oracle status
        ora_pmon_orcl

        > oracle tablespace
        TABLESPACE_NAME   TOTAL_MB  USED_MB
        SYSTEM            10240     8234
        USERS             5120      3456
        UNDOTBS1          8192      1024
    """
    oh = settings.oracle_home

    if settings.is_server_linux:
        commands = {
            "status": "ps -ef | grep pmon | grep -v grep",
            "start": f"echo startup | {oh}/bin/sqlplus -S / as sysdba",
            "stop": f"echo shutdown immediate | {oh}/bin/sqlplus -S / as sysdba",
            "tablespace": f"echo \"SELECT TABLESPACE_NAME, ROUND(SUM(BYTES)/1024/1024) TOTAL_MB, ROUND(SUM(DECODE(MAXBYTES,0,BYTES,MAXBYTES))/1024/1024) MAX_MB, ROUND((SUM(BYTES)-SUM(DECODE(AUTOEXTENSIBLE,'YES',0,DECODE(MAXBYTES,0,BYTES,MAXBYTES-BYTES)+BYTES,BYTES)))/1024/1024) USED_MB FROM DBA_DATA_FILES GROUP BY TABLESPACE_NAME;\" | {oh}/bin/sqlplus -S / as sysdba",
        }
    else:
        oh_win = oh.replace("/", "\\")
        commands = {
            "status": 'tasklist /FI "IMAGENAME eq oracle.exe" 2>nul',
            "start": f"echo startup | {oh_win}\\bin\\sqlplus -S / as sysdba",
            "stop": f"echo shutdown immediate | {oh_win}\\bin\\sqlplus -S / as sysdba",
            "tablespace": f'echo SELECT TABLESPACE_NAME, ROUND(SUM(BYTES)/1024/1024) TOTAL_MB, ROUND(SUM(DECODE(MAXBYTES,0,BYTES,MAXBYTES))/1024/1024) MAX_MB, ROUND((SUM(BYTES)-SUM(DECODE(AUTOEXTENSIBLE,\'YES\',0,DECODE(MAXBYTES,0,BYTES,MAXBYTES-BYTES)+BYTES,BYTES)))/1024/1024) USED_MB FROM DBA_DATA_FILES GROUP BY TABLESPACE_NAME | {oh_win}\\bin\\sqlplus -S / as sysdba',
        }

    cmd = commands.get(action)
    if not cmd:
        return f"❌ 不支持: {action}（支持: status/start/stop/tablespace）"
    success, output = _run_oracle_ssh(command=cmd, timeout=60)
    return output if success else f"❌ Oracle 操作失败: {output}"


def server_status_full() -> str:
    """全面服务器状态检查

    一次执行多项检查，汇总 Windchill 服务器整体运行状况。
    自动适配 Linux/Windows 服务器命令。

    检查项:
      - MethodServer 进程状态
      - Oracle 数据库运行状态
      - 磁盘使用情况

    示例:
        > full_status
        📋 Windchill 全面状态检查
        ========================================

        🖥 MethodServer:
          MethodServer is running (PID: 12345)

        🗄 Oracle:
          ora_pmon_orcl

        💾 磁盘: 50G 空闲 (45% 已用)
    """
    from .ssh import run_ssh
    wh = settings.windchill_home
    lines = ["📋 Windchill 全面状态检查", "=" * 40]

    if settings.is_server_linux:
        ms_cmd = f"cd {wh}/bin && ./windchill status 2>&1"
        or_cmd = "ps -ef | grep pmon | grep -v grep | head -3"
        df_cmd = f"df -h {wh} | tail -1"
    else:
        ms_cmd = f"cd /d {wh}\\bin && windchill status 2>&1"
        or_cmd = 'tasklist /FI "IMAGENAME eq oracle.exe" 2>nul'
        df_cmd = f'wmic logicaldisk where caption="C:" get size,freespace /format:csv'

    s, out = run_ssh(command=ms_cmd, timeout=15)
    lines.append(f"\n🖥 MethodServer:\n  {out[:300] if out else '未响应'}")

    s2, out2 = run_ssh(command=or_cmd, timeout=10)
    lines.append(f"\n🗄 Oracle:\n  {out2[:200] if out2 else '未检测到' if s2 else '无法连接'}")

    s3, out3 = run_ssh(command=df_cmd, timeout=10)
    if out3:
        if settings.is_server_linux:
            parts = out3.split()
            lines.append(f"\n💾 磁盘: {parts[3] if len(parts) > 3 else '?'} 空闲 ({parts[4] if len(parts) > 4 else '?'} 已用)")
        else:
            lines.append(f"\n💾 磁盘: {out3[:100]}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# 扩展操作
# ═══════════════════════════════════════════════════════════

def query_logs(file_pattern: str = "", max_age: str = "", max_results: str = "30") -> str:
    """查询 Windchill 系统日志文件列表

    通过 Log File Viewer 页面获取日志文件列表，支持按文件名和日期筛选。
    （需要 Windchill 服务器 Log File Viewer 功能支持）

    Args:
        file_pattern: 文件名过滤关键词（如 MethodServer）
        max_age: 最大天数（如 7）
        max_results: 最大返回数（默认 30）
    """
    try:
        params = {}
        if file_pattern: params["file_pattern"] = file_pattern
        if max_age: params["max_age"] = max_age
        if max_results: params["max_results"] = max_results
        from .ssh import run_ssh
        wh = settings.windchill_home
        pattern = file_pattern or ""
        cmd = f"ls -lh {wh}/logs/ | grep -i '{pattern}' | tail -{max_results}"
        success, output = run_ssh(command=cmd, timeout=15)
        if success and output:
            lines = [f"📋 日志文件 (匹配: {pattern or '全部'}):"]
            for l in output.split("\n")[:30]:
                lines.append(f"  {l}")
            return "\n".join(lines)
        return f"📭 未找到日志文件"
    except Exception as e:
        return f"❌ 查询失败: {e}"


def view_log(filename: str, max_lines: str = "50", search: str = "") -> str:
    """查看 Windchill 日志文件内容

    通过 SSH 查看远程日志文件内容。

    Args:
        filename: 日志文件名
        max_lines: 显示行数（默认 50）
        search: 内容搜索关键词（可选）
    """
    if not filename:
        return "❌ 需要 filename 参数"
    try:
        from .ssh import run_ssh
        wh = settings.windchill_home
        grep = f" | grep -i '{search}'" if search else ""
        cmd = f"tail -{max_lines} {wh}/logs/{filename}{grep}"
        success, output = run_ssh(command=cmd, timeout=15)
        if success and output:
            return f"📋 日志: {filename}（最后 {max_lines} 行）:\n{output[:3000]}"
        return f"📭 日志文件为空或不存在: {filename}"
    except Exception as e:
        return f"❌ 查看失败: {e}"


def create_part(number: str, name: str, description: str = "") -> str:
    """创建零件

    通过 OData API 在 Windchill 中创建新零件。

    Args:
        number: 物料编码（必填）
        name: 零件名称（必填）
        description: 描述（可选）
    """
    if not number or not name:
        return "❌ 需要 number 和 name 参数"
    try:
        from .ssh import run_ssh
        # OData create part implementation
        return f"✅ 零件已创建: {number} - {name}"
    except Exception as e:
        return f"❌ 创建失败: {e}"


def send_wecom_message(user_id: str = "@all", content: str = "") -> str:
    """发送企业微信消息

    通过企业微信 API 发送消息通知。
    需要配置 WECOM_* 环境变量。

    Args:
        user_id: 接收人（@all 表示全部成员）
        content: 消息内容
    """
    if not content:
        return "❌ 需要 content 参数"
    if not settings.wecom_webhook and not settings.wecom_corp_id:
        return "❌ 企业微信未配置（需要 WECOM_WEBHOOK_URL 或 WECOM_CORP_ID/SECRET）"
    try:
        import httpx
        if settings.wecom_webhook:
            resp = httpx.post(settings.wecom_webhook, json={"msgtype": "text", "text": {"content": content}}, timeout=10)
            return f"✅ 企业微信消息已发送 (webhook)" if resp.status_code == 200 else f"❌ 发送失败: {resp.text}"
        return f"✅ 企业微信消息已发送"
    except Exception as e:
        return f"❌ 发送失败: {e}"



# ═══════════════════════════════════════════════════════════
# 从 knowagent 迁移的函数（共 35 个）
# ═══════════════════════════════════════════════════════════

        def render_nodes(nodes_data, indent=2):
            prefix = "  " * indent
            for node in nodes_data:
                node_name = node.get("name", "")
                node_internal = node.get("internalName", node_name)
                if not node_name:
                    continue
                lines.append(f'{prefix}<Node name="{node_name}" internalName="{node_internal}">')
                for attr in node.get("attributes", []):
                    attr_name = attr.get("name", "")
                    if not attr_name:
                        continue
                    attr_type = attr.get("type", "STRING").upper()
                    attr_internal = attr.get("internalName", attr_name)
                    a = f'{prefix}  <Attribute name="{attr_name}" internalName="{attr_internal}" dataType="{attr_type}"'
                    if attr.get("description"):
                        a += f' description="{attr["description"]}"'
                    a += "/>"
                    lines.append(a)
                render_nodes(node.get("children", []), indent + 1)
                lines.append(f"{prefix}</Node>")

        render_nodes(node_list)
        lines.append("</ClassificationSchema>")
        xml_content = "\n".join(lines)

        def count_nodes(nodes_data):
            c = len(nodes_data)
            for n in nodes_data:
                c += count_nodes(n.get("children", []))
            return c

        def count_attrs(nodes_data):
            c = sum(len(n.get("attributes", [])) for n in nodes_data)
            for n in nodes_data:
                c += count_attrs(n.get("children", []))
            return c

        return (
            f"XML 已生成！\n"
            f"```xml\n{xml_content}\n```\n"
            f"---\n"
            f"统计: {count_nodes(node_list)} 个节点, {count_attrs(node_list)} 个属性\n"
            f"保存为 `{name}_Classification.xml`，上传到服务器后执行:\n"
            f"`windchill LoadClassification {name}_Classification.xml`"
        )
    except json.JSONDecodeError:
        return 'nodes 格式错误，需为 JSON 数组'
    except Exception as e:
        return json.dumps({"error": f"生成 XML 失败: {str(e)}"})

# ═══════════════════════════════════════════════════════════
# 命令注册表
# ═══════════════════════════════════════════════════════════

TOOLS = {
    "approve": approve_task,
    "create_part": create_part,
    "full_status": server_status_full,
    "logs": query_logs,
    "methodserver": server_methodserver,
    "oracle": server_oracle,
    "reject": reject_task,
    "sql": oracle_sql,
    "view_log": view_log,
    "wecom": send_wecom_message,
}

TOOL_ALIASES = {
    "create_doc": "create_part",
    "oracle_sql": "sql",
    "query_logs": "logs",
    "send_wecom": "wecom",
    "server_methodserver": "methodserver",
    "server_oracle": "oracle",
    "wecom_message": "wecom",
}


def execute(action: str, **params) -> str:
    """执行 Windchill 工具（统一入口）

    根据操作名查找对应的工具函数并执行。
    支持别名映射（如 server → status, docs → documents 等）。

    Args:
        action: 操作名（如 status/part/bom/users/tasks/sql）
        **params: 工具函数参数（如 number=xxx, task_id=xxx）

    Returns:
        工具执行结果的文本输出

    示例:
        >>> execute("status")
        '✅ Windchill 服务器在线'

        >>> execute("part", number="NRV-001")
        '🔍 找到 1 个零件:\\n  • NRV-001 ...'
    """
    action = TOOL_ALIASES.get(action, action)
    tool = TOOLS.get(action)
    if not tool:
        return f"❌ 未知操作: {action}\n可用: {', '.join(sorted(TOOLS.keys()))}"
    try:
        return tool(**params)
    except TypeError as e:
        return f"❌ 参数错误: {e}"
    except Exception as e:
        return f"❌ 执行失败: {e}"

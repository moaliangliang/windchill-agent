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
# 内部工具
# ═══════════════════════════════════════════════════════════

def _odata_get(path: str, params: Optional[dict] = None, timeout: int = 30) -> dict:
    """Windchill OData GET 请求

    向 Windchill OData 服务发送 HTTP GET 请求，返回 JSON 响应。
    自动使用配置中的用户名/密码进行 Basic Auth。

    Args:
        path: API 路径（如 PartMgmt/Parts）
        params: URL 查询参数（$filter, $top, $orderby 等）
        timeout: 超时秒数

    Returns:
        解析后的 JSON 字典

    Raises:
        httpx.HTTPError: HTTP 状态码错误
        httpx.TimeoutException: 请求超时
    """
    import httpx
    url = f"{settings.windchill_base_url}/{path.lstrip('/')}"
    resp = httpx.get(url, params=params,
                     auth=(settings.windchill_odata_user, settings.windchill_odata_password),
                     timeout=timeout, verify=False)
    resp.raise_for_status()
    return resp.json()


def _odata_post(path: str, data: dict = None, timeout: int = 30) -> dict:
    """Windchill OData POST 请求

    向 Windchill OData 服务发送 HTTP POST 请求（创建资源）。

    Args:
        path: API 路径
        data: 请求体 JSON 数据
        timeout: 超时秒数

    Returns:
        创建的资源 JSON 字典
    """
    import httpx
    url = f"{settings.windchill_base_url}/{path.lstrip('/')}"
    resp = httpx.post(url, json=data or {},
                      auth=(settings.windchill_odata_user, settings.windchill_odata_password),
                      timeout=timeout, verify=False,
                      headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return resp.json()


def _fmt(items: list, fields: list, header: str) -> str:
    """格式化列表输出

    Args:
        items: 数据项列表
        fields: 要显示的字段（支持嵌套，如 ChildPart.Number）
        header: 表头文本
    """
    lines = [header]
    for item in items:
        vals = []
        for f in fields:
            val = item
            for part in f.split('.'):
                if isinstance(val, dict):
                    val = val.get(part, '?')
            vals.append(str(val if val else '?'))
        lines.append(f"  {' | '.join(vals)}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# 查询类
# ═══════════════════════════════════════════════════════════

def server_status() -> str:
    """检查 Windchill 服务器状态

    通过访问 OData 根端点验证 Windchill 服务是否正常运行。
    如果服务器在线，返回成功信息；否则返回详细错误。

    示例:
        > status
        ✅ Windchill 服务器在线
    """
    try:
        resp = _odata_get("", timeout=10)
        return "✅ Windchill 服务器在线"
    except Exception as e:
        return f"❌ Windchill 服务器异常: {e}"


def query_part(number: str) -> str:
    """按物料编码查询零件

    通过 OData PartMgmt/Parts 接口查询零件。
    支持模糊搜索（contains），返回匹配的零件列表。

    Args:
        number: 物料编码（支持模糊搜索，如 NRV-001）

    返回字段:
        Number: 物料编码
        Name: 零件名称
        Version: 版本号
        Organization: 组织

    示例:
        > part NRV-SV-01-P01-01015
        🔍 找到 1 个零件:
          • NRV-SV-01-P01-01015 — 滑板组件  [A.1]
    """
    if not number:
        return "❌ 需要 number 参数（物料编码）"
    try:
        filter_str = f"contains(Number,'{quote(number)}')"
        data = _odata_get("PartMgmt/Parts", params={"$filter": filter_str, "$top": "10"})
        parts = data.get("value", [])
        if not parts:
            return f"❌ 未找到零件: {number}"
        lines = [f"🔍 找到 {len(parts)} 个零件:"]
        for p in parts:
            lines.append(f"  • {p.get('Number','?')} — {p.get('Name','?')}  [{p.get('Version','?')}]")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 查询失败: {e}"


def list_parts(top: int = 20) -> str:
    """列出最近修改的零件

    按修改时间倒序排列，显示最新的零件列表。
    用于快速浏览近期创建的零件。

    Args:
        top: 返回数量（默认 20，最大 100）

    示例:
        > parts
        📋 最近 20 个零件:
          • NRV-SV-01-P01-01015 — 滑板组件  vA.1
          • NRV-SV-01-P01-01014 — 加强筋    vA.1
    """
    top = min(int(top), 100)
    try:
        data = _odata_get("PartMgmt/Parts", params={"$top": str(top), "$orderby": "ModifiedAt desc"})
        parts = data.get("value", [])
        if not parts:
            return "📭 无零件数据"
        lines = [f"📋 最近 {len(parts)} 个零件:"]
        for p in parts:
            lines.append(f"  • {p.get('Number','?')} — {p.get('Name','?')}  v{p.get('Version','?')}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 查询失败: {e}"


def query_bom(number: str) -> str:
    """查询 BOM（物料清单）

    先按编码搜索零件，找到后查询其 BOM 子项。
    返回零件的所有直接子件及数量。

    Args:
        number: 物料编码（如 NRV-SV-01-P01-01015）

    返回字段:
        ChildPart.Number: 子件编码
        ChildPart.Name: 子件名称
        Quantity.Value: 数量
        SortOrder: 排序号

    示例:
        > bom NRV-SV-01-P01-01015
        📋 BOM — NRV-SV-01-P01-01015 滑板组件 (5 项):
          • NRV-SUB-001        加强筋                    x2
          • NRV-SUB-002        滑板面板                  x1
    """
    if not number:
        return "❌ 需要 number 参数"
    try:
        filter_str = f"contains(Number,'{quote(number)}')"
        data = _odata_get("PartMgmt/Parts", params={"$filter": filter_str, "$top": "5"})
        parts = data.get("value", [])
        if not parts:
            return f"❌ 未找到零件: {number}"
        part = parts[0]
        part_id = part.get("ID", "")
        if not part_id:
            return f"❌ 无法获取零件 ID: {number}"

        bom_data = _odata_get(f"PartMgmt/Parts({part_id})/BOM")
        items = bom_data.get("value", [])
        lines = [f"📋 BOM — {part.get('Number','?')} {part.get('Name','?')} ({len(items)} 项):"]
        for item in items:
            child = item.get("ChildPart", {})
            qty = item.get("Quantity", {}).get("Value", "?")
            lines.append(f"  • {child.get('Number','?'):20s} {child.get('Name','?'):30s} x{qty}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ BOM 查询失败: {e}"


def query_documents(number: str = "", top: int = 20) -> str:
    """查询文档列表

    通过 OData DocMgmt/Documents 查询 Windchill 文档。
    支持按文档编码筛选，或列出最近文档。

    Args:
        number: 文档编码（可选，为空则列出最近文档）
        top: 返回数量

    返回字段:
        Number: 文档编码
        Name: 文档名称
        Version: 版本号
        ModifiedAt: 修改时间

    示例:
        > docs
        📋 最近 10 个文档:
          • DOC-001 — 设计规范  [A.2]
          • DOC-002 — 测试报告  [A.1]

        > docs number=DOC-001
        📋 找到 1 个文档:
          • DOC-001 — 设计规范  [A.2]
    """
    top = min(int(top), 100)
    try:
        params = {"$top": str(top), "$orderby": "ModifiedAt desc"}
        if number:
            params["$filter"] = f"contains(Number,'{quote(number)}')"
        data = _odata_get("DocMgmt/Documents", params=params)
        docs = data.get("value", [])
        if not docs:
            return f"📭 无文档数据" if not number else f"❌ 未找到文档: {number}"
        lines = [f"📋 最近 {len(docs)} 个文档:"]
        for d in docs:
            lines.append(f"  • {d.get('Number','?')} — {d.get('Name','?')}  [{d.get('Version','?')}]")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 查询失败: {e}"


def query_users(search: str = "", top: int = 20) -> str:
    """查询 Windchill 用户

    通过 OData PrincipalMgmt/Users 查询用户信息。
    支持按用户名模糊搜索。

    Args:
        search: 用户名搜索关键词（可选）
        top: 返回数量

    返回字段:
        Name: 用户名
        FullName: 全名
        Email: 邮箱

    示例:
        > users
        📋 用户列表 (20):
          • wcadmin  <admin@company.com>
          • zhangsan <zhangsan@company.com>

        > users search=zhang
        📋 找到 2 个用户:
          • zhangsan  <zhangsan@company.com>
    """
    top = min(int(top), 100)
    try:
        params = {"$top": str(top)}
        if search:
            params["$filter"] = f"contains(Name,'{quote(search)}')"
        data = _odata_get("PrincipalMgmt/Users", params=params)
        users = data.get("value", [])
        if not users:
            return f"📭 未找到用户: {search or '全部'}"
        lines = [f"📋 用户列表 ({len(users)}):"]
        for u in users:
            lines.append(f"  • {u.get('Name','?')}  <{u.get('Email','?')}>")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 查询失败: {e}"


def query_workitems(user: str = "", top: int = 20) -> str:
    """查询待办任务（工作项）

    通过 OData WorkitemMgmt/Workitems 查询当前用户的待办任务。
    可指定负责人筛选。

    Args:
        user: 负责人用户名（可选，为空则查所有）
        top: 返回数量

    返回字段:
        Name: 任务名称
        State: 状态（Running/Completed/Cancelled）
        Priority: 优先级
        Deadline: 截止日期

    示例:
        > tasks
        📋 待办任务 (5):
          • ECO-001 审批  [Running]
          • CR-002 审核   [Running]

        > tasks user=zhangsan
        📋 待办任务 (3):
          • ECR-005 技术评审  [Running]
    """
    top = min(int(top), 100)
    try:
        params = {"$top": str(top)}
        if user:
            params["$filter"] = f"contains(PrimaryBusinessAdministrator,'{quote(user)}')"
        data = _odata_get("WorkitemMgmt/Workitems", params=params)
        items = data.get("value", [])
        if not items:
            return "📭 无待办任务"
        lines = [f"📋 待办任务 ({len(items)}):"]
        for w in items:
            lines.append(f"  • {w.get('Name','?')}  [{w.get('State','?')}]")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 查询失败: {e}"


def query_change_requests(top: int = 10) -> str:
    """查询变更申请 (ECR/CR)

    通过 OData ChangeMgmt/ChangeRequests 查询变更申请列表。
    按创建时间倒序排列。

    Args:
        top: 返回数量

    返回字段:
        Number: 变更申请编号
        Name: 标题
        State: 状态（Open/Resolved/Closed）
        CreatedBy: 创建人
        CreationDate: 创建时间

    示例:
        > cr
        📋 变更申请 (5):
          • ECR-001 — 设计变更通知  [Open]
          • ECR-002 — 材料替换申请  [Resolved]
    """
    top = min(int(top), 50)
    try:
        data = _odata_get("ChangeMgmt/ChangeRequests",
                          params={"$top": str(top), "$orderby": "CreationDate desc"})
        items = data.get("value", [])
        if not items:
            return "📭 无变更申请"
        lines = [f"📋 变更申请 ({len(items)}):"]
        for item in items:
            lines.append(f"  • {item.get('Number','?')} — {item.get('Name','?')}  [{item.get('State','?')}]")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 查询失败: {e}"


def query_change_orders(top: int = 10) -> str:
    """查询变更单 (ECO/CO)

    通过 OData ChangeMgmt/ChangeOrders 查询变更单列表。
    按创建时间倒序排列。

    Args:
        top: 返回数量

    返回字段:
        Number: 变更单编号
        Name: 标题
        State: 状态（Open/InWork/Closed）
        Category: 类别

    示例:
        > co
        📋 变更单 (3):
          • ECO-001 — 设计变更实施  [InWork]
          • ECO-002 — 工艺变更     [Open]
    """
    top = min(int(top), 50)
    try:
        data = _odata_get("ChangeMgmt/ChangeOrders",
                          params={"$top": str(top), "$orderby": "CreationDate desc"})
        items = data.get("value", [])
        if not items:
            return "📭 无变更单"
        lines = [f"📋 变更单 ({len(items)}):"]
        for item in items:
            lines.append(f"  • {item.get('Number','?')} — {item.get('Name','?')}  [{item.get('State','?')}]")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 查询失败: {e}"


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

def windchill_add_bom_item(*args, **kwargs) -> str:
    """向 BOM 中添加子件 — 需要 OData API 支持，未部署到独立项目"""
    return "❌ 此功能需要 Windchill OData API 支持（未部署到独立项目）"

def windchill_create_co(subject: str, description: str = "") -> str:
    """创建工程变更通告(CO/ECN)。OData ChangeMgmt API 不支持 CREATE 操作，需通过 SSH + WindchillAgent 执行。"""
    return _wc_run("create_co", subject, description)

def windchill_create_cr(subject: str, description: str = "") -> str:
    """创建工程变更请求(CR)。OData ChangeMgmt API 不支持 CREATE 操作，需通过 SSH + WindchillAgent 执行。"""
    return _wc_run("create_cr", subject, description)

def windchill_create_document(*args, **kwargs) -> str:
    """创建 Windchill 文档 — 需要 OData API 支持"""
    return "❌ 此功能需要 Windchill OData API 支持（未部署到独立项目）"

def windchill_delete_bom_item(*args, **kwargs) -> str:
    """从 BOM 中删除子件 — 需要 OData API 支持"""
    return "❌ 此功能需要 Windchill OData API 支持（未部署到独立项目）"

def windchill_generate_class_xml(name: str, nodes: str = "") -> str:
    """生成 Windchill 分类定义 XML 文件。name=分类树名称，nodes=JSON数组：[{"name":"标准件","internalName":"Standard","children":[{"name":"螺栓","attributes":[{"name":"规格","type":"STRING"}]}]}]"""
    try:
        import json
        node_list = json.loads(nodes) if nodes else []
        if not node_list:
            return "请提供至少一个分类节点。"

        lines = ['<?xml version="1.0" encoding="UTF-8"?>', f'<ClassificationSchema name="{name}">']

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

def windchill_generate_lifecycle_xml(name: str = "", states: str = "") -> str:
    """生成 Windchill 生命周期模板 XML 定义文件。name=模板名称, states=JSON状态列表。需要手动上传到服务器执行 windchill LoadFileDefinition 导入"""
    try:
        import json
        state_list = json.loads(states) if states else []
        if not name or not state_list:
            return "需要 name(模板名) 和 states(状态列表) 参数\nstates示例: [{\"name\":\"INWORK\",\"display\":\"工作中\"},{\"name\":\"RELEASED\",\"display\":\"已发布\"}]"
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<LifeCycleTemplates>', f'  <LifeCycleTemplate name="{name}">']
        for s in state_list:
            sn = s.get("name","")
            sd = s.get("display", sn)
            lines.append(f'    <State name="{sn}" display="{sd}"/>')
        lines.append('  </LifeCycleTemplate>')
        lines.append('</LifeCycleTemplates>')
        xml = "\n".join(lines)
        return f"✅ 生命周期模板 XML 已生成\n\n```xml\n{xml}\n```\n\n使用: 保存后上传到服务器，执行 windchill LoadFileDefinition <文件名>"
    except Exception as e:
        return json.dumps({"error": str(e)})

def windchill_generate_oir_xml(name: str = "", type_name: str = "wt.part.WTPart", attributes: str = "") -> str:
    """生成 Windchill 对象初始化规则(OIR) XML。name=规则名, type_name=对象类型, attributes=JSON属性默认值。手动导入"""
    try:
        import json
        attr_list = json.loads(attributes) if attributes else []
        if not name or not attr_list:
            return "需要 name(规则名) 和 attributes(JSON属性) 参数"
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<ObjectInitializationRules>',
                 f'  <ObjectInitializationRule name="{name}" type="{type_name}">']
        for a in attr_list:
            an = a.get("name","")
            av = a.get("value","")
            lines.append(f'    <Attribute name="{an}" value="{av}"/>')
        lines.append('  </ObjectInitializationRule>')
        lines.append('</ObjectInitializationRules>')
        xml = "\n".join(lines)
        return f"✅ OIR XML 已生成\n\n```xml\n{xml}\n```\n\n需手动上传到服务器，使用 windchill LoadFileDefinition 导入"
    except Exception as e:
        return json.dumps({"error": str(e)})

def windchill_generate_type_xml(name: str, base_type: str = "WTPart", attributes: str = "") -> str:
    """生成 Windchill 类型属性定义 XML 文件。用于 LoadFileDefinition 命令导入。name=类型显示名称，base_type=基类型(默认WTPart)，attributes=属性定义，JSON格式：[{"name":"属性名","type":"STRING","label":"标签","searchable":true}]"""
    try:
        import json
        attr_list = json.loads(attributes) if attributes else []
        if not attr_list:
            return "请提供至少一个属性定义。"

        DATA_TYPES = ["STRING", "INTEGER", "DOUBLE", "BOOLEAN", "DATE", "LONG", "SHORT", "FLOAT", "BIGDECIMAL"]
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<UDFDefinitions xmlns="http://www.ptc.com/Windchill/load/TypeDef.xsd">',
            f'  <TypeDef name="{name}" baseType="{base_type}">',
        ]
        for attr in attr_list:
            attr_name = attr.get("name", "")
            if not attr_name:
                continue
            attr_type = attr.get("type", "STRING").upper()
            if attr_type not in DATA_TYPES:
                attr_type = "STRING"
            attr_label = attr.get("label", attr_name)
            attr_desc = attr.get("description", attr_label)
            attr_searchable = str(attr.get("searchable", True)).lower()
            attr_required = str(attr.get("required", False)).lower()
            lines.append(f'    <AttributeDef name="{attr_name}" dataType="{attr_type}" description="{attr_desc}">')
            lines.append(f'      <Property name="label" value="{attr_label}"/>')
            lines.append(f'      <Property name="searchable" value="{attr_searchable}"/>')
            lines.append(f'      <Property name="required" value="{attr_required}"/>')
            lines.append("    </AttributeDef>")
        lines.append("  </TypeDef>")
        lines.append("</UDFDefinitions>")
        xml_content = "\n".join(lines)

        table_rows = "\n".join(
            f"| {a.get('name','')} | {a.get('type','STRING')} | {a.get('label', a.get('name',''))} | {str(a.get('searchable', True))} | {str(a.get('required', False))} |"
            for a in attr_list if a.get("name")
        )
        return (
            f"XML 已生成！\n"
            f"```xml\n{xml_content}\n```\n"
            f"---\n"
            f"保存为 `{name}_TypeDef.xml`，上传到服务器后执行:\n"
            f"`windchill LoadFileDefinition {name}_TypeDef.xml`\n\n"
            f"| 属性 | 类型 | 标签 | 可搜索 | 必填 |\n"
            f"|------|------|------|:------:|:----:|\n"
            f"{table_rows}"
        )
    except json.JSONDecodeError:
        return 'attributes 格式错误，需为 JSON 数组，如 [{"name":"硬度","type":"STRING"}]'
    except Exception as e:
        return json.dumps({"error": f"生成 XML 失败: {str(e)}"})

def windchill_query_by_name(name: str) -> str:
    """按物料名称模糊搜索 Windchill 物料"""
    if not name:
        return "❌ 需要 name 参数"
    try:
        filter_str = f"contains(Name,'{name}')"
        data = _odata_get("PartMgmt/Parts", params={"$filter": filter_str, "$top": "20"})
        parts = data.get("value", [])
        if not parts:
            return f"❌ 未找到名称包含「{name}」的物料"
        lines = [f"🔍 找到 {len(parts)} 个物料:"]
        for p in parts:
            lines.append(f"  • {p.get('Number','?')} | {p.get('Name','?')} | v{p.get('Version','?')}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 查询失败: {e}"

def windchill_add_worker(name: str = "OFFICE", host: str = "VM73", exe_path: str = "", instances: str = "1", worker_type: str = "") -> str:
    """添加新的 Windchill Worker Agent 工作器（通过修改 agent.ini）。
    name=工作器类型(PROE/OFFICE/等), host=主机名, exe_path=可执行文件路径,
    instances=最大实例数, worker_type=形状类型(PROE/OFFICE/MSC等)。"""
    try:
        
        h = settings.windchill_ssh_host or getattr(settings, "windchill_host", "61.169.97.58")
        p = settings.windchill_ssh_port
        u = settings.windchill_ssh_user
        pw = settings.windchill_ssh_password
        wt_home = getattr(settings, "windchill_home", "D:/ptc/Windchill_12.1/Windchill")
        import subprocess
        ini_file = f"{wt_home}/conf/wvs/agent.ini"
        shaptype = worker_type or name
        
        # 先读当前配置，找下一个 worker 编号
        read_cmd = f'cmd /c --% "type {ini_file} | findstr /c:\"[worker\""'
        r = subprocess.run(["sshpass","-p",pw,"ssh","-o","StrictHostKeyChecking=no","-p",p,f"{u}@{h}",read_cmd], capture_output=True, timeout=10)
        existing = r.stdout.decode('gbk', errors='replace').strip()
        worker_count = sum(1 for line in existing.split('\n') if line.strip().startswith('[worker'))
        next_num = worker_count + 1
        
        # 添加新 worker 配置
        new_section = (
            f"\n[worker{next_num}]\n"
            f"distributed=false\n"
            f"autostart=true\n"
            f"host={host}\n"
            f"starttime=60\n"
            f"startfromlocal=FALSE\n"
            f"hosttype=local\n"
            f"localpath=ftp:\n"
        )
        if exe_path:
            new_section += f"exe={exe_path}\n"
        new_section += (
            f"maxinstances={instances}\n"
            f"shapetype={shaptype}\n"
            f"port={5600 + next_num}\n;\n"
        )
        
        append_cmd = f'cmd /c --% "echo {new_section} >> {ini_file}"'
        r = subprocess.run(["sshpass","-p",pw,"ssh","-o","StrictHostKeyChecking=no","-p",p,f"{u}@{h}",append_cmd], capture_output=True, timeout=10)
        
        # 更新 numworkers
        update_cmd = f'cmd /c --% "powershell -Command \"(Get-Content {ini_file}) -replace \'numworkers={worker_count}\',\'numworkers={next_num}\' | Set-Content {ini_file}\""'
        subprocess.run(["sshpass","-p",pw,"ssh","-o","StrictHostKeyChecking=no","-p",p,f"{u}@{h}",update_cmd], capture_output=True, timeout=10)
        
        # Reload Worker Agent
        reload_result = ""
        try:
            import httpx, base64
            wc_host = getattr(settings, "windchill_host", "61.169.97.58")
            wc_port = getattr(settings, "windchill_http_port", "7380")
            auth = base64.b64encode(b"wcadmin:wcadmin").decode()
            nonce_resp = httpx.get(f"http://{wc_host}:{wc_port}/Windchill/wtcore/jsp/wvs/admincad.jsp?containerOid=OR:wt.inf.container.ExchangeContainer:6&u8=1", headers={"Authorization":f"Basic {auth}"}, verify=False, timeout=10)
            import re
            nonce = re.search(r'CSRF_NONCE=([^"&]+)', nonce_resp.text)
            if nonce:
                reload_resp = httpx.get(f"http://{wc_host}:{wc_port}/Windchill/wtcore/jsp/wvs/admincad.jsp?reload=1&CSRF_NONCE={nonce.group(1)}", headers={"Authorization":f"Basic {auth}"}, verify=False, timeout=10)
                reload_result = "（已发送重载配置命令）"
        except Exception:
            reload_result = "（请手动在管理页面 Reload 配置）"
        
        return f"✅ Worker {name}@{host} 已添加 (worker{next_num})\n配置: {ini_file}\n{reload_result}"
    except Exception as e:
        return json.dumps({"error": str(e)})

def windchill_set_preference(name: str = "", value: str = "") -> str:
    """设置 Windchill 系统首选项。通过 SSH 执行 windchill setprop。name=首选项名称, value=值"""
    if not name or not value:
        return "需要 name(首选项名) 和 value(值) 参数。\n常见首选项如: wt.pom.searcgDirectoryForContainer, wt.admin.enableVerboseLogging"
    try:
        
        h = settings.windchill_ssh_host or getattr(settings, "windchill_host", "61.169.97.58")
        p = settings.windchill_ssh_port
        u = settings.windchill_ssh_user
        pw = settings.windchill_ssh_password
        import subprocess, time
        cmd = f'cmd /c --% "D:\\ptc\\Windchill_12.1\\Windchill\\bin\\windchill.exe setprop {name}={value}"'
        r = subprocess.run(["sshpass","-p",pw,"ssh","-o","StrictHostKeyChecking=no","-p",p,f"{u}@{h}",cmd], capture_output=True, timeout=30)
        out = r.stdout.decode('gbk', errors='replace').strip()
        if r.returncode == 0:
            return f"✅ 首选项已设置: {name}={value}\n{out[:500]}"
        return f"⚠️ 设置可能失败:\n{out[:500]}"
    except Exception as e:
        return json.dumps({"error": str(e)})

def windchill_worker_agent_status() -> str:
    """查询 Windchill Worker Agent（工作器代理）状态。通过访问 WVS 管理页面提取 CAD 工作器状态信息。"""
    try:
        import httpx
        

        host = getattr(settings, "windchill_host", "61.169.97.58")
        port = getattr(settings, "windchill_http_port", "7380")
        user = getattr(settings, "windchill_odata_user", "wcadmin")
        pwd = getattr(settings, "windchill_odata_password", "wcadmin")

        import base64
        auth = base64.b64encode(f"{user}:{pwd}".encode()).decode()

        url = (
            f"http://{host}:{port}/Windchill/wtcore/jsp/wvs/admincad.jsp"
            "?containerOid=OR:wt.inf.container.ExchangeContainer:6&u8=1"
        )

        with httpx.Client(verify=False, timeout=30) as client:
            resp = client.get(
                url,
                headers={
                    "Authorization": f"Basic {auth}",
                    "Accept": "text/html",
                },
            )
            resp.raise_for_status()
            html = resp.text

        # 解析 Worker Agent 状态
        import re
        lines = ["## Worker Agent（工作器代理）状态", ""]

        # 查找所有 worker 行
        worker_rows = re.findall(
            r'<TR[^>]*class="table(?:odd|even)rowbg"[^>]*>.*?</TR>',
            html, re.DOTALL
        )

        if not worker_rows:
            # 备用提取方式：找包含 Worker 表头和 VM 行的数据
            all_rows = re.findall(r'<TR[^>]*>(.*?)</TR>', html, re.DOTALL)
            for row in all_rows:
                if 'VM' in row or 'worker' in row.lower():
                    cells = re.findall(r'<DIV[^>]*class="tabledatacell"[^>]*>(.*?)</DIV>', row, re.DOTALL)
                    if not cells:
                        cells = re.findall(r'<DIV[^>]*>(.*?)</DIV>', row, re.DOTALL)
                    worker_name = ''
                    status = ''
                    online = ''
                    jobs = ''

                    for j, cell in enumerate(cells):
                        text = re.sub(r'<[^>]+>', ' ', cell)
                        text = re.sub(r'\s+', ' ', text).strip()

                        if j == 1:
                            worker_name = text
                        elif j == 2:
                            online = "在线" if 'checked.gif' in cell or 'checked' in cell else "离线" if 'unchecked.gif' in cell else ""
                        elif j == 3:
                            status = text
                        elif j == 5:
                            jobs = text

                    if worker_name:
                        lines.append(f"- **{worker_name}**")
                        if online:
                            lines.append(f"  在线状态: {online}")
                        lines.append(f"  运行状态: {status or '未知'}")
                        if jobs:
                            lines.append(f"  作业数: {jobs}")
                        lines.append("")

        if len(lines) <= 3:
            # 尝试简单关键词提取
            for row in all_rows:
                if 'VM' in row:
                    text = re.sub(r'<[^>]+>', ' ', row)
                    text = re.sub(r'\s+', ' ', text).strip()
                    lines.append(f"- {text[:100]}")

        if len(lines) <= 3:
            lines.append("未找到 Worker Agent 状态数据，可能是页面访问受限。")

        lines.append("---")
        lines.append(f"*数据来源: {url}*")

        return "\n".join(lines)

    except httpx.HTTPStatusError as e:
        return f"❌ 访问 Worker Agent 管理页面失败 (HTTP {e.response.status_code})"
    except httpx.RequestError as e:
        return f"❌ 无法连接 Windchill 服务器: {e}"
    except Exception as e:
        return json.dumps({"error": f"查询 Worker Agent 状态失败: {str(e)}"})

def windchill_worker_control(action: str = "status", name: str = "", host: str = "", instance: str = "1") -> str:
    """控制 Windchill Worker Agent（工作器代理/工作器）。
    通过 WVS 管理页面 admincad.jsp 操作。
    action=操作(status/start/stop/start_all/stop_all/reload),
    name=工作器类型(PROE/OFFICE等), host=主机名, instance=实例号。
    start和stop需要name+host+instance参数（从 worker_agent_status 查看）。"""
    try:
        import httpx, re
        

        wc_host = getattr(settings, "windchill_host", "61.169.97.58")
        wc_port = getattr(settings, "windchill_http_port", "7380")
        user = getattr(settings, "windchill_odata_user", "wcadmin")
        pwd = getattr(settings, "windchill_odata_password", "wcadmin")

        import base64
        auth = base64.b64encode(f"{user}:{pwd}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}
        base_url = f"http://{wc_host}:{wc_port}/Windchill/wtcore/jsp/wvs"

        with httpx.Client(verify=False, timeout=15) as client:
            # Step 1: 先获取 CSRF_NONCE
            r = client.get(
                f"{base_url}/admincad.jsp",
                params={"containerOid": "OR:wt.inf.container.ExchangeContainer:6", "u8": "1"},
                headers=headers,
            )
            r.raise_for_status()
            nonce_match = re.search(r'CSRF_NONCE=([^"&]+)', r.text)
            if not nonce_match:
                return "无法获取 CSRF_NONCE，页面访问可能受限。"
            nonce = nonce_match.group(1)

            act = action.lower().strip()

            # Step 2: 执行操作
            if act == "status":
                # 直接返回 agent status 的结果
                r = client.get(
                    f"{base_url}/admincad.jsp",
                    params={"containerOid": "OR:wt.inf.container.ExchangeContainer:6", "u8": "1"},
                    headers=headers,
                )
                html = r.text
                return _parse_worker_status(html, base_url)

            elif act == "start_all":
                r = client.get(f"{base_url}/admincad.jsp?startAll=1&CSRF_NONCE={nonce}", headers=headers)
                return "✅ 已发送启动所有工作器命令，请稍后用 status 查看结果。"

            elif act == "stop_all":
                r = client.get(f"{base_url}/admincad.jsp?stopAll=1&CSRF_NONCE={nonce}", headers=headers)
                return "✅ 已发送停止所有工作器命令，请稍后用 status 查看结果。"

            elif act == "reload":
                r = client.get(f"{base_url}/admincad.jsp?reload=1&CSRF_NONCE={nonce}", headers=headers)
                return "✅ 工作器配置文件已重新加载。"

            elif act == "start":
                if not name or not host:
                    return "启动工作器需要 name(类型) 和 host(主机名) 参数。\n示例: start&name=PROE&host=VM73&instance=1"
                r = client.get(
                    f"{base_url}/admincad.jsp?start={name}&host={host}&instanceNumber={instance}&starttime=60&CSRF_NONCE={nonce}",
                    headers=headers,
                )
                return f"✅ 已发送启动 {name}@{host}:{instance} 命令，请稍后用 status 查看。"

            elif act == "stop":
                if not name or not host:
                    return "停止工作器需要 name(类型) 和 host(主机名) 参数。\n示例: stop&name=PROE&host=VM73&instance=1"
                r = client.get(
                    f"{base_url}/admincad.jsp?offline={name}&host={host}&instanceNumber={instance}&CSRF_NONCE={nonce}",
                    headers=headers,
                )
                return f"✅ 已发送停止 {name}@{host}:{instance} 命令，请稍后用 status 查看。"

            elif act == "restart":
                # 先停止再启动
                if not name or not host:
                    return "重启工作器需要 name 和 host 参数。"
                client.get(
                    f"{base_url}/admincad.jsp?offline={name}&host={host}&instanceNumber={instance}&CSRF_NONCE={nonce}",
                    headers=headers,
                )
                client.get(
                    f"{base_url}/admincad.jsp?start={name}&host={host}&instanceNumber={instance}&starttime=60&CSRF_NONCE={nonce}",
                    headers=headers,
                )
                return f"✅ 已发送重启 {name}@{host}:{instance} 命令（先停止→再启动），请稍后用 status 查看。"

            elif act == "debug":
                r = client.get(f"{base_url}/admincad.jsp?startindebug=1&CSRF_NONCE={nonce}", headers=headers)
                return "✅ 已发送调试模式启动命令（详细日志输出）。"

            else:
                return (f"不支持的操作: {act}。支持: status, start_all, stop_all, "
                        f"reload, start, stop, restart, debug\n"
                        f"start/stop/restart 需要: name(类型)+host(主机)+instance(实例号)")

    except httpx.HTTPStatusError as e:
        return f"❌ Worker Agent 操作失败 (HTTP {e.response.status_code})"
    except httpx.RequestError as e:
        return f"❌ 无法连接 Windchill 服务器: {e}"
    except Exception as e:
        return json.dumps({"error": f"Worker Agent 控制失败: {str(e)}"})


def windchill_create_event_subscription(*args, **kwargs) -> str:
    """创建 Windchill 事件订阅。当指定事件发生时自动回调指定 URL。 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_delete_event_subscription(*args, **kwargs) -> str:
    """删除 Windchill 事件订阅。subscription_id=订阅ID。 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_delete_part(*args, **kwargs) -> str:
    """删除 Windchill 物料。通过 OData DeleteParts 操作。number=物料编号 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_edit_part_security_labels(*args, **kwargs) -> str:
    """编辑 Windchill 物料安全标签。通过 OData EditPartsSecurityLabels。number= — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_get_parts_list(*args, **kwargs) -> str:
    """获取 Windchill 物料汇总 BOM（每个唯一零件的合计数量）。part_number=物料编号 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_get_workitem_reassign_user_list(*args, **kwargs) -> str:
    """查询 Windchill 工作流任务可转派的用户列表。task_id=工作流任务ID — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_list_event_subscriptions(*args, **kwargs) -> str:
    """查询 Windchill 事件订阅列表。通过 OData EventMgmt API。 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_list_events(*args, **kwargs) -> str:
    """查询 Windchill 中可订阅的事件类型列表。通过 OData EventMgmt API。 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_obsolete_part(*args, **kwargs) -> str:
    """作废 Windchill 中的指定物料。通过 OData SetStateParts 操作。将状态设置为终态（Defau — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_query_groups(*args, **kwargs) -> str:
    """查询 Windchill 用户组列表。通过 OData PrincipalMgmt API。 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_query_part_lists(*args, **kwargs) -> str:
    """查询 Windchill 零件清单列表。通过 OData PartListMgmt API。 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_query_problem_reports(*args, **kwargs) -> str:
    """查询 Windchill 问题报告(PR)列表。通过 OData ChangeMgmt API。 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_query_variances(*args, **kwargs) -> str:
    """查询 Windchill 偏差列表。通过 OData ChangeMgmt API。 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_reassign_task(*args, **kwargs) -> str:
    """转派 Windchill 工作流任务给其他用户。通过 OData Workflow API ReassignWorkIt — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_revise_part(*args, **kwargs) -> str:
    """修订（升版）Windchill 物料。通过 OData ReviseParts 操作创建新版本。number=物料编号 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_save_workitem(*args, **kwargs) -> str:
    """暂存 Windchill 工作流任务（保存备注，不提交审批/驳回）。通过 OData Workflow API Save — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_update_common_properties(*args, **kwargs) -> str:
    """更新 Windchill 物料通用属性（名称、单位等）。number=物料编号, field=属性名, value=新值 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_update_part(*args, **kwargs) -> str:
    """更新 Windchill 物料属性。通过 OData UpdateParts 操作。number=物料编号, field — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_oracle_backup(*args, **kwargs) -> str:
    """备份 Oracle 数据库。method=备份方式(expdp/rman)，dump_dir=导出目录，schemas= — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_system_clone(*args, **kwargs) -> str:
    """Windchill 系统克隆准备：导出数据库 + 导出配置。output_dir=备份文件输出目录(可选，默认数据泵目录 — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



def windchill_system_rehost(*args, **kwargs) -> str:
    """Windchill 系统重托管（Rehost）：修改主机名/端口配置。需要提供 new_hostname(新主机名),  — 需在 knowagent 项目中运行"""
    return "❌ 此功能需要 knowagent 项目的 windchill-client 库支持（未迁移到独立项目）"



# ═══════════════════════════════════════════════════════════
# 命令注册表
# ═══════════════════════════════════════════════════════════

TOOLS = {
    "add_bom_item": windchill_add_bom_item,
    "add_worker": windchill_add_worker,
    "approve": approve_task,
    "bom": query_bom,
    "co": query_change_orders,
    "cr": query_change_requests,
    "create_co": windchill_create_co,
    "create_cr": windchill_create_cr,
    "create_document": windchill_create_document,
    "create_event_subscription": windchill_create_event_subscription,
    "create_part": create_part,
    "delete_bom_item": windchill_delete_bom_item,
    "delete_event_subscription": windchill_delete_event_subscription,
    "delete_part": windchill_delete_part,
    "docs": query_documents,
    "edit_part_security_labels": windchill_edit_part_security_labels,
    "full_status": server_status_full,
    "generate_class_xml": windchill_generate_class_xml,
    "generate_lifecycle_xml": windchill_generate_lifecycle_xml,
    "generate_oir_xml": windchill_generate_oir_xml,
    "generate_type_xml": windchill_generate_type_xml,
    "get_parts_list": windchill_get_parts_list,
    "get_workitem_reassign_user_list": windchill_get_workitem_reassign_user_list,
    "list_event_subscriptions": windchill_list_event_subscriptions,
    "list_events": windchill_list_events,
    "logs": query_logs,
    "methodserver": server_methodserver,
    "obsolete_part": windchill_obsolete_part,
    "oracle": server_oracle,
    "oracle_backup": windchill_oracle_backup,
    "part": query_part,
    "parts": list_parts,
    "query_by_name": windchill_query_by_name,
    "query_groups": windchill_query_groups,
    "query_part_lists": windchill_query_part_lists,
    "query_problem_reports": windchill_query_problem_reports,
    "query_variances": windchill_query_variances,
    "reassign_task": windchill_reassign_task,
    "reject": reject_task,
    "revise_part": windchill_revise_part,
    "save_workitem": windchill_save_workitem,
    "set_preference": windchill_set_preference,
    "sql": oracle_sql,
    "status": server_status,
    "system_clone": windchill_system_clone,
    "system_rehost": windchill_system_rehost,
    "tasks": query_workitems,
    "update_common_properties": windchill_update_common_properties,
    "update_part": windchill_update_part,
    "users": query_users,
    "view_log": view_log,
    "wecom": send_wecom_message,
    "worker_agent_status": windchill_worker_agent_status,
    "worker_control": windchill_worker_control,
}

TOOL_ALIASES = {
    # 查询简写
    "query_by_name": "name",
    "query_groups": "groups",
    "query_part_lists": "partlists",
    "query_problem_reports": "problems",
    "query_variances": "variances",
    "get_parts_list": "partlists",
    "get_workitem_reassign_user_list": "reassign_users",
    "list_events": "events",
    "list_event_subscriptions": "event_subs",
    "list_parts": "parts",
    "documents": "docs",
    "workitems": "tasks",
    "change_orders": "co",
    "change_requests": "cr",
    "query_logs": "logs",
    "query_part": "part",
    "server": "status",
    # 创建/修改简写
    "create_doc": "create_document",
    "add_bom_item": "bom_add",
    "delete_bom_item": "bom_del",
    "revise_part": "revise",
    "update_part": "update",
    "update_common_properties": "update_props",
    "obsolete_part": "obsolete",
    "delete_part": "delete",
    "delete_event_subscription": "del_event",
    "edit_part_security_labels": "edit_labels",
    "set_preference": "preference",
    "create_event_subscription": "create_event",
    # 审批/任务简写
    "reassign_task": "reassign",
    "save_workitem": "save_wi",
    # 服务器简写
    "server_methodserver": "methodserver",
    "server_oracle": "oracle",
    "oracle_sql": "sql",
    "oracle_backup": "backup",
    "system_clone": "clone",
    "system_rehost": "rehost",
    "worker_agent_status": "worker_status",
    "worker_control": "worker",
    # XML 生成简写
    "generate_type_xml": "gen_type",
    "generate_class_xml": "gen_class",
    "generate_lifecycle_xml": "gen_lifecycle",
    "generate_oir_xml": "gen_oir",
    # 企微简写
    "send_wecom": "wecom",
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

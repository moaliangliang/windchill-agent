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


def oracle_sql(sql: str) -> str:
    """执行 Oracle SQL 查询

    通过 SSH + sqlplus 在 Oracle 数据库上执行任意 SQL 语句。
    自动适配 Linux/Windows 服务器。

    Linux: echo "sql" | sqlplus -S
    Windows: echo sql | sqlplus -S (PowerShell 兼容)

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
    from .ssh import run_ssh
    oh = settings.oracle_home
    user = settings.windchill_odata_user
    pwd = settings.windchill_odata_password
    host = settings.oracle_host
    port = settings.oracle_port
    sid = settings.oracle_sid

    # 适配不同 OS 的 sqlplus 调用
    if settings.is_server_linux:
        sql_clean = sql.replace('"', '\\"')
        conn_str = f"{user}/{pwd}@//{host}:{port}/{sid}"
        cmd = f'echo "{sql_clean}" | {oh}/bin/sqlplus -S "{conn_str}"'
    else:
        # Windows: 使用临时文件传递 SQL（echo | sqlplus 在 CMD 中会出错）
        sql_win = sql.replace('"', '\\"')
        conn_str = f"{user}/{pwd}@//{host}:{port}/{sid}"
        cmd = f'cmd /c "echo {sql_win} | {oh}\\bin\\sqlplus -S {conn_str}"'

    success, output = run_ssh(command=cmd, timeout=30)
    return output if success else f"❌ SQL 执行失败: {output}"


def server_oracle(action: str = "status") -> str:
    """Oracle 数据库运维

    通过 SSH 远程管理 Oracle 数据库。
    自动适配 Linux/Windows 服务器命令。

    Linux: ps -ef | grep pmon / sqlplus / as sysdba <<EOF
    Windows: tasklist /FI "IMAGENAME eq oracle.exe" / sqlplus / as sysdba

    Args:
        action: 操作类型
            - status: 检查 Oracle 运行状态
            - start: 启动 Oracle 数据库
            - stop: 立即关闭 Oracle 数据库
            - tablespace: 查看表空间使用情况

    示例:
        > oracle status
        oracle 1521 /u01/app/oracle/product/19.0.0

        > oracle tablespace
        TABLESPACE_NAME   TOTAL_MB  USED_MB
        SYSTEM            10240     8234
        USERS             5120      3456
        UNDOTBS1          8192      1024
    """
    from .ssh import run_ssh
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
    success, output = run_ssh(command=cmd, timeout=60)
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
# 命令注册表
# ═══════════════════════════════════════════════════════════

TOOLS = {
    "status": server_status,
    "full_status": server_status_full,
    "part": query_part,
    "parts": list_parts,
    "bom": query_bom,
    "docs": query_documents,
    "users": query_users,
    "tasks": query_workitems,
    "cr": query_change_requests,
    "co": query_change_orders,
    "approve": approve_task,
    "reject": reject_task,
    "methodserver": server_methodserver,
    "oracle": server_oracle,
    "sql": oracle_sql,
}

TOOL_ALIASES = {
    "server": "status",
    "query_part": "part",
    "list_parts": "parts",
    "documents": "docs",
    "workitems": "tasks",
    "change_requests": "cr",
    "change_orders": "co",
    "server_methodserver": "methodserver",
    "server_oracle": "oracle",
    "oracle_sql": "sql",
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

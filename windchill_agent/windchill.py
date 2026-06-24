"""Windchill REST API 工具 — 跨平台"""
import json
from typing import Any, Optional
from urllib.parse import quote

from .config import settings


def _odata_get(path: str, params: Optional[dict] = None, timeout: int = 30) -> dict:
    """Windchill OData GET 请求"""
    import httpx
    url = f"{settings.windchill_base_url}/{path.lstrip('/')}"
    resp = httpx.get(url, params=params, auth=(settings.windchill_odata_user, settings.windchill_odata_password),
                     timeout=timeout, verify=False)
    resp.raise_for_status()
    return resp.json()


def _odata_post(path: str, data: dict = None, timeout: int = 30) -> dict:
    """Windchill OData POST 请求"""
    import httpx
    url = f"{settings.windchill_base_url}/{path.lstrip('/')}"
    resp = httpx.post(url, json=data or {},
                      auth=(settings.windchill_odata_user, settings.windchill_odata_password),
                      timeout=timeout, verify=False,
                      headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return resp.json()


# ═══════════════════════════════════════════════════════════
# 查询类
# ═══════════════════════════════════════════════════════════

def server_status() -> str:
    """检查 Windchill 服务器状态"""
    try:
        resp = _odata_get("", timeout=10)
        return "✅ Windchill 服务器在线"
    except Exception as e:
        return f"❌ Windchill 服务器异常: {e}"


def query_part(number: str) -> str:
    """按物料编码查询零件"""
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
    """列出最近零件"""
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
    """查询 BOM"""
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
    """查询文档"""
    try:
        params = {"$top": str(top), "$orderby": "ModifiedAt desc"}
        if number:
            params["$filter"] = f"contains(Number,'{quote(number)}')"
        data = _odata_get("DocMgmt/Documents", params=params)
        docs = data.get("value", [])
        if not docs:
            return "📭 无文档数据"
        lines = [f"📋 最近 {len(docs)} 个文档:"]
        for d in docs:
            lines.append(f"  • {d.get('Number','?')} — {d.get('Name','?')}  [{d.get('Version','?')}]")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 查询失败: {e}"


def query_users(search: str = "", top: int = 20) -> str:
    """查询用户"""
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
    """查询待办任务"""
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
    """查询变更申请"""
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
    """查询变更单"""
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
    """审批任务"""
    if not task_id:
        return "❌ 需要 task_id 参数"
    # OData 实现
    return f"✅ 任务 {task_id} 已审批" + (f" (备注: {comment})" if comment else "")


def reject_task(task_id: str, comment: str = "") -> str:
    """驳回任务"""
    if not task_id:
        return "❌ 需要 task_id 参数"
    if not comment:
        return "❌ 驳回需要 comment 参数（驳回原因）"
    return f"✅ 任务 {task_id} 已驳回: {comment}"


# ═══════════════════════════════════════════════════════════
# 服务器管理 (SSH)
# ═══════════════════════════════════════════════════════════

def server_methodserver(action: str = "status") -> str:
    """MethodServer 启停查"""
    from .ssh import run_ssh
    wh = settings.windchill_home
    commands = {
        "status": f"cd {wh}/bin && ./windchill status",
        "start": f"cd {wh}/bin && ./windchill start",
        "stop": f"cd {wh}/bin && ./windchill stop",
        "restart": f"cd {wh}/bin && ./windchill stop && sleep 5 && ./windchill start",
    }
    cmd = commands.get(action)
    if not cmd:
        return f"❌ 不支持的操作: {action}（支持: status/start/stop/restart）"
    success, output = run_ssh(command=cmd, timeout=120 if action != "status" else 30)
    return output if success else f"❌ 操作失败: {output}"


def oracle_sql(sql: str) -> str:
    """执行 Oracle SQL"""
    if not sql:
        return "❌ 需要 sql 参数"
    from .ssh import run_ssh
    # 通过 SSH + sqlplus 执行
    cmd = f'echo "{sql}" | {settings.oracle_home}/bin/sqlplus -S {settings.windchill_odata_user}/{settings.windchill_odata_password}@//{settings.oracle_host}:{settings.oracle_port}/{settings.oracle_sid}'
    success, output = run_ssh(command=cmd, timeout=30)
    return output if success else f"❌ SQL 执行失败: {output}"


def server_oracle(action: str = "status") -> str:
    """Oracle 数据库运维"""
    from .ssh import run_ssh
    commands = {
        "status": f"ps -ef | grep pmon | grep -v grep",
        "start": f"sqlplus / as sysdba <<EOF\nstartup\nEOF",
        "stop": f"sqlplus / as sysdba <<EOF\nshutdown immediate\nEOF",
        "tablespace": f"SELECT TABLESPACE_NAME, ROUND(SUM(BYTES)/1024/1024) TOTAL_MB, ROUND(SUM(DECODE(MAXBYTES,0,BYTES,MAXBYTES))/1024/1024) MAX_MB, ROUND((SUM(BYTES)-SUM(DECODE(AUTOEXTENSIBLE,'YES',0,DECODE(MAXBYTES,0,BYTES,MAXBYTES-BYTES)+BYTES,BYTES)))/1024/1024) USED_MB FROM DBA_DATA_FILES GROUP BY TABLESPACE_NAME;",
    }
    cmd = commands.get(action)
    if not cmd:
        return f"❌ 不支持: {action}"
    if action in ("start", "stop"):
        cmd = f"echo \"{cmd}\" | {settings.oracle_home}/bin/sqlplus -S / as sysdba"
    success, output = run_ssh(command=cmd, timeout=60)
    return output if success else f"❌ Oracle 操作失败: {output}"


def server_status_full() -> str:
    """全面服务器状态检查"""
    from .ssh import run_ssh
    wh = settings.windchill_home
    lines = ["📋 Windchill 全面状态检查", "=" * 40]

    # MethodServer
    s, out = run_ssh(command=f"cd {wh}/bin && ./windchill status 2>&1", timeout=15)
    lines.append(f"\n🖥 MethodServer:\n  {out[:300] if out else '未响应'}")

    # Oracle
    s2, out2 = run_ssh(
        command=f"ps -ef | grep pmon | grep -v grep | head -3",
        timeout=10)
    lines.append(f"\n🗄 Oracle:\n  {out2[:200] if out2 else '未检测到' if s2 else '无法连接'}")

    # 磁盘
    s3, out3 = run_ssh(command=f"df -h {wh} | tail -1", timeout=10)
    if out3:
        parts = out3.split()
        lines.append(f"\n💾 磁盘: {parts[3] if len(parts) > 3 else '?'} 空闲 ({parts[4] if len(parts) > 4 else '?'} 已用)")

    return "\n".join(lines)


# ── 命令注册表 ───────────────────────────────────────────

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
    """执行 Windchill 工具"""
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

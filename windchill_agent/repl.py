"""Windchill Agent REPL — 跨平台交互终端（Windows/Mac/Linux）"""

import os
import shlex
import sys
import time
from typing import Optional

from .config import settings
from .windchill import TOOLS, TOOL_ALIASES, execute as windchill_execute
from .kb import kb as knowledge_base

try:
    from colorama import init, Fore, Style, Back
    init()
except ImportError:
    # Fallback: no color
    class Fore:
        CYAN = GREEN = YELLOW = RED = BLUE = MAGENTA = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""
    class Back:
        RESET = ""


C = Fore  # color shortcuts
S = Style


# ── 帮助信息 ──────────────────────────────────────────────

HELP_TEXT = f"""
{C.CYAN}Windchill Agent v1.0 — 54 个工具 · 跨平台 Windchill/Oracle 运维{S.RESET_ALL}
{'=' * 60}

{Style.BRIGHT}查询类 (15):{S.RESET_ALL}
  {C.GREEN}status                          {S.RESET_ALL}服务器状态
  {C.GREEN}full_status                     {S.RESET_ALL}全面检查(MS+Oracle+磁盘)
  {C.GREEN}part <编码>{S.RESET_ALL}                    按编码查零件
  {C.GREEN}parts{S.RESET_ALL}                          最近零件列表
  {C.GREEN}query_by_name <名称>{S.RESET_ALL}            按名称查零件
  {C.GREEN}bom <编码>{S.RESET_ALL}                      查 BOM
  {C.GREEN}docs [number=编码]{S.RESET_ALL}              文档列表/搜索
  {C.GREEN}users [search=关键词]{S.RESET_ALL}           用户列表/搜索
  {C.GREEN}tasks [user=用户名]{S.RESET_ALL}             待办任务
  {C.GREEN}cr / co{S.RESET_ALL}                         变更申请 / 变更单
  {C.GREEN}logs [file_pattern=xxx]{S.RESET_ALL}         日志列表
  {C.GREEN}view_log <filename>{S.RESET_ALL}             查看日志内容
  {C.GREEN}get_parts_list{S.RESET_ALL}                  零件清单列表
  {C.GREEN}list_events{S.RESET_ALL}                     事件列表

{Style.BRIGHT}创建/修改类 (14):{S.RESET_ALL}
  {C.GREEN}create_part <编码> <名称>{S.RESET_ALL}       创建零件
  {C.GREEN}create_co / create_cr{S.RESET_ALL}           创建变更单/申请
  {C.GREEN}create_document <编码> <名称>{S.RESET_ALL}   创建文档
  {C.GREEN}add_bom_item <编码> <子件> [数量]{S.RESET_ALL} BOM 添加子件
  {C.GREEN}delete_bom_item <编码> <子件>{S.RESET_ALL}   BOM 删除子件
  {C.GREEN}revise_part / update_part <编码>{S.RESET_ALL} 修订/更新零件
  {C.GREEN}delete_part / obsolete_part <编码>{S.RESET_ALL} 删除/报废零件
  {C.GREEN}set_preference <name> <value>{S.RESET_ALL}   设置首选项

{Style.BRIGHT}审批/任务类 (5):{S.RESET_ALL}
  {C.GREEN}approve <task_id> [comment]{S.RESET_ALL}     审批任务
  {C.GREEN}reject <task_id> <原因>{S.RESET_ALL}         驳回任务
  {C.GREEN}reassign_task <task_id> <用户>{S.RESET_ALL}  转派任务
  {C.GREEN}save_workitem <task_id> [comment]{S.RESET_ALL} 保存工作项

{Style.BRIGHT}服务器管理 (9):{S.RESET_ALL}
  {C.GREEN}methodserver <status/start/stop>{S.RESET_ALL}   MethodServer 控制
  {C.GREEN}worker_agent_status{S.RESET_ALL}                Worker Agent 状态
  {C.GREEN}worker_control <action> [name] [host]{S.RESET_ALL} Worker Agent 控制
  {C.GREEN}oracle <status/tablespace>{S.RESET_ALL}         Oracle 运维
  {C.GREEN}oracle_backup <expdp/rman>{S.RESET_ALL}         Oracle 备份
  {C.GREEN}sql <SQL>{S.RESET_ALL}                          执行 Oracle SQL
  {C.GREEN}system_clone / system_rehost{S.RESET_ALL}       系统克隆/迁移
  {C.GREEN}add_worker <name> <host>{S.RESET_ALL}           添加工作器

{Style.BRIGHT}XML 生成 (4):{S.RESET_ALL}
  {C.GREEN}generate_type_xml / generate_class_xml{S.RESET_ALL}   类型/分类 XML
  {C.GREEN}generate_lifecycle_xml / generate_oir_xml{S.RESET_ALL} 生命周期/OIR XML

{Style.BRIGHT}其他:{S.RESET_ALL}
  {C.GREEN}wecom <content>{S.RESET_ALL}                    发送企业微信消息
  {C.GREEN}config{S.RESET_ALL}                             查看配置（含OS类型）
  {C.GREEN}ask <问题>{S.RESET_ALL}                          智能问答（RAG + DeepSeek）
  {C.GREEN}search <关键词>{S.RESET_ALL}                      搜索操作文档
  {C.GREEN}kb_build{S.RESET_ALL}                            构建/更新知识库索引
  {C.GREEN}docs{S.RESET_ALL}                               打开操作文档目录
  {C.GREEN}help / exit{S.RESET_ALL}                        帮助 / 退出
  {Style.DIM}所有命令支持简写: query_by_name → query_by_name 或 query_by_name{S.RESET_ALL}

{Style.DIM}示例:
  part NRV-SV-01-P01-01015          查零件
  bom NRV-SV-01-P01-01015           查 BOM
  create_part A-001 测试零件         创建零件
  add_bom_item A-001 B-001 qty=2    BOM 添加子件
  oracle tablespace                 查看表空间
  worker_agent_status               查看 Worker 状态
  methodserver restart              重启 MethodServer
  system_clone output_dir=/tmp      克隆系统{S.RESET_ALL}
"""


def parse_input(text: str) -> tuple:
    """解析用户输入为 (命令, 参数字典)"""
    text = text.strip()
    if not text:
        return ("", {})

    parts = shlex.split(text)
    cmd = parts[0].lower()
    args = parts[1:]

    params = {}
    # 解析 key=value 参数
    remaining = []
    for arg in args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            params[k] = v
        else:
            remaining.append(arg)

    # 剩余参数按位置匹配
    if cmd in ("ask", "query", "问题"):
        if remaining:
            params["keyword"] = " ".join(remaining)
    elif cmd == "search":
        if remaining:
            params["keyword"] = " ".join(remaining)
    elif cmd in ("part", "bom", "number"):
        if remaining:
            params["number"] = remaining[0]
    elif cmd == "sql":
        if remaining:
            params["sql"] = " ".join(remaining)
    elif cmd in ("approve", "reject"):
        if remaining:
            params["task_id"] = remaining[0]
        if len(remaining) > 1 and cmd == "reject":
            params["comment"] = " ".join(remaining[1:])
    elif cmd in ("methodserver", "oracle"):
        if remaining:
            params["action"] = remaining[0]
    elif cmd in ("users", "docs", "tasks"):
        if remaining:
            params["search"] = remaining[0]

    return (cmd, params)


def execute_command(cmd: str, params: dict) -> Optional[str]:
    """执行命令"""
    if cmd in ("exit", "quit"):
        print(f"{C.CYAN}👋 再见!{S.RESET_ALL}")
        sys.exit(0)

    if cmd in ("help", "?"):
        print(HELP_TEXT)
        return None

    if cmd == "config":
        print(settings.summary())
        return None
        docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
        keyword = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else params.get("keyword", params.get("text", ""))
        if not keyword:
            keyword = params.get("keyword", params.get("text", ""))
        if not keyword:
            print(f"{C.YELLOW}需要搜索关键词，示例: search 集群安装{S.RESET_ALL}")
            return None
        if os.path.exists(docs_dir):
            import glob, subprocess
            files = glob.glob(os.path.join(docs_dir, "*.md"))
            results = []
            for f in files:
                r = subprocess.run(["grep", "-n", "-i", keyword, f], capture_output=True, text=True, timeout=5)
                if r.stdout.strip():
                    fname = os.path.basename(f).replace(".md", "")
                    for line in r.stdout.strip().split("\n"):
                        results.append(f"  📄 {fname}:{line}")
            if results:
                print(f"{C.GREEN}🔍 找到 {len(results)} 处匹配「{keyword}」:{S.RESET_ALL}")
                print("\n".join(results[:30]))
                if len(results) > 30:
                    print(f"  ... 还有 {len(results)-30} 处")
            else:
                print(f"{C.YELLOW}❌ 未找到「{keyword}」相关文档{S.RESET_ALL}")
        else:
            print(f"{C.YELLOW}📚 docs/ 目录不存在{S.RESET_ALL}")
        return None

    if cmd in ("kb_build", "build_kb", "rebuild"):
        print(f"{C.CYAN}📚 正在构建知识库...{S.RESET_ALL}")
        result = knowledge_base.build()
        print(result)
        return None

    if cmd in ("ask", "query", "问题"):
        question = params.get("keyword", params.get("text", ""))
        if not question:
            question = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        if not question:
            print(f"{C.YELLOW}请输入问题，如: ask BOM 怎么搭建{S.RESET_ALL}")
            return None
        print(f"{C.CYAN}🤔 思考中...{S.RESET_ALL}")
        result = knowledge_base.ask(question)
        print(result)
        return None

    if cmd == "search":
        docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
        keyword = params.get("keyword", params.get("text", ""))
        if not keyword and params.get("", ""):
            keyword = list(params.values())[0]
        if not keyword:
            print(f"{C.YELLOW}需要搜索关键词{S.RESET_ALL}")
            return None
        if os.path.exists(docs_dir):
            import glob, subprocess as _sp
            files = glob.glob(os.path.join(docs_dir, "*.md"))
            results = []
            for f in files:
                r = _sp.run(["grep", "-n", "-i", keyword, f], capture_output=True, text=True, timeout=5)
                if r.stdout.strip():
                    fname = os.path.basename(f).replace(".md", "")
                    for line in r.stdout.strip().split("\n"):
                        results.append(f"  📄 {fname}:{line}")
            if results:
                print(f"{C.GREEN}🔍 找到 {len(results)} 处匹配「{keyword}」:{S.RESET_ALL}")
                print("\n".join(results[:40]))
            else:
                print(f"{C.YELLOW}❌ 文档中未找到「{keyword}」{S.RESET_ALL}")
        else:
            print(f"{C.YELLOW}docs/ 目录不存在{S.RESET_ALL}")
        return None

    if cmd == "docs":
        docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
        if os.path.exists(docs_dir):
            print(f"{C.CYAN}📚 操作文档目录: {docs_dir}{S.RESET_ALL}")
            import glob
            for f in sorted(glob.glob(os.path.join(docs_dir, "*.md"))):
                name = os.path.basename(f).replace(".md", "")
                print(f"  📄 {name}")
            print(f"\n{Style.DIM}用 open 命令打开: open docs/{os.listdir(docs_dir)[0] if os.listdir(docs_dir) else ''}{S.RESET_ALL}")
        else:
            print(f"{C.YELLOW}📚 docs/ 目录不存在{S.RESET_ALL}")
        return None

    if cmd == "windchill":
        # 兼容 mac-agent 格式: windchill part number=xxx
        sub_cmd = params.get("keyword", params.get("action", ""))
        if sub_cmd:
            return windchill_execute(sub_cmd, **{k: v for k, v in params.items() if k not in ("keyword", "action")})
        return windchill_execute("status")

    # 直接命令
    if cmd in TOOLS or cmd in TOOL_ALIASES:
        return windchill_execute(cmd, **params)

    if cmd in settings.__dict__:
        return f"  {cmd} = {getattr(settings, cmd)}"

    return f"❌ 未知命令: {cmd}\n输入 help 查看帮助"


def main():
    os_icon = {"macos": "🍎", "windows": "🪟", "linux": "🐧"}.get(settings.os_type, "💻")
    print(f"{C.CYAN}{Style.BRIGHT}Windchill Agent{S.RESET_ALL} {Style.DIM}v1.0{S.RESET_ALL}")
    print(f"{Style.DIM}{os_icon} {settings.os_type} | 输入 help 查看帮助, exit 退出{S.RESET_ALL}")
    print()

    if not settings.is_windchill_configured:
        print(f"{C.YELLOW}⚠ Windchill 未配置{S.RESET_ALL}")
        print(f"{Style.DIM}  请设置 .env 文件或环境变量:")
        print(f"  WINDCHILL_HOST, WINDCHILL_ODATA_USER, WINDCHILL_ODATA_PASSWORD{S.RESET_ALL}")
        print()

    # 单条命令模式
    if len(sys.argv) > 1:
        cmd, params = parse_input(" ".join(sys.argv[1:]))
        result = execute_command(cmd, params)
        if result:
            print(result)
        return

    # 交互模式
    while True:
        try:
            text = input(f"{C.CYAN}› {S.RESET_ALL}").strip()
            if not text:
                continue
            cmd, params = parse_input(text)
            start = time.time()
            result = execute_command(cmd, params)
            if result:
                print(result)
                elapsed = time.time() - start
                print(f"{Style.DIM}⏱ {elapsed:.1f}s{S.RESET_ALL}")
            print()
        except KeyboardInterrupt:
            print(f"\n{C.CYAN}👋 再见!{S.RESET_ALL}")
            break
        except EOFError:
            print()
            break
        except Exception as e:
            print(f"{C.RED}❌ 错误: {e}{S.RESET_ALL}")


if __name__ == "__main__":
    main()

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
{C.CYAN}Windchill Agent v1.0 -- SSH 运维工具 . 10 个核心命令{S.RESET_ALL}
{"=" * 60}

{Style.BRIGHT}服务器管理:{S.RESET_ALL}
  {C.GREEN}methodserver <status/start/stop>{S.RESET_ALL}    MethodServer 控制
  {C.GREEN}oracle <status/tablespace>{S.RESET_ALL}          Oracle 运维
  {C.GREEN}sql <SQL>{S.RESET_ALL}                           执行 Oracle SQL
  {C.GREEN}full_status{S.RESET_ALL}                         全面状态(MS+Oracle+磁盘)
  {C.GREEN}logs [file_pattern=xxx]{S.RESET_ALL}             查询日志列表
  {C.GREEN}view_log <filename>{S.RESET_ALL}                 查看日志内容

{Style.BRIGHT}其他:{S.RESET_ALL}
  {C.GREEN}wecom <content>{S.RESET_ALL}                     发送企业微信消息
  {C.GREEN}ask <问题>{S.RESET_ALL}                          智能问答（RAG + DeepSeek）
  {C.GREEN}kb_build{S.RESET_ALL}                            构建/更新知识库索引
  {C.GREEN}config{S.RESET_ALL}                              查看配置
  {C.GREEN}help / exit{S.RESET_ALL}                         帮助 / 退出

{Style.DIM}所有操作基于 SSH，无需 OData API。
单条命令模式:
  windchill methodserver status        查 MethodServer 状态
  windchill oracle status              查 Oracle 状态
  windchill sql "SELECT * FROM..."      执行 SQL
  windchill logs file_pattern=Method   查日志

交互模式直接输入命令:
  methodserver restart
  oracle tablespace{S.RESET_ALL}
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
        params.pop("action", None)
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

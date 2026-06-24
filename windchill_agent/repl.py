"""Windchill Agent REPL — 跨平台交互终端（Windows/Mac/Linux）"""

import os
import shlex
import sys
import time
from typing import Optional

from .config import settings
from .windchill import TOOLS, TOOL_ALIASES, execute as windchill_execute

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
{C.CYAN}Windchill Agent — 跨平台 Windchill/Oracle 运维工具{S.RESET_ALL}
{'=' * 50}

{Style.BRIGHT}Windchill 操作:{S.RESET_ALL}
  {C.GREEN}status{S.RESET_ALL}                检查 Windchill 服务器状态
  {C.GREEN}full_status{S.RESET_ALL}           全面服务器检查（MS+Oracle+磁盘）
  {C.GREEN}part <编码>{S.RESET_ALL}            按物料编码查询零件
  {C.GREEN}parts{S.RESET_ALL}                 最近零件列表
  {C.GREEN}bom <编码>{S.RESET_ALL}            查询 BOM
  {C.GREEN}docs{S.RESET_ALL}                  文档列表
  {C.GREEN}users{S.RESET_ALL}                 用户列表
  {C.GREEN}tasks{S.RESET_ALL}                 待办任务
  {C.GREEN}cr{S.RESET_ALL}                    变更申请
  {C.GREEN}co{S.RESET_ALL}                    变更单

{Style.BRIGHT}服务器管理:{S.RESET_ALL}
  {C.GREEN}methodserver <status/start/stop>{S.RESET_ALL}  MethodServer 控制
  {C.GREEN}oracle <status/tablespace>{S.RESET_ALL}        Oracle 运维
  {C.GREEN}sql <SQL>{S.RESET_ALL}             执行 Oracle SQL
  {C.GREEN}logs [file_pattern=xxx]{S.RESET_ALL}  查询日志列表
  {C.GREEN}view_log <filename>{S.RESET_ALL}      查看日志内容

{Style.BRIGHT}审批操作:{S.RESET_ALL}
  {C.GREEN}approve <task_id>{S.RESET_ALL}      审批任务
  {C.GREEN}reject <task_id> <原因>{S.RESET_ALL} 驳回任务

{Style.BRIGHT}其他:{S.RESET_ALL}
  {C.GREEN}wecom <content>{S.RESET_ALL}        发送企业微信消息
  {C.GREEN}docs{S.RESET_ALL}                  打开操作文档目录

{Style.BRIGHT}系统:{S.RESET_ALL}
  {C.GREEN}config{S.RESET_ALL}                查看配置（含OS类型）
  {C.GREEN}help{S.RESET_ALL}                  显示帮助
  {C.GREEN}exit/quit{S.RESET_ALL}             退出

{Style.DIM}示例:
  part NRV-SV-01-P01-01015    查零件
  bom NRV-SV-01-P01-01015     查 BOM
  oracle tablespace           查看表空间
  sql SELECT * FROM...        执行 SQL
  methodserver restart        重启 MethodServer{S.RESET_ALL}
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
    if cmd in ("part", "bom", "number"):
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

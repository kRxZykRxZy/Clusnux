"""
Interactive admin/setup console using curses (no Tkinter, no static HTML).
Blue-themed dashboard inspired by container UIs: server list, metrics placeholders,
command runner, heartbeat, and orchestrator load-balancer view.
"""

import asyncio
import curses
import json
from dataclasses import dataclass, field
from typing import Dict, Optional

import websockets


@dataclass
class NodeInfo:
    ws_url: str
    node_id: str = "unknown"
    role: str = "unknown"
    private_ip: str = ""
    last_seen: float = 0.0


@dataclass
class AppState:
    ws_url: str = "ws://127.0.0.1:8734"
    role: str = "admin"
    status: str = "disconnected"
    log: list[str] = field(default_factory=list)
    ws: Optional[websockets.WebSocketClientProtocol] = None
    nodes: Dict[str, NodeInfo] = field(default_factory=dict)
    active_node: Optional[str] = None  # ws_url of active node


async def send_json(ws, payload):
    await ws.send(json.dumps(payload))


async def recv_loop(state: AppState, log_lines: int = 400):
    try:
        async for message in state.ws:
            state.log.append(message)
            state.log = state.log[-log_lines:]
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue
            if data.get("task") == "heartbeat":
                ws_url = data.get("ws_url") or state.ws_url
                node_id = data.get("node_id", "unknown")
                node = NodeInfo(
                    ws_url=ws_url,
                    node_id=node_id,
                    role=data.get("role", "unknown"),
                    private_ip=data.get("private_ip", ""),
                    last_seen=data.get("ts", 0.0),
                )
                state.nodes[ws_url] = node
                if not state.active_node:
                    state.active_node = ws_url
    except Exception as exc:  # noqa: BLE001
        state.log.append(f"[error] receive loop: {exc}")
        state.status = "error"


async def connect(state: AppState):
    if state.ws:
        await state.ws.close()
    state.status = "connecting"
    state.ws = await websockets.connect(state.ws_url)
    state.status = f"connected as {state.role}"
    state.active_node = state.ws_url
    asyncio.create_task(recv_loop(state))


async def send_heartbeat(state: AppState):
    if not state.ws:
        state.log.append("[warn] not connected")
        return
    await send_json(state.ws, {"task": "heartbeat", "role": state.role})
    state.log.append("[>] heartbeat sent")


async def send_cmd(state: AppState, cmd: str):
    if not state.ws:
        state.log.append("[warn] not connected")
        return
    await send_json(state.ws, {"task": "cmd", "command": cmd, "role": state.role})
    state.log.append(f"[>] cmd sent: {cmd}")


def _draw_panel(stdscr, y, x, w, title, content_lines, color_pair=0):
    stdscr.attron(curses.color_pair(color_pair))
    stdscr.addstr(y, x, title[: w - 1], curses.A_BOLD)
    for idx, line in enumerate(content_lines, start=1):
        if y + idx >= curses.LINES:
            break
        stdscr.addstr(y + idx, x, line[: w - 1])
    stdscr.attroff(curses.color_pair(color_pair))


def _bar(value: float, width: int = 20) -> str:
    value = max(0.0, min(1.0, value))
    filled = int(value * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def draw(stdscr, state: AppState, cmd_buffer: str):
    stdscr.clear()
    max_y, max_x = stdscr.getmaxyx()

    header = f"Clusnux Admin Dashboard | Role: {state.role} | Status: {state.status}"
    stdscr.attron(curses.color_pair(2))
    stdscr.addstr(0, 0, header[: max_x - 1], curses.A_BOLD)
    stdscr.attroff(curses.color_pair(2))
    stdscr.addstr(1, 0, f"WS: {state.ws_url}"[: max_x - 1], curses.A_DIM)
    stdscr.addstr(2, 0, "Keys: [c] connect  [h] heartbeat  [r] toggle role  [l] next discovered  [b] balancer view  [q] quit", curses.A_DIM)

    left_w = max_x // 3
    right_w = max_x - left_w - 1

    # Server list
    nodes_lines = []
    for ws_url, node in sorted(state.nodes.items()):
        marker = ">" if ws_url == state.active_node else " "
        nodes_lines.append(f"{marker} {node.node_id} ({node.role})")
        nodes_lines.append(f"    {node.private_ip} | {ws_url}")
    if not nodes_lines:
        nodes_lines = ["No heartbeats yet.", "Press h to query current node."]
    _draw_panel(stdscr, 4, 0, left_w, "Servers", nodes_lines, color_pair=1)

    # Metrics / graphs placeholder
    graph_lines = [
        "CPU : " + _bar(0.2, width=24) + " (placeholder)",
        "MEM : " + _bar(0.4, width=24) + " (placeholder)",
        "NET : " + _bar(0.1, width=24) + " (placeholder)",
        "Note: metrics route not implemented; heartbeat only.",
    ]
    _draw_panel(stdscr, 4, left_w + 1, right_w, "Graphs", graph_lines, color_pair=3)

    # Load balancer / orchestrator view
    lb_lines = []
    if state.role == "orchestrator":
        targets = list(state.nodes.keys())
        if targets:
            lb_lines.append(f"Discovered targets: {len(targets)}")
            for idx, ws in enumerate(targets[:5], start=1):
                lb_lines.append(f"{idx}. {ws}")
        else:
            lb_lines.append("No targets discovered yet.")
        lb_lines.append("Orchestrators act as load balancers; rotate [l] to next.")
    else:
        lb_lines.append("Switch to role 'orchestrator' to manage balancing.")
    _draw_panel(stdscr, 11, left_w + 1, right_w, "Load Balancer", lb_lines, color_pair=4)

    # Command input
    stdscr.attron(curses.color_pair(2))
    stdscr.addstr(max_y - 4, 0, "Command:", curses.A_BOLD)
    stdscr.attroff(curses.color_pair(2))
    stdscr.addstr(max_y - 3, 0, cmd_buffer[: max_x - 1])

    # Log
    log_height = max_y - 15
    log_lines = state.log[-log_height:] if log_height > 0 else []
    _draw_panel(stdscr, max_y - log_height - 6, 0, max_x, "Events", log_lines, color_pair=0)

    stdscr.refresh()


async def tui_main(stdscr):
    curses.curs_set(1)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)   # server list
    curses.init_pair(2, curses.COLOR_BLUE, -1)   # header / command
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)  # graphs
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN)  # balancer

    state = AppState()
    cmd_buffer = ""
    balancer_index = 0
    while True:
        draw(stdscr, state, cmd_buffer)
        ch = stdscr.getch()
        if ch in (curses.KEY_EXIT, ord("q")):
            break
        if ch == ord("c"):
            await connect(state)
        elif ch == ord("h"):
            await send_heartbeat(state)
        elif ch == ord("r"):
            state.role = "orchestrator" if state.role == "admin" else "admin"
            state.status = f"mode={state.role}"
        elif ch == ord("l"):
            targets = list(state.nodes.keys())
            if targets:
                balancer_index = (balancer_index + 1) % len(targets)
                state.ws_url = targets[balancer_index]
                state.status = f"selected {state.ws_url}"
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            cmd_buffer = cmd_buffer[:-1]
        elif ch == curses.KEY_ENTER or ch == 10 or ch == 13:
            if cmd_buffer.strip():
                await send_cmd(state, cmd_buffer.strip())
                cmd_buffer = ""
        elif 32 <= ch <= 126:
            cmd_buffer += chr(ch)
    if state.ws:
        await state.ws.close()


def run():
    asyncio.run(curses.wrapper(tui_main))


if __name__ == "__main__":
    run()

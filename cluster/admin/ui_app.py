"""
Interactive TUI for admin/setup roles (no Tkinter, no static HTML).
Uses curses to render a minimal but styled UI for sending heartbeat and cmd tasks
over the WebSocket control plane.
"""

import asyncio
import curses
import json
from dataclasses import dataclass
from typing import Optional

import websockets


@dataclass
class AppState:
    ws_url: str = "ws://127.0.0.1:8734"
    role: str = "admin"
    status: str = "disconnected"
    log: list[str] = None
    ws: Optional[websockets.WebSocketClientProtocol] = None

    def __post_init__(self):
        if self.log is None:
            self.log = []


async def send_json(ws, payload):
    await ws.send(json.dumps(payload))


async def recv_loop(state: AppState, log_lines: int = 200):
    try:
        async for message in state.ws:
            state.log.append(message)
            state.log = state.log[-log_lines:]
    except Exception as exc:  # noqa: BLE001
        state.log.append(f"[error] receive loop: {exc}")
        state.status = "error"


async def connect(state: AppState):
    if state.ws:
        await state.ws.close()
    state.status = "connecting"
    state.ws = await websockets.connect(state.ws_url)
    state.status = f"connected as {state.role}"
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


def draw(stdscr, state: AppState, cmd_buffer: str):
    stdscr.clear()
    max_y, max_x = stdscr.getmaxyx()
    header = f"Clusnux Admin/Setup UI | Role: {state.role} | Status: {state.status}"
    stdscr.addstr(0, 0, header[: max_x - 1], curses.A_BOLD)
    stdscr.addstr(2, 0, f"WebSocket: {state.ws_url}"[: max_x - 1])
    stdscr.addstr(3, 0, "Commands: [c] connect  [h] heartbeat  [r] toggle role  [q] quit", curses.A_DIM)
    stdscr.addstr(5, 0, "Command input:", curses.A_BOLD)
    stdscr.addstr(6, 0, cmd_buffer[: max_x - 1])

    stdscr.addstr(8, 0, "Log:", curses.A_BOLD)
    log_start = 9
    for idx, line in enumerate(state.log[-(max_y - log_start - 1) :], start=log_start):
        stdscr.addstr(idx, 0, line[: max_x - 1])

    stdscr.refresh()


async def tui_main(stdscr):
    curses.curs_set(1)
    state = AppState()
    cmd_buffer = ""
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
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            cmd_buffer = cmd_buffer[:-1]
        elif ch == curses.KEY_ENTER or ch == 10 or ch == 13:
            if cmd_buffer.strip():
                await send_cmd(state, cmd_buffer.strip())
                cmd_buffer = ""
        elif ch >= 32 and ch <= 126:
            cmd_buffer += chr(ch)
    if state.ws:
        await state.ws.close()


def run():
    asyncio.run(curses.wrapper(tui_main))


if __name__ == "__main__":
    run()

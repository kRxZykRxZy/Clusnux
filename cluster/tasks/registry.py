import asyncio
from typing import Dict

# Global registry of running async subprocesses keyed by PID
running_commands: Dict[int, asyncio.subprocess.Process] = {}


def register_process(pid: int, process: asyncio.subprocess.Process) -> None:
    running_commands[pid] = process


def pop_process(pid: int) -> asyncio.subprocess.Process | None:
    return running_commands.pop(pid, None)


def get_process(pid: int) -> asyncio.subprocess.Process | None:
    return running_commands.get(pid)


def list_processes() -> Dict[int, str]:
    return {pid: "running" for pid in running_commands.keys()}


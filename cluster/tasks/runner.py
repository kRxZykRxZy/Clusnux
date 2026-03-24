import asyncio
import shlex
import json
import logging
from cluster.tasks import registry


logger = logging.getLogger(__name__)


async def run_command(cmd: str, websocket):
    """Run a command and stream output/events over WebSocket."""
    args = shlex.split(cmd)
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    pid = process.pid
    registry.register_process(pid, process)

    await websocket.send(json.dumps({
        "task": "cmd_started",
        "pid": pid,
        "command": cmd
    }))

    try:
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await websocket.send(json.dumps({
                "task": "cmd_output",
                "pid": pid,
                "output": line.decode().rstrip()
            }))
        await process.wait()
        await websocket.send(json.dumps({
            "task": "cmd_complete",
            "pid": pid,
            "returncode": process.returncode
        }))
    except Exception as exc:
        logger.exception("Command execution failed")
        await websocket.send(json.dumps({
            "task": "cmd_error",
            "pid": pid,
            "error": "command_failed",
            "detail": str(exc)
        }))
    finally:
        registry.pop_process(pid)


async def stop_command(pid: int, websocket):
    process = registry.get_process(pid)
    await websocket.send(json.dumps({
        "task": "stop_ack",
        "pid": pid
    }))
    if not process:
        await websocket.send(json.dumps({
            "task": "stop_result",
            "pid": pid,
            "status": "not_found"
        }))
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
        status = "terminated"
    except asyncio.TimeoutError:
        process.kill()
        status = "killed"
    registry.pop_process(pid)
    await websocket.send(json.dumps({
        "task": "stop_result",
        "pid": pid,
        "status": status,
        "returncode": process.returncode
    }))

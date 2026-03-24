import shlex
import subprocess
import asyncio
import json
import psutil

# Keep track of running commands if needed
running_commands = {}  # pid -> process object


async def handle_request(data, websocket):
    """
    Handles requests sent to the current node over WebSocket.
    Supports streaming command output with PID and sending node metrics.
    """
    task = data.get("task")

    if task == "cmd":
        cmd = data.get("command")
        client_ip, client_port = websocket.remote_address
        print(f"[>] Running terminal command from {client_ip}:{client_port} -> {cmd}")

        args = shlex.split(cmd)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        pid = process.pid
        running_commands[pid] = process

        # Send PID back to the master
        await websocket.send(json.dumps({
            "task": "cmd_started",
            "pid": pid,
            "command": cmd
        }))

        try:
            # Stream stdout line by line
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
        except Exception as e:
            await websocket.send(json.dumps({
                "task": "cmd_error",
                "pid": pid,
                "error": str(e)
            }))
        finally:
            running_commands.pop(pid, None)

    elif task == "metrics":
        # Send CPU, memory, disk, and network stats
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()._asdict()
        disk = psutil.disk_usage('/')._asdict()
        net = psutil.net_io_counters(pernic=True)

        await websocket.send(json.dumps({
            "task": "metrics",
            "cpu_percent": cpu,
            "memory": mem,
            "disk": disk,
            "network": {k: v._asdict() for k, v in net.items()}
        }))

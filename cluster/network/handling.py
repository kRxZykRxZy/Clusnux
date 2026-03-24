import asyncio
import json
import logging
import time
from cluster.tasks.runner import run_command, stop_command
from cluster.tasks import registry
from cluster.metrics.system import collect_system_metrics
from cluster.admin.control import perform_action
from cluster.docker.runtime import run_container
from cluster.config.loader import load_config

logger = logging.getLogger(__name__)


async def handle_request(data, websocket):
    """
    Handles requests sent to the current node over WebSocket.
    Supports streaming command output with PID, metrics, and control actions.
    """
    task = data.get("task")

    if task == "cmd":
        cmd = data.get("command")
        if not cmd:
            await websocket.send(json.dumps({"status": "error", "code": "missing_command"}))
            return
        client_ip, client_port = websocket.remote_address
        logger.info("Running command from %s:%s -> %s", client_ip, client_port, cmd)
        await run_command(cmd, websocket)

    elif task == "stop":
        pid = data.get("pid")
        if pid is None:
            await websocket.send(json.dumps({"status": "error", "code": "missing_pid"}))
            return
        await stop_command(pid, websocket)

    elif task == "metrics":
        await websocket.send(json.dumps(collect_system_metrics()))

    elif task == "heartbeat":
        config = load_config()
        await websocket.send(json.dumps({
            "task": "heartbeat",
            "status": "ok",
            "node_id": config.get("node_id"),
            "ts": time.time()
        }))

    elif task == "docker_run":
        await run_container(data, websocket)

    elif task == "tasks":
        await websocket.send(json.dumps({
            "task": "tasks",
            "running": registry.list_processes()
        }))

    elif task == "admin_control":
        action = data.get("action")
        result = perform_action(action, data.get("reason"))
        await websocket.send(json.dumps({
            "task": "admin_control",
            **result
        }))

    else:
        await websocket.send(json.dumps({"status": "unsupported_task"}))

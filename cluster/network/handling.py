import asyncio
import json
import logging
import time
from cluster.tasks.runner import run_command, stop_command
from cluster.tasks import registry
from cluster.metrics.system import collect_system_metrics
from cluster.admin.control import perform_action
from cluster.docker.runtime import run_container
from cluster.config.loader import load_config, ALLOWED_ROLES

# Role-based capabilities for WS tasks (kept centralized for clarity/testing).
ROLE_CAPS = {
    "admin": {"cmd", "stop", "metrics", "heartbeat", "docker_run", "tasks", "admin_control"},
    "orchestrator": {"cmd", "stop", "metrics", "heartbeat", "tasks"},
    "cluster": {"heartbeat"},
}

logger = logging.getLogger(__name__)


async def handle_request(data, websocket):
    """
    Handles requests sent to the current node over WebSocket.
    Supports streaming command output with PID, metrics, and control actions.
    """
    task = data.get("task")
    config = load_config()
    role = (data.get("role") or "").lower() or config.get("role", "cluster")

    if role not in ALLOWED_ROLES:
        await websocket.send(json.dumps({"status": "error", "code": "unauthorized_role"}))
        logger.warning("Rejected request with invalid role: %s", role)
        return

    if task not in ROLE_CAPS.get(role, set()):
        await websocket.send(json.dumps({"status": "error", "code": "forbidden", "role": role, "task": task}))
        logger.warning("Forbidden task=%s for role=%s", task, role)
        return

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
        await websocket.send(json.dumps({
            "task": "heartbeat",
            "status": "ok",
            "node_id": config.get("node_id"),
            "role": config.get("role"),
            "private_ip": config.get("advertise_ip"),
            "ws_url": f"ws://{config.get('advertise_ip')}:{config.get('port')}",
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

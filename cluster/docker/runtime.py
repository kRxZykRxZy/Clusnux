import asyncio
import json
import logging
import uuid
from typing import Dict

logger = logging.getLogger(__name__)


async def run_container(request: Dict, websocket):
    """
    Placeholder for container execution. Emits started + error to keep contract stable.
    """
    image = request.get("image")
    container_id = f"stub-{uuid.uuid4().hex[:8]}"
    await websocket.send(json.dumps({
        "task": "docker_started",
        "container_id": container_id,
        "image": image
    }))
    # In a real implementation, docker SDK calls would go here.
    await asyncio.sleep(0)
    await websocket.send(json.dumps({
        "task": "docker_error",
        "container_id": container_id,
        "error": "not_implemented"
    }))

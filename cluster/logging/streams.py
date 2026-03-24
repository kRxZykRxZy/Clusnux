import json
from typing import AsyncIterator


async def stream_lines(websocket, iterator: AsyncIterator[str], task: str, **kwargs):
    """Utility to stream log lines over websocket with consistent payload shape."""
    async for line in iterator:
        payload = {"task": task, "line": line.rstrip()}
        payload.update(kwargs)
        await websocket.send(json.dumps(payload))


import asyncio
import json
import logging
import websockets
from cluster.network.handling import handle_request

logger = logging.getLogger(__name__)


class WebSocketServer:
    """ The main websocket control system that handles all requests from administrators or orchestring servers. """

    def __init__(self, host="0.0.0.0", port=8734):
        self.host = host
        self.port = port
        self.connected_nodes = set()  # Keep track of connected clients

    async def handler(self, websocket, path):
        """ Handle incoming messages from clients (master). """
        print(f"[+] Node connected: {websocket.remote_address}")
        self.connected_nodes.add(websocket)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.info("[>] Received command: %s", data)
                    await handle_request(data, websocket)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({"status": "invalid_json"}))
                except Exception as exc:
                    logger.exception("Unhandled error during handling")
                    await websocket.send(json.dumps({
                        "status": "error",
                        "code": "internal_error"
                    }))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_nodes.remove(websocket)
            print(f"[-] Control Server disconnected: {websocket.remote_address}")

    def run(self):
        """ Start the WebSocket server. """
        print(f"[*] Starting WebSocket server on {self.host}:{self.port}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            websockets.serve(self.handler, self.host, self.port)
        )
        loop.run_forever()

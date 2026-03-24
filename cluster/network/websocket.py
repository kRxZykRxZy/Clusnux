import asyncio
import json
import websockets
from handling import handle_request

class server:
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
                    print(f"[>] Received command: {data}")
                    handle_request(data, websocket)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({"status": "invalid_json"}))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_nodes.remove(websocket)
            print(f"[-] Control Server disconnected: {websocket.remote_address}")

    def run(self):
        """ Start the WebSocket server. """
        print(f"[*] Starting WebSocket server on {self.host}:{self.port}")
        asyncio.get_event_loop().run_until_complete(
            websockets.serve(self.handler, self.host, self.port)
        )
        asyncio.get_event_loop().run_forever()

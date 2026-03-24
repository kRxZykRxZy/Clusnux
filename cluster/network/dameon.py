import threading
import time
import json
import subprocess
from cluster.network.websocket import WebSocketServer

class ClusterDaemon:
    """ Network Daemon worker that runs a WebSocket server and handles HTTP-Requested cluster tasks. """

    def __init__(self, host="0.0.0.0", port=8734):
        self.host = host
        self.port = port
        self.ws_thread = None

    def start_websocket_server(self):
        """ Starts the WebSocket server in a separate thread. """
        try:
            print(f"[*] Starting WebSocket server on {self.host}:{self.port}")
            ws_server = WebSocketServer(host=self.host, port=self.port)
            ws_server.run()
        except Exception as e:
            print(f"[!] WebSocket server failed: {e}")

    def start_daemon(self):
        """Starts the daemon with the WebSocket server as a worker."""
        self.ws_thread = threading.Thread(target=self.start_websocket_server)
        self.ws_thread.daemon = True  # Stops automatically if main program exits
        self.ws_thread.start()
        print("[*] WebSocket server thread started as daemon.")

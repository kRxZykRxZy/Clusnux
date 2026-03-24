import threading
import logging
from cluster.network.websocket import WebSocketServer
from cluster.config.loader import load_config
from cluster.logging.config import setup_logging


logger = logging.getLogger(__name__)


class DaemonService:
    """
    Manages the lifecycle of the node agent: config, logging, and WebSocket control plane.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8734):
        self.host = host
        self.port = port
        self.config = load_config()
        setup_logging(self.config.get("logging", {}))
        self.ws_thread = None

    def _run_ws(self):
        """Start the websocket server (blocking)."""
        server = WebSocketServer(host=self.host, port=self.port)
        server.run()

    def start(self):
        """Start the daemon with WS server in a background thread."""
        if self.ws_thread and self.ws_thread.is_alive():
            logger.info("WebSocket server already running on %s:%s", self.host, self.port)
            return
        logger.info("Starting WebSocket server on %s:%s", self.host, self.port)
        self.ws_thread = threading.Thread(target=self._run_ws, name="ws-thread", daemon=True)
        self.ws_thread.start()
        logger.info("WebSocket server thread started as daemon.")

    def join(self):
        """Join the websocket thread."""
        if self.ws_thread:
            self.ws_thread.join()


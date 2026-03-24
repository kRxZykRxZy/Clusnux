import threading
import logging
from cluster.network.websocket import WebSocketServer
from cluster.config.loader import load_config
from cluster.logging.config import setup_logging
from cluster.admin.ui_server import UIServer


logger = logging.getLogger(__name__)


class DaemonService:
    """
    Manages the lifecycle of the node agent: config, logging, and WebSocket control plane.
    """

    def __init__(self, host: str | None = None, port: int | None = None):
        self.config = load_config()
        self.host = host or self.config.get("host", "0.0.0.0")
        self.port = port or self.config.get("port", 8734)
        setup_logging(self.config.get("logging", {}))
        self.ws_thread = None
        self.ui_server: UIServer | None = None

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

        if self.config.get("role") == "admin":
            ui_port = self.config.get("ui_port", 8080)
            self.ui_server = UIServer(host=self.host, port=ui_port)
            self.ui_server.start()

    def join(self):
        """Join the websocket thread."""
        if self.ws_thread:
            self.ws_thread.join()

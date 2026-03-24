import functools
import logging
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class UIServer:
    """
    Lightweight static file server that hosts the admin/setup UI.
    Designed to be started only for admin role (or during initial setup).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8080, directory: Optional[Path] = None):
        self.host = host
        self.port = port
        self.directory = directory or Path(__file__).parent / "ui"
        self.httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        if self.httpd:
            logger.info("UI server already running on %s:%s", self.host, self.port)
            return

        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(self.directory))
        self.httpd = ThreadingHTTPServer((self.host, self.port), handler)

        self._thread = threading.Thread(target=self.httpd.serve_forever, name="ui-server", daemon=True)
        self._thread.start()
        logger.info("UI server started on http://%s:%s serving %s", self.host, self.port, self.directory)

    def stop(self):
        if not self.httpd:
            return
        logger.info("Stopping UI server on %s:%s", self.host, self.port)
        self.httpd.shutdown()
        self.httpd.server_close()
        self.httpd = None
        self._thread = None


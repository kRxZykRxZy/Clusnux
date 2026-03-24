import os
import socket
from typing import Dict
import socket
import contextlib

ALLOWED_ROLES = {"admin", "orchestrator", "cluster"}


def _detect_private_ip() -> str:
    """
    Attempt to detect a non-loopback private IP for advertising WS endpoints.
    Falls back to 127.0.0.1 if detection fails.
    """
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def load_config() -> Dict:
    """Load configuration from environment with sane defaults."""
    role_env = os.getenv("CLUSNUX_ROLE")
    role = (role_env.lower() if role_env else "cluster")
    if role not in ALLOWED_ROLES:
        role = "cluster"

    advertise_ip = _detect_private_ip()
    host = os.getenv("CLUSNUX_HOST", "")
    bind_host = host if host else advertise_ip if role in {"cluster", "orchestrator"} else "0.0.0.0"
    return {
        "host": bind_host or "0.0.0.0",
        "port": int(os.getenv("CLUSNUX_PORT", "8734")),
        "node_id": os.getenv("CLUSNUX_NODE_ID", socket.gethostname()),
        "role": role,
        "advertise_ip": advertise_ip,
        "ui_port": int(os.getenv("CLUSNUX_UI_PORT", "8080")),
        "logging": {},
    }

import os
import socket
from typing import Dict


def load_config() -> Dict:
    """Load configuration from environment with sane defaults."""
    return {
        "host": os.getenv("CLUSNUX_HOST", "0.0.0.0"),
        "port": int(os.getenv("CLUSNUX_PORT", "8734")),
        "node_id": os.getenv("CLUSNUX_NODE_ID", socket.gethostname()),
        "logging": {},
    }


import logging
from typing import Dict

logger = logging.getLogger(__name__)


def perform_action(action: str, reason: str | None = None) -> Dict[str, str]:
    """
    Handle privileged admin actions. This is a stub for future system hooks.
    """
    logger.info("Admin action requested: %s reason=%s", action, reason)
    if action not in {"shutdown", "restart", "upgrade"}:
        return {"status": "error", "code": "unsupported_admin_action"}
    return {"status": "ok", "action": action, "reason": reason or ""}


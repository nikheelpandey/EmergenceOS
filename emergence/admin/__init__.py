"""
Admin control plane for a live EmergenceOS kernel.

External clients (CLI, HTTP ingress) connect via a local Unix socket
to inspect and control the running runtime.
"""

from emergence.admin.client import AdminClient, AdminConnectionError
from emergence.admin.runtime_lock import RuntimeLock, RuntimeLockError
from emergence.admin.server import AdminServer

__all__ = [
    "AdminClient",
    "AdminConnectionError",
    "AdminServer",
    "RuntimeLock",
    "RuntimeLockError",
]

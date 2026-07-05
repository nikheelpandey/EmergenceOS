"""
Persistent runtime boot for EmergenceOS.

Constructs a fully wired kernel with all plugins loaded and
core platform services running. The kernel stays alive until
explicitly shut down (Ctrl+C / SIGTERM).
"""

from __future__ import annotations

from dataclasses import dataclass

from emergence.admin.runtime_lock import RuntimeLock
from emergence.admin.server import AdminServer
from emergence.core.event import Event, EventType
from emergence.ingress.http.server import HttpIngressServer, default_http_port
from emergence.kernel.boot_context import build_kernel
from emergence.kernel.kernel import Kernel


# Platform services spawned on every persistent boot.
PLATFORM_SERVICES: tuple[str, ...] = (
    "heartbeat",
    "event_collector",
    "job_worker",
)


from emergence.persistence.flush import flush_persistence


def build_runtime(*, persist: bool = True) -> Kernel:
    """
    Boot the full EmergenceOS runtime.

    - All plugins discovered and registered
    - Supervisor enabled for fault tolerance
    - Core platform services spawned and waiting
    - Kernel state records service PIDs for discovery
    """
    kernel = build_kernel(
        spawn=None,
        load_plugins=True,
        enable_supervisor=True,
        persist=persist,
    )
    ctx = kernel.context

    ctx.state.set("os:status", "booting")
    ctx.state.set("max_beats", 0)  # heartbeat runs indefinitely

    heartbeat = kernel.spawn(
        ctx.registry.get("heartbeat"),
        priority=10,
    )
    collector = kernel.spawn(
        ctx.registry.get("event_collector"),
        priority=9,
    )
    worker = kernel.spawn(
        ctx.registry.get("job_worker"),
        priority=5,
    )

    ctx.state.set("svc:heartbeat", str(heartbeat.process_id))
    ctx.state.set("svc:collector", str(collector.process_id))
    ctx.state.set("svc:worker", str(worker.process_id))
    ctx.state.set("os:status", "running")

    ctx.event_bus.publish(
        Event(
            event_type=EventType.KERNEL_STARTED,
            payload={
                "mode": "persistent",
                "services": list(PLATFORM_SERVICES),
            },
        )
    )

    return kernel


@dataclass
class RuntimeService:
    """
    Persistent runtime with admin control plane and runtime lock.
    """

    kernel: Kernel
    admin: AdminServer
    http: HttpIngressServer
    lock: RuntimeLock

    @classmethod
    def start(cls) -> RuntimeService:
        lock = RuntimeLock.create()
        lock.acquire()
        kernel = build_runtime(persist=True)
        admin = AdminServer(kernel)
        admin.start()
        http = HttpIngressServer(kernel, port=default_http_port())
        http.start()
        lock.publish_manifest(
            host=admin.host,
            port=admin.port,
            http_port=http.port,
        )
        return cls(kernel=kernel, admin=admin, http=http, lock=lock)

    def stop(self) -> None:
        flush_persistence(self.kernel.context)
        self.http.stop()
        self.admin.stop()
        self.lock.release()
        self.kernel.shutdown()

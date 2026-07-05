"""
Persistent runtime boot for EmergenceOS.

Constructs a fully wired kernel with all plugins loaded and
core platform services running. The kernel stays alive until
explicitly shut down (Ctrl+C / SIGTERM).
"""

from __future__ import annotations

from emergence.core.event import Event, EventType
from emergence.kernel.boot_context import build_kernel
from emergence.kernel.kernel import Kernel


# Platform services spawned on every persistent boot.
PLATFORM_SERVICES: tuple[str, ...] = (
    "heartbeat",
    "event_collector",
    "job_worker",
)


def build_runtime() -> Kernel:
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

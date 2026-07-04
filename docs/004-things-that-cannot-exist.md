I love this document because it forces discipline.

Most projects document what they **have**.

Very few document what they **refuse to have**.

Linux has "don't break userspace."

The Zen of Python has "There should be one, and preferably only one, obvious way to do it."

Raft explicitly rejects multiple leaders.

Those constraints are part of why those systems remain elegant.

I'd even consider this one of the foundational documents.

---

# 004 - Things That Cannot Exist

> *"A system is defined as much by the designs it rejects as by the ones it embraces."*

---

# Purpose

This document defines architectural constructs that are explicitly forbidden within EmergenceOS.

These are not implementation limitations.

They are deliberate design constraints intended to preserve the integrity, predictability, and composability of the system.

Any feature proposal that introduces one of these concepts should be reconsidered before implementation.

---

# 1. No God Process

No process may have unrestricted authority over the system.

There shall never exist a process that:

* schedules other processes
* bypasses permissions
* directly modifies kernel state
* owns every resource
* performs every cognitive task

Large processes should be decomposed into smaller, specialized processes.

The kernel coordinates.

Processes collaborate.

---

# 2. No Thinking Kernel

The kernel must never perform reasoning.

The kernel cannot:

* call an LLM
* execute prompts
* rank semantic quality
* decide plans
* choose strategies
* summarize information
* generate text

The kernel manages execution.

It never contributes intelligence.

---

# 3. No Direct Process Communication

Processes may never invoke one another directly.

Forbidden:

```text
Planner → Researcher
```

Required:

```text
Planner
    ↓
Publish Event
    ↓
Event Bus
    ↓
Research Process
```

Every interaction must be observable.

---

# 4. No Shared Mutable State

Processes may not modify shared objects.

Every mutable state has exactly one owner.

Examples:

* Process lifecycle → Kernel
* Memory → Memory Manager
* Events → Event Bus
* Tool execution → Executor

If multiple components need access, they communicate through messages rather than shared mutation.

---

# 5. No Hidden State

Every state transition must be explicit.

Forbidden:

* implicit retries
* invisible waiting
* undocumented caches
* secret flags
* magic variables

If the system changes, the kernel should know that it changed.

---

# 6. No Undocumented Side Effects

Every operation should produce only its documented effects.

A memory retrieval should not silently update memory.

Publishing an event should not unexpectedly schedule unrelated work.

State changes must always be explicit.

---

# 7. No Tool Access Outside the Executor

Processes never invoke tools directly.

Forbidden:

```python
process.run_shell(...)
```

Required:

```text
Process

↓

Executor Request

↓

Executor

↓

Shell
```

The Executor is the only component permitted to interact with external systems.

---

# 8. No Memory Access Outside the Memory Manager

Processes do not own memory.

Processes request memory.

The Memory Manager decides:

* storage
* indexing
* retrieval
* compression
* eviction

No shortcuts.

---

# 9. No Scheduler Decisions Inside Processes

Processes perform work.

They never decide:

* execution order
* priorities
* dispatch timing
* fairness

Scheduling belongs exclusively to the Scheduler.

---

# 10. No Business Logic in Infrastructure

Kernel services must remain application agnostic.

Forbidden:

```text
if process_type == "Research":
    ...
```

The kernel should never know whether a process is researching, coding, planning, or evaluating.

---

# 11. No Global Singleton State

The system should avoid mutable global variables.

All state should belong to explicit entities.

Hidden global state makes replay and testing unreliable.

---

# 12. No Implicit Permissions

Permissions are never inferred.

A process either possesses a permission or it does not.

There is no concept of:

*"probably safe."*

---

# 13. No Infinite Processes

Every process must have at least one termination condition.

Possible termination reasons include:

* completion
* timeout
* cancellation
* failure
* resource exhaustion

Long-running services are implemented as managed service processes with explicit lifecycles.

---

# 14. No Silent Failure

Failures must always produce observable events.

Forbidden:

```text
Tool failed.

Nothing happened.
```

Required:

```text
ToolFailed Event

↓

Recovery Policy

↓

Retry or Escalation
```

---

# 15. No Circular Dependencies

Dependency graphs must remain acyclic.

Forbidden:

```text
Planner
    ↓
Evaluator
    ↓
Planner
```

Cycles should instead communicate through new events and new process instances.

---

# 16. No Multiple Owners

Every mutable object has exactly one owner.

Never:

```text
Scheduler

and

Kernel

both update process state.
```

Instead:

```text
Scheduler

requests

Kernel

to change state.
```

Ownership is singular.

Always.

---

# 17. No Irreproducible Infrastructure

Infrastructure should behave identically when replaying the same event stream.

Kernel behavior should not depend on:

* random numbers
* current time (unless modeled as an event)
* hidden caches
* undocumented heuristics

Determinism is a feature.

---

# 18. No Process Identity by Implementation

The kernel should not distinguish processes based on implementation details.

The following should be equally valid:

* Python process
* Rust process
* Local LLM process
* Remote LLM process
* Rule-based process

Behavior matters.

Implementation does not.

---

# 19. No Leaky Abstractions

Every subsystem exposes only its public contract.

Examples:

The Scheduler should not know how memory is stored.

The Executor should not know how planning works.

The Memory Manager should not know how scheduling decisions are made.

Subsystems communicate through interfaces rather than implementation details.

---

# 20. No Special Cases

Special cases accumulate complexity.

If a capability is valuable, it should become a general abstraction.

Instead of:

> "Research processes behave differently."

Ask:

> "What abstraction is missing that makes research processes appear unique?"

Generalize before specializing.

---

# Architectural Smells

The following are warning signs that the architecture may be drifting away from its principles.

* A process needs direct access to another process.
* The kernel needs to inspect the content of an LLM response.
* Multiple components update the same piece of state.
* A subsystem depends on implementation details of another subsystem.
* A feature requires a hard-coded exception in the kernel.
* A process can perform work without emitting events.
* A capability cannot be replayed from the event log.
* A new component cannot be explained using the existing system model.

Architectural smells are not necessarily bugs, but they should trigger careful design review.

---

# The Rule of Three

Before introducing a new abstraction, ask three questions:

1. Can this be expressed using the existing system model?
2. Does it violate any design principles or forbidden constructs?
3. Will this simplify the system as a whole rather than only this one feature?

If the answer to any of these questions is "no," the abstraction should not be introduced.

---

# Final Principle

The purpose of these constraints is not to make development harder.

It is to make the architecture easier to reason about.

A feature that requires violating these rules should be viewed with skepticism, even if it appears convenient.

Every shortcut taken today becomes technical debt tomorrow.

EmergenceOS should remain a system where new capabilities emerge from a small set of consistent abstractions rather than from an ever-growing collection of exceptions.

---

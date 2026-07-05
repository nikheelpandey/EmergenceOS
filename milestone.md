# EmergenceOS Milestones

> Living tracker for kernel infrastructure milestones.
>
> **Last updated:** 2026-07-05
>
> **Sources:** [docs/003-system-model.md](docs/003-system-model.md) · [docs/001-principles.md](docs/001-principles.md) · [docs/building-applications.md](docs/building-applications.md)

---

## Progress Summary


| ID  | Milestone                    | Status   | Depends On | Principles |
| --- | ---------------------------- | -------- | ---------- | ---------- |
| M1  | Kernel Stabilization         | Complete | —          | P7, P8     |
| M2  | Runtime Integration          | Complete | M1         | P4, P15    |
| M3  | Security Manager             | Complete | M2         | P14        |
| M4  | Scheduler + Resource Budgets | Complete | M3         | P6, P8     |
| M5  | Memory Manager               | Complete | M3         | P5         |
| M6  | Checkpoint Manager           | Complete | M5         | P5, P9     |
| M7  | Event Sourcing Backbone      | Complete | M4, M6     | P4, P7     |
| M8  | Fault Tolerance              | Complete | M6, M7     | P9         |
| M9  | Observability Kernel         | Complete | M7         | P10        |
| M10 | ExecutionSpec + Tool Model   | Complete | M4         | P2, P13    |
| M11 | Plugin Ecosystem             | Complete | M3, M10    | P16, P13   |
| M12 | Cognitive Infrastructure     | Complete | M4, M11    | P1, P12    |


---



## M1 — Kernel Stabilization

**Goal:** Deterministic, test-green kernel with explicit state transitions.

**Principles:** P7 (Deterministic Infrastructure), P8 (Explicit State Transitions)

**Constraints (004):** #5 No Hidden State · #14 No Silent Failure · #16 No Multiple Owners

**Status:** Complete

### Deliverables

- [x] All unit tests pass; fix `pytest.ini` (`--cov=emergence`)
- [x] `StateStore` edge-case fixes
- [x] `Kernel` delegates lifecycle to `LifecycleManager`
- [x] Restore `try/except` in `run_next()` → `FAILED` + `PROCESS_FAILED` event
- [x] Remove debug `print` statements from `Kernel`
- [x] `ProcessTable` transition validation via `LifecycleManager`
- [x] Single boot path via `create_kernel_context()`



### Acceptance Criteria

- `pytest tests/` exits 0
- hello_world runs end-to-end
- Invalid transitions raise `ValueError`
- Runner exception → `FAILED` state + observable event



### Key Files

`emergence/kernel/kernel.py` · `emergence/kernel/lifecycle.py` · `emergence/kernel/process_table.py` · `boot.py` · `emergence/kernel/boot_context.py` · `pytest.ini`

---



## M2 — Runtime Integration (ProcessContext)

**Goal:** Processes access kernel services through `ProcessContext`; Kernel owns composition.

**Principles:** P4 (Events), P15 (Local Reasoning, Global Coordination)

**Constraints (004):** #3 No Direct Process Communication · #4 No Shared Mutable State · #11 No Global Singleton State

**Status:** Complete

### Deliverables

- [x] `Kernel` constructed from `KernelContext`
- [x] On `spawn()`: create mailbox, grant default capabilities, register in `ProcessRegistry`
- [x] On terminal state: revoke capabilities, destroy mailbox, unregister
- [x] `ProcessContext` passed to `PythonRunner` via `Executor`
- [x] `correlation_id` / `causation_id` propagated on lifecycle events
- [x] Integration test: spawn → execute with context → state read/write



### Acceptance Criteria

- `PythonRunner` receives `ProcessContext`, not raw `Process`
- Process accesses `StateStore` only through context
- Termination cleans up mailbox + capabilities
- Child events carry `causation_id` pointing to parent event



### Key Files

`emergence/kernel/kernel.py` · `emergence/kernel/context.py` · `emergence/core/process_context.py` · `emergence/executor/`

---



## M3 — Security Manager

**Goal:** Capability-based least-privilege enforcement; messaging is event-mediated.

**Principles:** P14 (Explicit Permissions)

**Constraints (004):** #1 No God Process · #12 No Implicit Permissions · #3 No Direct Process Communication

**Status:** Complete

### Deliverables

- [x] `CapabilityManager` gates `StateStore`, `MailboxManager.send`, restricted `EventBus.publish`
- [x] Default grants in `capabilities.py` declared in `ProcessDefinition`
- [x] Unauthorized access raises domain exception — tested
- [x] Mailbox send always emits `MessageReceivedEvent`
- [x] `Request` unified with `Message` hierarchy
- [x] Request-response via `correlation_id` in mailbox messages
- [x] Unit tests: grant/deny paths, message round-trip



### Acceptance Criteria

- Process without `state:write` cannot mutate state
- Process A → B communication observable as `MessageReceivedEvent`
- No process bypasses capability check



### Key Files

`emergence/security/` · `emergence/kernel/mailbox_manager.py` · `emergence/common/`

---



## M4 — Scheduler + Resource Budgets

**Goal:** Event-driven scheduling with WAITING/BLOCKED, priorities, dependencies, and budget gates.

**Principles:** P6 (Reasoning is a Managed Resource), P8 (Explicit State Transitions)

**Constraints (004):** #9 No Scheduler Decisions Inside Processes · #13 No Infinite Processes

**Status:** Complete

### Deliverables

- [x] `Kernel` supports `WAITING` / `BLOCKED` transitions
- [x] `WaitCondition` integrated — process yields to `WAITING`
- [x] Scheduler subscribes to `MessageReceivedEvent`, state events, timer wakeups
- [x] Priority queue replaces pure FIFO
- [x] Dependency-aware scheduling (acyclic graph)
- [x] `ResourceBudget` enforcement: deny dispatch when exhausted; timeout → `FAILED`
- [x] Budget consumption tracker



### Acceptance Criteria

- `WAITING` process not dequeued until condition satisfied
- Message arrival → `WAITING` → `READY` → enqueued
- Higher priority runs first when both ready
- Process exceeding `max_execution_time_seconds` → `FAILED` with event



### Key Files

`emergence/scheduler/scheduler.py` · `emergence/kernel/kernel.py` · `emergence/core/wait_condition.py` · `emergence/core/budget.py`

---



## M5 — Memory Manager

**Goal:** Centralized memory ownership — processes request, never store directly.

**Principles:** P5 (State is Durable)

**Constraints (004):** #8 No Memory Access Outside the Memory Manager

**Status:** Complete

### Deliverables

- [x] `MemoryManager` subsystem wrapping `MemoryStore`
- [x] Processes access memory via `ProcessContext.memory` request API
- [x] Memory categories scaffolded: working, episodic, semantic
- [x] Capability-gated: `memory:write`, `memory:read`
- [x] Emits `MEMORY_STORED` / `MEMORY_RETRIEVED` / `MEMORY_DELETED` events
- [x] Added to `KernelContext`
- [x] Unit + integration tests



### Acceptance Criteria

- No code path allows process to mutate `MemoryStore` directly
- Memory operations produce observable events
- Unauthorized memory access denied



### Key Files

`emergence/memory/memory_manager.py` (new) · `emergence/memory/memory_store.py` · `emergence/kernel/context.py`

---



## M6 — Checkpoint Manager

**Goal:** Durable process snapshots enabling recovery.

**Principles:** P5 (State is Durable), P9 (Failure is First-Class)

**Constraints (004):** #5 No Hidden State

**Status:** Complete

### Deliverables

- [x] `CheckpointManager` subsystem (`emergence/checkpoint/`)
- [x] Checkpoint model: process state, working memory ref, event offset, resource usage, timestamps
- [x] `create_checkpoint()` / `restore_checkpoint()`
- [x] Emits `CHECKPOINT_CREATED` / `CHECKPOINT_RESTORED` events
- [x] Capability-gated: `checkpoint:create`, `checkpoint:restore`
- [x] In-memory store first; SQLite adapter stub
- [x] Integration test: checkpoint → kill → restore → resume



### Acceptance Criteria

- Restored process resumes from checkpoint without re-executing completed work
- Checkpoint creation is observable via events
- Long-running process has at least one checkpoint before `WAITING`



### Key Files

`emergence/checkpoint/` (new) · `emergence/kernel/context.py`

---



## M7 — Event Sourcing Backbone

**Goal:** Append-only event log; deterministic replay.

**Principles:** P4 (Events as source of truth), P7 (Deterministic Infrastructure)

**Constraints (004):** #17 No Irreproducible Infrastructure

**Status:** Complete

### Deliverables

- [x] `EventStore`: `append()`, `query()`, `replay()`
- [x] Event bus publishes to `EventStore` sink on every publish
- [x] Replay engine reconstructs process table, state store, scheduler queue
- [x] File-backed adapter (JSONL or SQLite)
- [x] Full `correlation_id` / `causation_id` chain preserved
- [x] Tests: record N events → replay → identical snapshot



### Acceptance Criteria

- Every published event persisted
- `replay(from_ts)` reproduces kernel state deterministically
- Replay test covers spawn → execute → wait → complete → fail



### Key Files

`emergence/events/event_store.py` (new) · `emergence/events/replay.py` (new)

---



## M8 — Fault Tolerance

**Goal:** Crash recovery, retries, supervision — infrastructure-owned failure handling.

**Principles:** P9 (Failure is First-Class)

**Constraints (004):** #14 No Silent Failure · #13 No Infinite Processes

**Status:** Complete

### Deliverables

- [x] Supervisor loop (kernel-level)
- [x] Heartbeat / watchdog for long-running processes
- [x] Retry policy using `ResourceBudget.max_retries` with backoff
- [x] Recovery actions: retry, restore from checkpoint, escalate, terminate
- [x] `PROCESS_FAILED` triggers recovery policy evaluation
- [x] Crash events in `EventStore`
- [x] Integration test: flaky process succeeds on retry N



### Acceptance Criteria

- Crash produces observable event + recovery action
- Checkpoint restore used before retry when available
- Max retries respected from budget



### Key Files

`emergence/kernel/supervisor.py` (new) · `emergence/kernel/lifecycle.py` · `emergence/checkpoint/`

---



## M9 — Observability Kernel

**Goal:** Every decision inspectable; audit trail from event log.

**Principles:** P10 (Observability Before Optimization)

**Status:** Complete

### Deliverables

- [x] Per-process structured logs (correlated by `process_id`, `correlation_id`)
- [x] Metrics: process count by state, queue depth, event throughput, token consumption
- [x] Trace API: `trace(correlation_id)` returns causal chain
- [x] Audit trail: reconstruct any process execution from event log
- [x] Debug CLI: `list processes`, `trace event`, `dump state`, `show budget`
- [x] Every state transition generates event + log entry



### Acceptance Criteria

- `trace(correlation_id)` returns full cross-process chain
- Debug CLI shows live system state
- No state transition without corresponding event



### Key Files

`emergence/observability/` (new) · `emergence/events/event_bus.py`

---



## M10 — ExecutionSpec + Tool Request Model

**Goal:** Separate runner backend from target; tools only via Executor.

**Principles:** P2 (Kernel Never Thinks), P13 (Replaceability)

**Constraints (004):** #7 No Tool Access Outside the Executor · #10 No Business Logic in Infrastructure

**Status:** Complete

### Deliverables

- [x] `ExecutionSpec` model: `runner`, `target`, `config`
- [x] `ProcessDefinition` uses `ExecutionSpec` instead of conflated `implementation`
- [x] Tool request flow: Process → Executor → Tool → result event
- [x] Processes never call tools directly
- [x] Budget decrements on tool invocation
- [x] Migration: hello_world uses `ExecutionSpec`



### Acceptance Criteria

- No direct tool invocation from process code in tests
- Tool execution produces event chain with causation
- Runner replaceable without kernel changes



### Key Files

`emergence/core/execution_spec.py` (new) · `emergence/executor/executor.py` · `emergence/core/process_definition.py`

---



## M11 — Plugin Ecosystem

**Goal:** Installable, discoverable process modules with declared capabilities.

**Principles:** P16 (Evolution Without Rewrite), P13 (Replaceability)

**Status:** Complete

### Deliverables

- [x] Plugin manifest (`plugin.yaml`): entrypoint, required capabilities, supported events
- [x] `/plugins` directory convention with auto-discovery
- [x] Dynamic `ProcessDefinition` loading
- [x] Capability grants on load; kernel enforces
- [x] hello_world migrated to plugin layout
- [x] Plugin load/unload lifecycle events



### Acceptance Criteria

- Drop plugin folder → kernel discovers and spawns
- Plugin without declared capabilities cannot access gated resources



### Key Files

`emergence/plugins/` (new) · `emergence/apps/hello_world.py`

---



## M12 — Cognitive Infrastructure (Goal / Plan / Task)

**Goal:** Restore application-level entities from system model for multi-process orchestration.

**Principles:** P1 (Everything is a Process), P12 (Composition Over Specialization)

**Status:** Complete

### Deliverables

- [x] Restore `Goal`, `Plan`, `Task` models
- [x] Goal → Plan → Task decomposition API (kernel-managed)
- [x] Task assignment to processes; dependency graph feeds scheduler
- [x] Events: `GOAL_CREATED`, `PLAN_UPDATED`, `TASK_COMPLETED`, etc.
- [x] Integration test: Goal spawns Planner → Plan → Tasks → scheduled execution



### Acceptance Criteria

- Goal/Plan/Task lifecycle matches enums in `state.py`
- Tasks map to process instances via scheduler
- Kernel never calls LLM to decompose goals



### Key Files

`emergence/core/goal.py` · `emergence/core/plan.py` · `emergence/core/task.py` (new)

---



## Out of Scope (Future)

Tracked separately from current milestones:

- Distributed runtime (multiple kernels, cluster scheduling)
- Ollama / Docker / WASM runners (partial — see M13)
- Vector search, knowledge graphs (memory Phase 2+ — see M15)
- Human-in-the-loop UI (`USER_*` events per P11 — see M17)

---

## Future Cognitive / AI Milestones

M1–M12 built the kernel. These milestones target **AI applications that run on EmergenceOS** without violating P2 (Kernel Never Thinks) or P7 (Deterministic Infrastructure).

| ID  | Milestone              | Status  | Depends On | Goal |
| --- | ---------------------- | ------- | ---------- | ---- |
| M13 | LLM Tool Provider      | Planned | M10        | Register Ollama/OpenAI as budgeted tools; token accounting in `BudgetTracker` |
| M14 | Planner Plugin         | Planned | M11, M12   | LLM process decomposes goals into `TaskSpec` lists; kernel only schedules |
| M15 | Memory + RAG           | Planned | M5, M13    | Vector index over episodic/semantic memory; retrieval as a tool |
| M16 | Researcher / Evaluator | Planned | M14, M15   | Multi-agent loop: plan → research → evaluate → reflect → replan |
| M17 | Human-in-the-loop      | Planned | M7, M16    | `USER_APPROVAL_REQUESTED` events, interrupt/resume, approval gates |
| M18 | Reference AI App       | Planned | M16, M17   | Research Assistant: goal-driven, long-running, observable end-to-end |

### M13 — LLM Tool Provider

**Goal:** Processes invoke LLMs through `context.tools`, never directly.

**Deliverables:**
- `llm.chat` tool with provider adapters (Ollama, OpenAI-compatible API)
- Token consumption decrements `ResourceBudget`
- Tool result events with `correlation_id` / `causation_id`
- Integration test: plugin calls LLM tool, budget enforced

**Acceptance:** No `import openai` in process plugins; all LLM access via `ToolExecutor`.

### M14 — Planner Plugin

**Goal:** Autonomous plan decomposition as a replaceable plugin process.

**Deliverables:**
- `plugins/planner/` invokes `llm.chat` to produce `TaskSpec` JSON
- Kernel `create_plan_from_goal()` spawns planner, waits for plan artifact in memory
- Planner is a normal long-running process (checkpoint + wait)

**Acceptance:** `python boot.py --plan "Research X"` produces a valid plan without kernel LLM imports.

### M15 — Memory + RAG

**Goal:** Retrieval-augmented generation over kernel-managed memory.

**Deliverables:**
- Vector index adapter (in-memory first; Chroma optional)
- `memory.search` tool with episodic + semantic scopes
- Researcher plugin stores findings in episodic memory, retrieves context for prompts

**Acceptance:** Researcher recalls prior findings across process restarts via checkpoint + memory.

### M16 — Researcher / Evaluator Loop

**Goal:** Reference multi-agent cognitive pipeline on the OS.

**Deliverables:**
- Researcher plugin: gather → store → respond
- Evaluator plugin: score output, emit `EVALUATION_COMPLETED`
- Coordinator reacts to evaluation, triggers replan or completion
- Integration test mirrors `system_model_demo` but with LLM tools

**Acceptance:** Goal reaches `COMPLETED` or `FAILED` with full event audit trail.

### M17 — Human-in-the-loop

**Goal:** Users can approve, redirect, or interrupt running cognitive workflows.

**Deliverables:**
- `USER_MESSAGE_RECEIVED`, `USER_APPROVAL_REQUESTED`, `USER_APPROVAL_GRANTED` events
- Processes block on `wait_for_approval()` with checkpoint
- CLI or HTTP ingress publishes user events to the bus

**Acceptance:** Research Assistant pauses before external action; resumes after approval.

### M18 — Reference AI App: Research Assistant

**Goal:** Ship a complete cognitive application demonstrating the full stack.

**Deliverables:**
- `plugins/research_assistant/` — goal intake, planning, research, evaluation, report
- Long-running, checkpointed, observable via `./eos trace`
- `python boot.py --research "topic"` end-to-end demo

**Acceptance:** User provides a topic; system produces a report with traceable provenance.

---



## Changelog


| Date       | Entry                                                                      |
| ---------- | -------------------------------------------------------------------------- |
| 2026-07-05 | **v0.1.0 release** — M1–M12, plugins, long-running services, 462 tests     |
| 2026-07-05 | Long-running apps — heartbeat, collector, job_worker, orchestrator fleet   |
| 2026-07-05 | M11 complete — plugin discovery, plugin.yaml manifests, hello_world plugin |
| 2026-07-05 | M10 complete — ExecutionSpec, tool request model, hello_world migration    |
| 2026-07-05 | M9 complete — observability kernel, trace/metrics/budget CLI               |
| 2026-07-05 | M8 complete — supervisor, retry policy, checkpoint-aware recovery          |
| 2026-07-05 | M7 complete — EventStore, PersistingEventBus, replay engine                |
| 2026-07-05 | M6 complete — CheckpointManager, gated restore, auto-checkpoint on WAITING |
| 2026-07-05 | M5 complete — MemoryManager, gated ProcessContext.memory                   |
| 2026-07-04 | M4 complete — priority scheduler, WAITING/BLOCKED, budget enforcement      |
| 2026-07-04 | M3 complete — capability-gated services, Request/Message hierarchy         |
| 2026-07-04 | M2 complete — ProcessContext runtime integration, spawn/cleanup lifecycle  |
| 2026-07-03 | M1 complete — kernel stabilization, unified boot, lifecycle delegation     |
| 2026-07-03 | Created milestone tracker; started M1 Kernel Stabilization                 |



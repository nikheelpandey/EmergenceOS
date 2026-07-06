# EmergenceOS Milestones

> Living tracker for kernel and product milestones.
>
> **Last updated:** 2026-07-06 (M30 complete)
>
> **Sources:** [docs/003-system-model.md](docs/003-system-model.md) · [docs/001-principles.md](docs/001-principles.md) · [docs/005-ux-vision.md](docs/005-ux-vision.md) · [docs/building-applications.md](docs/building-applications.md)

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
| M13 | LLM Tool Provider            | Complete | M10        | P2, P13    |
| M14 | Planner Plugin               | Complete | M11, M12   | P1, P2     |
| M15 | Memory + RAG                 | Complete | M5, M13    | P5         |
| M16 | Researcher / Evaluator       | Complete | M14, M15   | P1, P12    |
| M17 | Human-in-the-loop            | Complete | M7, M16    | P11        |
| M18 | Reference AI App             | Complete | M16, M17   | P1, P10    |
| M19 | Live Kernel Control Plane    | Complete | M9         | P10        |
| M20 | Durable Persistence          | Complete | M6, M7     | P5, P7     |
| M21 | Goal Registry                | Complete | M12, M20   | P1, P10    |
| M22 | Knowledge Layer              | Complete | M5, M15, M21 | P5, P10  |
| M23 | Timeline & Narrative API     | Complete | M7, M21    | P4, P10    |
| M24 | Event Inspector API          | Complete | M9, M19    | P10        |
| M25 | HTTP Ingress                 | Complete | M19–M24    | P4, P11    |
| M26 | Goal Inbox (Web UI v1)       | Complete | M25        | P10, P11   |
| M27 | Spaces                       | Complete | M21, M22, M26 | P14, P16 |
| M28 | Scheduled Work & Cron        | Complete | M4, M23    | P4, P6     |
| M29 | Channel Ingress              | Complete | M25        | P4         |
| M30 | Artifact Service             | Complete | M20, M21, M27 | P5, P10 |


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

Tracked separately from M19–M29:

- Distributed runtime (multiple kernels, cluster scheduling)
- Docker / WASM runners (PythonRunner + Ollama sufficient for UX v1 — see M13)
- Chroma / external vector DB backends (TF-IDF sufficient for v1 Knowledge — see M15, M22)
- Chat-style primary UI (violates [005-ux-vision.md](docs/005-ux-vision.md))

---

## Future Cognitive / AI Milestones

M1–M18 complete. The kernel and reference cognitive AI stack ship together.

| ID  | Milestone              | Status   | Depends On | Goal |
| --- | ---------------------- | -------- | ---------- | ---- |
| M13 | LLM Tool Provider      | Complete | M10        | Register Ollama/OpenAI as budgeted tools; token accounting in `BudgetTracker` |
| M14 | Planner Plugin         | Complete | M11, M12   | LLM process decomposes goals into `TaskSpec` lists; kernel only schedules |
| M15 | Memory + RAG           | Complete | M5, M13    | Vector index over episodic/semantic memory; retrieval as a tool |
| M16 | Researcher / Evaluator | Complete | M14, M15   | Multi-agent loop: plan → research → evaluate → reflect → replan |
| M17 | Human-in-the-loop      | Complete | M7, M16    | `USER_APPROVAL_REQUESTED` events, interrupt/resume, approval gates |
| M18 | Reference AI App       | Complete | M16, M17   | Research Assistant: goal-driven, long-running, observable end-to-end |

### M13 — LLM Tool Provider

**Status:** Complete

**Goal:** Processes invoke LLMs through `context.tools`, never directly.

**Deliverables:**
- [x] `llm.chat` tool with provider adapters (Ollama, OpenAI-compatible API, mock)
- [x] Token consumption decrements `ResourceBudget`
- [x] Tool result events with `correlation_id` / `causation_id`
- [x] Integration test: plugin calls LLM tool, budget enforced

**Acceptance:** No `import openai` in process plugins; all LLM access via `ToolExecutor`.

### M14 — Planner Plugin

**Status:** Complete

**Goal:** Autonomous plan decomposition as a replaceable plugin process.

**Deliverables:**
- [x] `plugins/planner/` invokes `llm.chat` to produce `TaskSpec` JSON
- [x] Kernel `create_plan_from_goal()` spawns planner, waits for plan artifact in state
- [x] Planner is a normal process (checkpoint + wait capable)
- [x] `python boot.py --plan "Research X"` produces a valid plan

**Acceptance:** `python boot.py --plan "Research X"` produces a valid plan without kernel LLM imports.

### M15 — Memory + RAG

**Status:** Complete

**Goal:** Retrieval-augmented generation over kernel-managed memory.

**Deliverables:**
- [x] Vector index adapter (in-memory TF-IDF)
- [x] `memory.search` tool with episodic + semantic scopes
- [x] Researcher plugin stores findings in episodic memory, retrieves context for prompts

**Acceptance:** Researcher recalls prior findings across process restarts via checkpoint + memory.

### M16 — Researcher / Evaluator Loop

**Status:** Complete

**Goal:** Reference multi-agent cognitive pipeline on the OS.

**Deliverables:**
- [x] Researcher plugin: gather → store → respond
- [x] Evaluator plugin: score output, emit `EVALUATION_COMPLETED`
- [x] Coordinator reacts to evaluation, triggers replan or completion
- [x] Integration test mirrors `system_model_demo` but with LLM tools

**Acceptance:** Goal reaches `COMPLETED` or `FAILED` with full event audit trail.

### M17 — Human-in-the-loop

**Status:** Complete

**Goal:** Users can approve, redirect, or interrupt running cognitive workflows.

**Deliverables:**
- [x] `USER_MESSAGE_RECEIVED`, `USER_APPROVAL_REQUESTED`, `USER_APPROVAL_GRANTED` events
- [x] Processes block on `wait_for_approval()` with checkpoint
- [x] CLI ingress: `./eos approve <request_id>`

**Acceptance:** Research Assistant pauses before external action; resumes after approval.

### M18 — Reference AI App: Research Assistant

**Status:** Complete

**Goal:** Ship a complete cognitive application demonstrating the full stack.

**Deliverables:**
- [x] `plugins/research_assistant/` — goal intake, planning, research, evaluation, report
- [x] Long-running, checkpointed, observable via `./eos trace`
- [x] `python boot.py --research "topic"` end-to-end demo

**Acceptance:** User provides a topic; system produces a report with traceable provenance.

---

## UX & Product Milestones (M19–M29)

M1–M18 delivered the kernel and reference cognitive AI stack. M19–M29 deliver the **UX foundation and first product surface** described in [docs/005-ux-vision.md](docs/005-ux-vision.md).

**Do not start web UI work (M26) until M19, M20, and M21 are complete.**

| ID  | Milestone              | Status  | Depends On | Goal |
| --- | ---------------------- | ------- | ---------- | ---- |
| M19 | Live Kernel Control Plane | Complete | M9      | Connect all clients to the single running kernel |
| M20 | Durable Persistence    | Complete | M6, M7     | Goals, events, and memory survive restart |
| M21 | Goal Registry          | Complete | M12, M20   | Goals as living workloads with computed health |
| M22 | Knowledge Layer        | Complete | M5, M15, M21 | Memory → browsable Knowledge with provenance |
| M23 | Timeline & Narrative API | Complete | M7, M21  | Event log → human timeline grouped by day |
| M24 | Event Inspector API    | Complete | M9, M19    | Click any event → full causal inspector |
| M25 | HTTP Ingress           | Complete | M19–M24    | REST + WebSocket API for external clients |
| M26 | Goal Inbox (Web UI v1) | Complete | M25        | First end-user product surface |
| M27 | Spaces                 | Complete | M21, M22, M26 | Namespaces for life/work domains |
| M28 | Scheduled Work & Cron  | Complete | M4, M23    | Future work visible on goal timeline |
| M29 | Channel Ingress        | Complete | M25        | Slack/email/Telegram as goal submission channels |

### Dependency graph

```
M19 ──┬──► M24 ──┐
M20 ──► M21 ──┬──► M22 ──┐
              ├──► M23 ──├──► M25 ──► M26 ──► M27
              └──────────┘
M25 ──► M29
M23 ──► M28
```

---

## M19 — Live Kernel Control Plane

**Goal:** One running kernel; all observability and control clients connect to it.

**Principles:** P10 (Observability Before Optimization)

**Depends on:** M9

**Status:** Complete

### Deliverables

- [x] Admin TCP API exposed by `RuntimeService.start()` on `127.0.0.1:<port>`
- [x] `./eos ps`, `top`, `sched`, `state`, `budget`, `trace`, `approve` connect to live kernel by default
- [x] `--demo` flag retained for offline inspection only
- [x] System snapshot API: process table, scheduler queue, state store, pending approvals
- [x] Runtime lock via PID file + `runtime.json` manifest
- [x] Integration test: serve in one process, query from another

### Acceptance Criteria

- Terminal 1: `./eos serve`
- Terminal 2: `./eos ps` shows live platform services (heartbeat, etc.) — not a demo kernel
- `./eos approve <id>` in Terminal 2 unblocks a waiting process in Terminal 1
- Snapshot API returns identical data to `./eos ps` + `./eos sched`

### Key Files

`emergence/admin/` · `emergence/kernel/runtime.py` · `emergence/cli/__main__.py` · `tests/integration/test_admin_integration.py`

---

## M20 — Durable Persistence

**Goal:** The OS survives restart. Living workloads and timelines are real across sessions.

**Principles:** P5 (State is Durable), P7 (Deterministic Infrastructure)

**Depends on:** M6, M7

**Status:** Complete

### Deliverables

- [x] `JsonlEventStore` wired when `EMERGENCE_DATA_DIR` is set
- [x] SQLite checkpoint store implemented
- [x] Cognitive state restored on boot via `cognitive.json` snapshot
- [x] Episodic + semantic memory persisted via `FileMemoryStore`
- [x] Shared state persisted via `state.json` snapshot
- [x] Configurable data directory (`EMERGENCE_DATA_DIR` / `~/.emergence/`)
- [x] Integration test: create goal → flush → restart → goal and history intact

### Acceptance Criteria

- Event log written to disk on every publish (when persistence enabled)
- Runtime restart preserves goals, memory artifacts, and event history
- `./eos serve` with `EMERGENCE_DATA_DIR` writes under data directory

### Key Files

`emergence/persistence/` · `emergence/memory/file_memory_store.py` · `emergence/checkpoint/sqlite_adapter.py` · `tests/integration/test_persistence_integration.py`

---

## M21 — Goal Registry

**Goal:** Goals become living workloads — persistent entities with computed health, not ephemeral jobs.

**Principles:** P1 (Everything is a Process), P10 (Observability)

**Depends on:** M12, M20

**Status:** Complete

### Deliverables

- [x] `GoalRegistry` — durable, queryable store separate from in-memory `CognitiveManager` dict
- [x] Goal ↔ process association (root process, child task processes)
- [x] Computed health from kernel signals (never LLM self-report):

  | Signal | Health |
  |--------|--------|
  | Child process failed | Degraded |
  | Budget exceeded | Degraded |
  | Approval pending beyond threshold | Needs attention |
  | No activity beyond staleness window | Idle |
  | All processes healthy, active | Healthy |

- [x] Aggregate stats: uptime, active child count, knowledge size, last event timestamp
- [x] Goal kinds: one-shot (archive on complete) vs persistent (service workload)
- [x] Events: `GOAL_HEALTH_CHANGED`, goal stats updated on process lifecycle events

### Acceptance Criteria

- [x] Research Assistant registered as a persistent goal with uptime and child process count
- [x] Health transitions to Degraded when a child process fails — no plugin code required
- [x] Goal survives kernel restart (depends on M20)
- [x] API/query returns health, pipeline stage, and associated process list

### Key Files

`emergence/cognitive/` (new `goal_registry.py`) · `emergence/core/goal.py` · `emergence/kernel/kernel.py`

---

## M22 — Knowledge Layer

**Goal:** Memory becomes browsable Knowledge — accumulated intelligence visible to users.

**Principles:** P5 (State is Durable), P10 (Observability)

**Depends on:** M5, M15, M21

**Status:** Complete

### Deliverables

- [x] `KnowledgeIndex` — aggregates `MemoryStoredEvent` by goal (and later, space)
- [x] Artifact typing: document, summary, report, embedding, dataset, finding
- [x] Provenance: source process, plugin, timestamp, correlation chain
- [x] Approximate size accounting per artifact
- [x] Query API: list by goal, filter by type, sort by recency
- [x] Goal stats feed knowledge size into `GoalRegistry`

### Acceptance Criteria

- [x] Goal card data: "143 MB · 123 docs · 2 reports · updated 2m ago"
- [x] Researcher storing findings automatically appears in Knowledge index
- [x] Click artifact → resolves to inspector event chain (depends on M24)
- [x] Knowledge survives kernel restart (depends on M20)

### Key Files

`emergence/memory/` (new `knowledge_index.py`) · `emergence/events/memory_events.py` · `emergence/cognitive/goal_registry.py`

---

## M23 — Timeline & Narrative API

**Goal:** Time as a first-class UX dimension — event log rendered as human timeline.

**Principles:** P4 (Events as source of truth), P10 (Observability)

**Depends on:** M7, M21

**Status:** Complete

### Deliverables

- [x] Event → human-language translation layer (template-based, deterministic — not LLM)
- [x] Filtered timeline API: by goal, correlation, date range
- [x] Day-grouped output (Yesterday / Today / Tomorrow)
- [x] Every timeline entry links to event ID for inspector drill-down
- [x] Scheduled future entries placeholder (full cron in M28)

### Acceptance Criteria

- [x] `goal.timeline` admin API returns grouped narrative entries
- [x] "Research Assistant stored 4 findings" derived from `MEMORY_STORED` events — not hardcoded strings in plugins
- [x] Timeline survives restart and replays correctly from event log

### Key Files

`emergence/events/narrative.py` · `emergence/admin/snapshot_api.py` · `emergence/admin/server.py` · `tests/unit/events/test_narrative.py` · `tests/integration/test_timeline_integration.py`

---

## M24 — Event Inspector API

**Goal:** Everything inspectable — the trust layer behind Timeline and Knowledge.

**Principles:** P10 (Observability Before Optimization)

**Depends on:** M9, M19

**Status:** Complete

### Deliverables

- [x] Structured inspector payload per event: why, process, plugin, capability, duration, memory delta
- [x] Correlation chain expansion (extends `./eos trace`)
- [x] Process → plugin → capability resolution
- [x] Duration computed from `PROCESS_STARTED` / `PROCESS_COMPLETED` event pairs
- [x] `GET /events/{id}/inspect` endpoint (via M25)

### Acceptance Criteria

- [x] Any timeline entry expands to full inspector with correlation chain
- [x] "Why did this happen?" answered from event causation — not LLM narrative
- [x] Inspector works against live kernel (depends on M19)

### Key Files

`emergence/observability/inspector.py` · `emergence/admin/snapshot_api.py` · `tests/unit/observability/test_inspector.py` · `tests/integration/test_inspector_integration.py`

---

## M25 — HTTP Ingress

**Goal:** External clients (web UI, mobile, channels) can drive the kernel without the REPL.

**Principles:** P4 (Events), P11 (Human Authority)

**Depends on:** M19, M21, M22, M23, M24

**Status:** Complete

### Deliverables

- [x] REST API:
  - `POST /goals` — submit goal in natural language
  - `GET /goals`, `GET /goals/{id}`
  - `GET /goals/{id}/timeline`, `/knowledge`, `/processes`
  - `POST /approvals/{id}` — grant or reject
  - `GET /events`, `GET /events/{id}/inspect`
  - `GET /system/snapshot` — Activity Monitor data
- [x] WebSocket + SSE: stream translated events per goal
- [x] Local auth token (`EMERGENCE_API_TOKEN`)
- [x] Integration test: full research assistant flow via curl only

### Acceptance Criteria

- [x] `curl` can create a goal, watch event stream, and approve a pending request
- [x] No REPL required for end-to-end research assistant demo
- [x] WebSocket client receives narrative events as processes run

### Key Files

`emergence/ingress/http/` · `emergence/ingress/goal_submission.py` · `emergence/kernel/runtime.py` · `tests/integration/test_http_integration.py`

---

## M26 — Goal Inbox (Web UI v1)

**Goal:** First end-user product surface — Goals, Knowledge, Timeline, visible Processes.

**Principles:** P10, P11

**Depends on:** M25

**Status:** Complete

### Deliverables

- [x] Goal list with health cards and pipeline progress bars
- [x] Goal detail: overview, processes (Activity Monitor style), knowledge, timeline
- [x] Approval cards with artifact preview
- [x] Event inspector drill-down on any timeline entry
- [x] System Activity Monitor (global process view)
- [x] Empty state teaching the OS metaphor (see [005-ux-vision.md](docs/005-ux-vision.md))
- [x] Processes visible but not manageable — no PIDs or spawn commands in default view

### Acceptance Criteria

- [x] Non-developer completes research flow without terminal
- [x] Process pipeline visible; user understands "multiple things are happening"
- [x] Approval works from browser; process resumes after grant
- [x] No chat-thread primary UI

### Key Files

`web/` (index.html, app.js, styles.css) · consumes M25 HTTP API

---

## M27 — Spaces

**Goal:** Multiple domains of life/work — each Space owns goals, memory, policies, and plugins.

**Principles:** P14 (Explicit Permissions), P16 (Evolution Without Rewrite)

**Depends on:** M21, M22, M26

**Status:** Complete

### Deliverables

- [x] `Space` entity: name, policies, plugin set, memory namespace prefix
- [x] Space-scoped goals, knowledge, and process association
- [x] Space desktop API: active goals, recent knowledge, attention needed
- [x] Default space + create / list / switch
- [x] UI: Space sidebar; switching changes goal and knowledge context

### Acceptance Criteria

- [x] "Work" and "Personal" spaces have isolated knowledge indexes
- [x] Memory keys scoped as `space:category:pid:key`
- [x] Space desktop shows correct aggregates per space

### Key Files

`emergence/spaces/` · `emergence/memory/memory_manager.py` · `emergence/cognitive/goal_registry.py` · `tests/integration/test_spaces_integration.py`

---

## M28 — Scheduled Work & Cron

**Goal:** Future scheduled actions visible on goal timeline ("Tomorrow: scheduled publication").

**Principles:** P4 (Events), P6 (Reasoning is a Managed Resource)

**Depends on:** M4, M23

**Status:** Complete

### Deliverables

- [x] `ScheduleManager` — register future wakeups tied to goals
- [x] Cron entries as first-class events
- [x] Timeline shows future scheduled items alongside past events
- [x] Scheduler integration: timer wakeups enqueue processes

### Acceptance Criteria

- [x] Scheduled publication appears on goal timeline before it runs
- [x] Timer fires → process enqueued → observable event chain
- [x] Missed schedules handled on kernel restart (depends on M20)

### Key Files

`emergence/scheduler/schedule_manager.py` · `emergence/events/narrative.py` · `tests/integration/test_schedule_integration.py`

---

## M29 — Channel Ingress

**Goal:** Submit goals from Slack, email, or Telegram — not chat loops.

**Principles:** P4 (Events)

**Depends on:** M25

**Status:** Complete

### Deliverables

- [x] Channel adapter pattern: inbound message → `POST /goals` → tracking link reply
- [x] Approval pushback to originating channel (via shared event stream)
- [x] Reference adapter: webhook channel
- [x] Channels submit goals and receive status updates — they do not host a ReAct loop

### Acceptance Criteria

- [x] Message "Research X" in channel → goal created → reply with tracking URL
- [x] Approval request visible in web UI; grant resumes process
- [x] No conversational thread as primary interaction model

### Key Files

`emergence/ingress/channels/` · M25 HTTP API · `tests/integration/test_http_integration.py`

---

## M30 — Artifact Service

**Goal:** Physical artifacts as a first-class kernel primitive — queryable, versioned, event-driven outputs that processes consume by type, not file path.

**Principles:** P5 (Memory & Durability), P10 (Observability)

**Depends on:** M20, M21, M27

**Status:** Complete

### Deliverables

- [x] `ArtifactService` on `KernelContext` — create, read, update, delete, search, version, watch, link, export
- [x] Typed artifacts with goal/process/space provenance, tags, metadata, and lineage versioning
- [x] Blob storage + `artifacts.json` persistence (separate from Knowledge semantic index)
- [x] Events: `artifact.created`, `artifact.updated`, `artifact.deleted` — scheduler wake on artifact changes
- [x] Kernel tools `artifact.*` with `artifact.read` / `artifact.write` capabilities
- [x] HTTP: `GET /artifacts`, `GET /artifacts/{id}`, `GET /goals/{id}/artifacts`
- [x] Admin API: `artifacts.list`, `artifacts.get`

### Acceptance Criteria

- [x] Process finds artifacts by type/query without filesystem paths or LLM
- [x] Artifact update emits `artifact.updated` and supersedes prior version
- [x] Artifacts survive restart via `EMERGENCE_DATA_DIR`
- [x] Knowledge and Artifacts remain separate subsystems (semantic vs physical)

### Key Files

`emergence/artifacts/service.py` · `emergence/events/artifact_events.py` · `emergence/tools/artifact_tools.py` · `tests/unit/artifacts/` · `tests/integration/test_artifact_integration.py`

---

## Ready for UX checklist

Before starting M26 (web UI):

- [x] M19 — `./eos ps` shows live processes from running kernel
- [x] M20 — goals survive kernel restart
- [x] M21 — goal has computed health, uptime, child processes
- [x] M22 — knowledge list derivable from memory events
- [x] M23 — timeline derivable from event log
- [x] M24 — any event inspectable with correlation chain
- [x] M25 — curl drives full research assistant flow

---

## Changelog


| Date       | Entry                                                                      |
| ---------- | -------------------------------------------------------------------------- |
| 2026-07-06 | **v0.4.0 release** — Artifact Service (M30), OS tools, goal policies, web UI v2 (595 tests) |
| 2026-07-06 | **M30 complete** — physical artifact kernel primitive, versioning, event-driven updates |
| 2026-07-05 | **M24–M29 complete** — Event Inspector, HTTP ingress, Goal Inbox web UI, Spaces, Cron, Channel ingress (558 tests) |
| 2026-07-05 | **M23 complete** — narrative timeline from event log, day grouping, admin `goal.timeline` API |
| 2026-07-05 | **M21–M22 complete** — Goal Registry, Knowledge Layer |
| 2026-07-05 | **M19–M29 planned** — UX foundation, Goal Registry, Knowledge, HTTP ingress, Goal Inbox web UI |
| 2026-07-05 | **M13–M18 complete** — LLM tools, RAG, planner, researcher/evaluator, HITL, research assistant |
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



# Changelog

All notable changes to EmergenceOS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-07-05

UX foundation and first product surface (M19–M29): live control plane, durable persistence, goal registry, knowledge layer, narrative timeline, event inspector, HTTP ingress, Goal Inbox web UI, spaces, scheduled work, and channel ingress.

### Added

#### Live control plane (M19)
- Admin TCP API on `127.0.0.1:<port>` via `RuntimeService` / `./eos serve`
- `./eos ps`, `top`, `sched`, `state`, `budget`, `trace`, `approve` connect to live kernel
- Runtime lock (`runtime.json` + PID file) — single instance per data directory

#### Durable persistence (M20)
- `JsonlEventStore`, SQLite checkpoints, file-backed memory
- Cognitive state, goal registry, knowledge index, spaces, and schedules persist across restart
- `EMERGENCE_DATA_DIR` (default `~/.emergence/`)

#### Goal registry (M21)
- `GoalRegistry` — durable goals with computed health (healthy/degraded/needs_attention/idle)
- Goal ↔ process association, one-shot vs persistent kinds
- Admin API: `goals`, `goal.get`

#### Knowledge layer (M22)
- `KnowledgeIndex` — artifacts from `MEMORY_STORED` events (findings, reports, docs, …)
- Provenance chain, size accounting, goal card summaries
- Admin API: `knowledge.list`, `knowledge.get`

#### Timeline & narrative (M23)
- Deterministic event → human-language translation (`emergence/events/narrative.py`)
- Day-grouped timeline (Today / Yesterday / Tomorrow)
- Admin API: `goal.timeline`, `timeline.list`

#### Event inspector (M24)
- Structured inspector payload: why, plugin, capabilities, duration, correlation chain
- Admin API: `event.inspect` · HTTP: `GET /events/{id}/inspect`

#### HTTP ingress (M25)
- REST API on `http://127.0.0.1:8765` (`EMERGENCE_HTTP_PORT`)
- Goals, timeline, knowledge, results, approvals, system snapshot
- WebSocket + SSE event streams per goal
- Optional auth: `EMERGENCE_API_TOKEN`

#### Goal Inbox web UI (M26)
- `web/` — goal list, detail, Results panel, knowledge previews, timeline drill-down, approvals
- Served at `/` when `./eos serve` is running

#### Spaces (M27)
- `SpaceRegistry` — isolated namespaces for goals, knowledge, and memory
- Memory keys scoped as `space:category:pid:key`
- HTTP: `GET/POST /spaces`, `POST /spaces/{id}/switch`

#### Scheduled work (M28)
- `ScheduleManager` — one-shot future wakeups tied to goals
- Timeline shows scheduled future entries; fires processes on due time

#### Channel ingress (M29)
- Webhook adapter: `POST /channels/webhook` → goal + tracking URL

#### Ollama integration
- `EMERGENCE_LLM_PROVIDER=ollama` + `EMERGENCE_LLM_MODEL=qwen2.5:7b` for real research output
- Topic-aware mock LLM fallback; `research_output.py` formats reports

### Fixed
- Knowledge API and web UI now return full artifact **content** (not just metadata)
- `reconcile_from_memory()` indexes reports missing from knowledge index after restart
- Legacy memory key format backward compatibility (`category:pid:key` and `space:category:pid:key`)

### Tests
- 560+ tests (unit + integration for admin, persistence, goals, knowledge, timeline, HTTP, spaces, schedules)

## [0.2.0] - 2026-07-05

Cognitive AI milestones M13–M18: LLM tools, RAG memory search, LLM planner, researcher/evaluator plugins, human-in-the-loop approval, and the research assistant reference app.

### Added

#### LLM tools (M13)
- `llm.chat` tool with Mock, Ollama, and OpenAI-compatible providers
- Token and cost accounting in `ToolExecutor` / `BudgetTracker`
- `tool.llm` capability gating separate from `tool.python`
- Environment config: `EMERGENCE_LLM_PROVIDER`, `EMERGENCE_LLM_MODEL`, `EMERGENCE_LLM_BASE_URL`, `EMERGENCE_LLM_API_KEY`

#### Memory + RAG (M15)
- In-memory TF-IDF vector index (`emergence/memory/vector_index.py`)
- `memory.search` tool scoped to episodic/semantic memory
- Auto-indexing on episodic/semantic store operations

#### Cognitive AI plugins (M14, M16, M18)
- `plugins/planner/` — LLM-driven goal → TaskSpec decomposition
- `plugins/researcher/` — LLM research with RAG context
- `plugins/evaluator/` — LLM quality scoring, `EVALUATION_COMPLETED` events
- `plugins/research_assistant/` — end-to-end research pipeline

#### Human-in-the-loop (M17)
- `USER_MESSAGE_RECEIVED`, `USER_APPROVAL_REQUESTED`, `USER_APPROVAL_GRANTED` events
- `ProcessContext.wait_for_approval()` with auto-checkpoint
- `Kernel.grant_user_approval()` and `./eos approve <request_id>`

#### Kernel API
- `create_plan_from_goal()`, `spawn_planner_for_goal()`, `finalize_plan_from_planner()`
- Boot modes: `--plan "topic"`, `--research "topic"`

#### Tests
- 483 tests (21 new for M13–M18)

### Fixed
- `create_kernel_context()` no longer discards empty `Executor` instances (falsy `__len__` bug)

## [0.1.0] - 2026-07-05

First public release. EmergenceOS ships a working kernel, plugin ecosystem, cognitive orchestration primitives, and reference applications demonstrating long-running multi-process coordination.

### Added

#### Kernel & runtime
- `KernelContext` composition root with unified boot via `create_kernel_context()` and `build_kernel()`
- `ProcessContext` — gated access to state, memory, mailboxes, checkpoints, tools, and events
- Priority scheduler with `WAITING` / `BLOCKED` states, dependency graphs, and wake-on-event
- `LifecycleManager` with explicit state transitions and `PROCESS_FAILED` handling
- Mailbox manager with request/response correlation and `MessageReceivedEvent` mediation
- Resource budgets: execution time, token limits, tool invocations, and retries

#### Security
- Capability-based access control (`CapabilityManager`, `SecurityManager`)
- Gated wrappers for state, memory, mailboxes, events, checkpoints, and tools
- Declared capabilities in `ProcessDefinition` and plugin manifests

#### Memory & durability
- `MemoryManager` with working, episodic, and semantic categories
- `CheckpointManager` with auto-checkpoint on `WAITING` and restore support
- `EventStore` with append-only log, JSONL persistence, and deterministic replay
- `Supervisor` for retry and checkpoint-aware recovery on process failure

#### Execution & tools
- `Executor` with pluggable runners (`PythonRunner`)
- `ToolExecutor` — processes invoke tools only through `ProcessContext.tools`
- `ExecutionSpec` model separating runner backend from target

#### Observability
- `ObservabilityKernel` with metrics, tracing, and audit trail
- CLI: `./eos ps`, `top`, `sched`, `state`, `budget`, `metrics`, `trace`

#### Plugins
- Auto-discovery from `plugins/` via `plugin.yaml` manifests
- Reference plugins: `hello_world`, `heartbeat`, `job_worker`, `orchestrator`, `event_collector`

#### Cognitive infrastructure (M12)
- `Goal`, `Plan`, `Task` models and `CognitiveManager`
- `kernel.create_goal()`, `create_plan()`, `execute_plan()`

#### Tests
- 462 tests at v0.1.0 tag

[0.3.0]: https://github.com/nikheelpandey/EmergenceOS/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/nikheelpandey/EmergenceOS/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/nikheelpandey/EmergenceOS/releases/tag/v0.1.0

# Changelog

All notable changes to EmergenceOS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Plugin discovery from `/plugins` with `plugin.yaml` manifests
- `PluginManager` load/unload lifecycle with `PLUGIN_LOADED` / `PLUGIN_UNLOADED` events
- Reference plugins: `hello_world`, `planner`, `worker`, `heartbeat`, `event_collector`, `job_worker`, `orchestrator`

#### Cognitive infrastructure
- `Goal`, `Plan`, `Task` models and `CognitiveManager`
- Kernel APIs: `create_goal`, `create_plan`, `execute_plan`
- Task dependency graph feeds the scheduler

#### Applications & demos
- `boot.py` modes: default, `--demo`, `--goal`, `--services`
- System-model simulation (coordinator / researcher / evaluator)
- Long-running service fleet with multi-phase orchestration
- Shared helpers in `emergence/apps/long_running_runtime.py`

#### Tests
- 462 tests (unit + integration) with pytest and coverage reporting

### Changed
- `hello_world` migrated to plugin layout
- Kernel delegates lifecycle, security, and composition to dedicated subsystems
- `Request` unified with `Message` hierarchy (`kw_only` dataclasses)

### Removed
- Legacy monolithic capability/checkpoint modules under `emergence/core/`
- `emergence/scheduler/policies.py` (replaced by integrated scheduler)

### Documentation
- `milestone.md` — M1–M12 complete tracker
- `docs/building-applications.md` — guide for custom plugins and apps
- Updated `readme.md` for v0.1

[0.2.0]: https://github.com/nikheelpandey/EmergenceOS/releases/tag/v0.2.0
[0.1.0]: https://github.com/nikheelpandey/EmergenceOS/releases/tag/v0.1.0

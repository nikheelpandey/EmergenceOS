# EmergenceOS Architecture Diagram

EmergenceOS is an **event-driven operating system for AI agents**. The kernel is deterministic and never calls LLMs; intelligence lives in **plugins** — long-lived processes coordinated via mailboxes, events, capability-gated services, and a priority scheduler.

---

## 1. Layered System Overview

```mermaid
flowchart TB
    subgraph L4["Layer 4 — User / Ingress"]
        BOOT["boot.py"]
        EOS["./eos CLI"]
        REPL["KernelIngress REPL<br/>(eos&gt; prompt)"]
    end

    subgraph L3["Layer 3 — Applications"]
        direction TB
        subgraph Plugins["Auto-discovered Plugins (plugins/*)"]
            P_AI["AI: planner · researcher · evaluator · research_assistant"]
            P_SVC["Services: heartbeat · event_collector · job_worker · orchestrator"]
            P_DEMO["Demo: hello_world · worker"]
        end
        APPS["Built-in Apps (emergence/apps/)"]
        COG["CognitiveManager<br/>Goal → Plan → Task"]
    end

    subgraph L2["Layer 2 — Kernel Services"]
        direction TB
        K["Kernel<br/>(coordination only)"]
        SCH["Scheduler<br/>(priority + dependencies)"]
        LCM["LifecycleManager"]
        SUP["Supervisor<br/>(fault tolerance)"]
        MM["MailboxManager"]
        SS["StateStore"]
        MEM["MemoryManager"]
        CP["CheckpointManager"]
        TE["ToolExecutor"]
        OBS["ObservabilityKernel"]
        SEC["SecurityManager"]
    end

    subgraph L1["Layer 1 — Infrastructure"]
        EB["PersistingEventBus"]
        ES["EventStore<br/>(append-only log)"]
        EXE["Executor + Runners"]
        PM["PluginManager"]
        REPLAY["ReplayEngine"]
    end

    subgraph L0["Layer 0 — Domain Core (emergence/core/)"]
        CORE["Process · ProcessDefinition · Event<br/>Goal · Plan · Task · Budget · IDs"]
    end

    subgraph EXT["External (optional)"]
        OLLAMA["Ollama"]
        OPENAI["OpenAI-compatible API"]
        MOCK["Mock LLM (default)"]
    end

    L4 --> L3
    L3 --> K
    K --> L2
    L2 --> L1
    L1 --> L0
    TE --> EXT
```

**Dependency rule:** `core/` has zero infrastructure imports. Everything else depends inward on `core/`.

---

## 2. Kernel Internals & Composition Root

All services are wired in `create_kernel_context()` — the single composition root:

```mermaid
flowchart LR
    subgraph Boot["boot.py / eos serve"]
        BC["create_kernel_context()"]
        BK["build_kernel() / build_runtime()"]
    end

    subgraph KernelContext["KernelContext"]
        direction TB
        EB2["PersistingEventBus ← EventStore"]
        CAP["CapabilityManager → SecurityManager"]
        SCH2["Scheduler"]
        ST["StateStore"]
        PT["ProcessTable"]
        REG["ProcessRegistry"]
        MB["MailboxManager"]
        MEM2["MemoryManager ← MemoryStore"]
        CHK["CheckpointManager"]
        EXE2["Executor"]
        TOOLS["ToolExecutor ← ToolRegistry"]
        OBS2["ObservabilityKernel"]
        COG2["CognitiveManager"]
        PLG["PluginManager"]
    end

    subgraph Runtime["Runtime Objects"]
        K2["Kernel"]
        LCM2["LifecycleManager"]
        SUP2["Supervisor"]
        ING["KernelIngress REPL"]
    end

    BC --> KernelContext
    BK --> K2
    KernelContext --> K2
    K2 --> LCM2
    K2 --> SUP2
    K2 --> ING
```

---

## 3. Process Execution Lifecycle

```mermaid
stateDiagram-v2
    [*] --> CREATED: kernel.spawn()
    CREATED --> READY: PROCESS_READY
    READY --> RUNNING: scheduler dequeues
    RUNNING --> COMPLETED: run() returns
    RUNNING --> WAITING: ProcessWaiting exception
    WAITING --> READY: MessageReceived / state change / dependency satisfied
    RUNNING --> FAILED: unhandled error
    FAILED --> READY: Supervisor retry from checkpoint
    COMPLETED --> [*]
    FAILED --> [*]: max retries exceeded

    note right of WAITING
        Checkpoint saved
        Process re-executed on wake
    end note
```

**Execution pipeline:**

```mermaid
sequenceDiagram
    participant U as User / REPL
    participant K as Kernel
    participant S as Scheduler
    participant E as Executor
    participant R as PythonRunner
    participant P as Plugin (run function)
    participant PC as ProcessContext (gated)
    participant EB as EventBus

    U->>K: spawn(ProcessDefinition)
    K->>EB: PROCESS_CREATED / PROCESS_READY
    K->>S: enqueue(process_id)

    loop run_forever()
        S->>K: dequeue next ready process
        K->>EB: PROCESS_STARTED
        K->>PC: build gated context
        K->>E: execute(context)
        E->>R: resolve runner_key
        R->>P: run(context)

        alt normal completion
            P-->>K: return
            K->>EB: PROCESS_COMPLETED
        else long-running wait
            P-->>K: raise ProcessWaiting
            K->>EB: PROCESS_WAITING + checkpoint
        else failure
            P-->>K: exception
            K->>EB: PROCESS_FAILED
        end
    end
```

---

## 4. Communication Patterns

Processes **never call each other directly**. Two primary channels:

```mermaid
flowchart TB
    subgraph ProcessA["Process A (Plugin)"]
        PA["run(context)"]
    end

    subgraph ProcessB["Process B (Plugin)"]
        PB["run(context)"]
    end

    subgraph GatedAPI["ProcessContext — Capability-Gated Facades"]
        GS["GatedStateStore"]
        GM["GatedMemoryManager"]
        GE["GatedEventBus"]
        GMB["GatedMailboxManager"]
        GT["GatedToolAccess"]
        GC["GatedCheckpointManager"]
    end

    subgraph KernelServices["Kernel Services"]
        SS2["StateStore"]
        MEM3["MemoryManager"]
        EB3["PersistingEventBus"]
        MM2["MailboxManager"]
        TE2["ToolExecutor"]
        CP2["CheckpointManager"]
    end

    subgraph EventDriven["Event-Driven Wakeups"]
        MRE["MessageReceivedEvent"]
        SCE["StateChangedEvent"]
        PCE["ProcessCompletedEvent"]
    end

    PA --> GatedAPI
    GatedAPI --> KernelServices

    PA -->|"send(Message)"| GMB
    GMB --> MM2
    MM2 -->|"deliver"| PB
    MM2 --> MRE
    MRE --> EB3
    EB3 -->|"wake scheduler"| SCH3["Scheduler"]

    GE --> EB3
    EB3 --> ES2["EventStore"]
    EB3 --> SUP3["Supervisor"]
    EB3 --> COG3["CognitiveManager"]
```

**IPC message types** (`emergence/common/`): `Message`, `Request`, `Response`, `Command`

---

## 5. Security & Capability Model

Every kernel service exposed to a process is wrapped in a **Gated\*** facade. `SecurityManager.require()` enforces capabilities on every operation.

```mermaid
flowchart LR
    subgraph Spawn["On kernel.spawn()"]
        DEF["ProcessDefinition"]
        MAN["plugin.yaml<br/>required_capabilities"]
        GRANT["CapabilityManager.grant()"]
    end

    subgraph Defaults["Default Capabilities"]
        D1["state.read / state.write"]
        D2["event.publish / event.subscribe"]
        D3["message.send"]
    end

    subgraph Extra["Plugin-declared"]
        E1["tool.llm"]
        E2["tool.python"]
        E3["memory.read / memory.write"]
        E4["checkpoint.read / checkpoint.write"]
        E5["message.receive"]
    end

    subgraph Enforcement["Runtime Enforcement"]
        SM["SecurityManager"]
        GF["Gated Facades"]
        DENY["CapabilityDeniedError"]
    end

    DEF --> GRANT
    MAN --> GRANT
    Defaults --> GRANT
    Extra --> GRANT
    GRANT --> GF
    GF --> SM
    SM -->|"missing cap"| DENY
```

---

## 6. Plugin System

```mermaid
flowchart TB
    subgraph Discovery["Plugin Discovery"]
        SCAN["PluginManager.discover()"]
        YAML["plugins/*/plugin.yaml"]
        EP["entrypoint: module:function"]
    end

    subgraph Manifest["plugin.yaml Schema"]
        M1["name · runner · entrypoint"]
        M2["required_capabilities"]
        M3["max_execution_time_seconds"]
        M4["config"]
    end

    subgraph Registration["Registration"]
        PD["ProcessDefinition"]
        PR["PythonRunner"]
        REG2["ProcessRegistry"]
        EXE3["Executor.register_runner()"]
    end

    subgraph AllPlugins["10 Plugins"]
        direction LR
        hello["hello_world"]
        worker["worker"]
        planner["planner"]
        researcher["researcher"]
        evaluator["evaluator"]
        ra["research_assistant"]
        hb["heartbeat"]
        ec["event_collector"]
        jw["job_worker"]
        orch["orchestrator"]
    end

    SCAN --> YAML
    YAML --> Manifest
    YAML --> EP
    EP -->|"dynamic import"| PD
    PD --> REG2
    PR --> EXE3
    AllPlugins --> YAML
```

| Plugin | Role | Key capabilities |
|--------|------|-----------------|
| **hello_world** | Demo | `tool.python` |
| **worker** | Cognitive task worker | state |
| **planner** | LLM goal decomposition | `tool.llm`, state |
| **researcher** | LLM research + RAG | `tool.llm`, memory, messages |
| **evaluator** | LLM quality scoring | `tool.llm`, `event.publish` |
| **research_assistant** | End-to-end pipeline | LLM, memory, checkpoint, approval |
| **heartbeat** | Long-running service | memory, checkpoint, messages |
| **event_collector** | Event → episodic memory | memory, messages |
| **job_worker** | Mailbox work queue | memory, messages, `tool.python` |
| **orchestrator** | Multi-service coordinator | memory, state, messages |

---

## 7. Tool Invocation & LLM Boundary

The kernel **never** calls an LLM. Plugins invoke tools via `context.tools.invoke()`:

```mermaid
flowchart LR
    PLG2["Plugin"]
    GTA["GatedToolAccess"]
    TE3["ToolExecutor"]
    SM2["SecurityManager<br/>(capability check)"]
    TR["ToolRegistry"]
    BT["BudgetTracker"]

    subgraph Tools["Registered Tools"]
        echo["echo"]
        llm["llm.chat"]
        memsearch["memory.search"]
    end

    subgraph Providers["LLM Providers (env-configured)"]
        mock["mock (default)"]
        ollama["ollama → localhost:11434"]
        openai["openai-compatible API"]
    end

    PLG2 -->|"invoke('llm.chat', args)"| GTA
    GTA --> TE3
    TE3 --> SM2
    TE3 --> TR
    TE3 --> BT
    TR --> Tools
    llm --> Providers
    TE3 -->|"TOOL_REQUESTED / TOOL_COMPLETED"| EB4["EventBus"]
```

**Environment variables:** `EMERGENCE_LLM_PROVIDER`, `EMERGENCE_LLM_MODEL`, `EMERGENCE_LLM_BASE_URL`, `EMERGENCE_LLM_API_KEY`

---

## 8. Cognitive Pipeline

```mermaid
flowchart TB
    USER2["User / REPL / boot.py --plan"]

    subgraph Cognitive["CognitiveManager"]
        G["Goal"]
        PL["Plan"]
        T["Task(s)"]
    end

    subgraph Execution2["Kernel Orchestration"]
        SP1["spawn planner plugin"]
        SP2["spawn worker / researcher tasks"]
        DEP["Scheduler respects depends_on + priority"]
    end

    subgraph Plugins2["AI Plugins"]
        PLN["planner → llm.chat → writes plan to state"]
        WRK["worker → executes task"]
        RES["researcher → llm.chat + memory.search"]
        EVL["evaluator → llm.chat scoring"]
        RA2["research_assistant → full pipeline"]
    end

    USER2 --> G
    G --> SP1
    SP1 --> PLN
    PLN --> PL
    PL --> T
    T --> SP2
    SP2 --> WRK
    SP2 --> RES
    SP2 --> EVL
    SP2 --> RA2
    SP2 --> DEP
```

---

## 9. Persistence & Storage Layer

All storage is **in-memory today** (event sourcing foundation for future durability):

```mermaid
flowchart TB
    subgraph Stores["In-Memory Stores"]
        ES3["EventStore<br/>(append-only event log)"]
        MS["MemoryStore<br/>(working / episodic / semantic)"]
        VI["VectorIndex<br/>(TF-IDF RAG)"]
        SS3["StateStore<br/>(global key-value)"]
        CPS["InMemoryCheckpointStore<br/>(SQLite stub exists)"]
    end

    subgraph Managers["Managers (single ownership)"]
        EB5["PersistingEventBus → EventStore"]
        MM3["MemoryManager → MemoryStore + VectorIndex"]
        CP3["CheckpointManager → CheckpointStore"]
        ST2["StateStore"]
        RE2["ReplayEngine ← EventStore"]
    end

    EB5 --> ES3
    MM3 --> MS
    MM3 --> VI
    CP3 --> CPS
    RE2 --> ES3
```

---

## 10. Entry Points & Boot Modes

```mermaid
flowchart TD
    subgraph Entry["Entry Points"]
        B1["python boot.py"]
        B2["./eos serve"]
        B3["python boot.py --once ..."]
        B4["python boot.py --research / --plan"]
    end

    subgraph Modes["Boot Builders"]
        BR["build_runtime()<br/>persistent OS + platform services"]
        BK2["build_kernel()<br/>batch / single spawn"]
        BSD["build_system_model_demo()"]
        BLS["build_long_running_services()"]
        BRA["build_research_assistant()"]
        BPD["build_plan_demo()"]
    end

    subgraph Runtime2["Runtime"]
        RF["Kernel.run_forever()"]
        REPL2["KernelIngress REPL"]
        PLAT["Platform services:<br/>heartbeat · collector · workers · orchestrator"]
    end

    B1 -->|default| BR
    B2 --> BR
    B3 --> BK2
    B3 --> BSD
    B3 --> BLS
    B4 --> BRA
    B4 --> BPD

    BR --> PLAT
    BR --> RF
    BR --> REPL2
    BK2 --> RF
```

---

## 11. Architectural Invariants

| Invariant | Meaning |
|-----------|---------|
| **Kernel never thinks** | No LLM, planning, or reasoning in kernel code |
| **Single ownership** | Each mutable resource has exactly one manager |
| **Event-driven** | All cross-cutting communication via immutable events |
| **Capability security** | Least privilege on every gated service call |
| **Long-lived processes** | `wait_for_message()` → WAITING → checkpoint → wake → re-execute |
| **Composition root** | `boot_context.create_kernel_context()` is the only wiring point |
| **No direct IPC** | Processes communicate via mailboxes + events, never direct calls |

---

## 12. Repository Map

```
EmergenceOS/
├── boot.py                    # Primary entry point
├── eos                        # CLI wrapper → emergence.cli
├── emergence/
│   ├── core/                  # Domain model (no infra deps)
│   ├── kernel/                # Kernel, boot, mailboxes, lifecycle
│   ├── scheduler/             # Priority queue + dependencies
│   ├── executor/              # Runners + ToolExecutor
│   ├── events/                # EventBus, EventStore, replay
│   ├── security/              # Capabilities + Gated facades
│   ├── memory/                # MemoryManager + TF-IDF vector index
│   ├── checkpoint/            # Process snapshots
│   ├── cognitive/             # Goal → Plan → Task
│   ├── plugins/               # Plugin loader + manager
│   ├── tools/                 # LLM providers + tool registry
│   ├── observability/         # Metrics, tracing, CLI display
│   ├── cli/                   # eos subcommands
│   └── apps/                  # Built-in demos
├── plugins/                   # 10 auto-discovered plugins
├── tests/                     # 486 unit + integration tests
└── docs/                      # Design principles, guides
```

---

See also: [architecture.md](../architecture.md) for design philosophy and principles.

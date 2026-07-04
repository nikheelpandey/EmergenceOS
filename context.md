# EmergenceOS Development Context

## Vision

EmergenceOS is an operating system for autonomous intelligence.

The goal is **not** to build another AI agent framework.

The goal is to build an operating system whose "processes" are intelligent entities.

Processes may be:

- Python code
- LLMs
- Workflows
- Humans
- Remote services
- Future execution backends

The operating system itself should remain deterministic.

It coordinates intelligence.

It does not perform intelligence.

---

# Design Philosophy

EmergenceOS is inspired far more by Linux than by existing agent frameworks.

The core philosophy is:

- deterministic infrastructure
- intelligent processes
- event-driven architecture
- immutable value objects
- explicit ownership
- composition over inheritance
- dependency inversion
- declarative configuration
- small orthogonal abstractions

---



# Architectural Principles



## Separation of Concerns

Each subsystem owns exactly one responsibility.

Kernel

- owns coordination

Scheduler

- owns scheduling

Executor

- owns execution delegation

MemoryManager

- owns memory

CheckpointManager

- owns checkpoints

LifecycleManager

- owns lifecycle transitions

Processes

- own reasoning

---



## Event Driven

Processes never communicate directly.

Everything important eventually becomes an immutable Event.

Examples

- ProcessCreated
- ProcessStarted
- ProcessCompleted
- ToolExecuted
- MemoryStored
- CheckpointCreated

---



## Single Ownership

Every mutable object has exactly one owner.

Examples

Process lifecycle

→ LifecycleManager

Scheduling queue

→ Scheduler

Execution

→ Executor

Memory

→ MemoryManager

Checkpoints

→ CheckpointManager

Kernel owns orchestration only.

---



## Small Kernel

Kernel should never

- execute tools
- call LLMs
- plan
- summarize
- evaluate
- store memory

Kernel coordinates only.

---



# Repository Structure

```text
EmergenceOS/

boot.py

emergence/

    apps/

    core/

    events/

    executor/

    kernel/

    scheduler/

    memory/

    checkpoint/

    security/
```

---



# Current Core Objects



## [ids.py](http://ids.py)

Strongly typed IDs.

Implemented

- ProcessID
- GoalID
- PlanID
- TaskID
- EventID
- CheckpointID
- ProcessDefinitionID

These wrap UUID.

We intentionally avoid raw UUIDs.

Objects expose

```python
process.process_id

event.event_id

goal.goal_id
```

instead of generic `.id`.

---



## [state.py](http://state.py)

Contains

- ProcessState
- TaskState
- GoalState
- PlanState
- CheckpointState

Also contains transition maps.

Example

```text
CREATED

↓

READY

↓

RUNNING

↓

COMPLETED
```

Kernel/LifecycleManager validates transitions.

---



## [budget.py](http://budget.py)

Immutable ResourceBudget.

Contains limits only.

Currently

- token budget
- time
- retries
- tool invocations
- memory
- cost

Usage accounting will live elsewhere.

---



## [event.py](http://event.py)

Immutable Event.

Contains

```text
EventID

EventType

timestamp

source_process

correlation_id

causation_id

payload
```

Events are historical facts.

---



## process_definition.py

Immutable executable description.

Currently contains

```text
ProcessDefinitionID

name

description

version

implementation

default_budget

required_permissions

metadata
```

---



## [process.py](http://process.py)

Represents runtime process.

Contains

```text
ProcessID

ProcessDefinition

ProcessState

GoalID

ResourceBudget

ParentProcessID

timestamps
```

Contains helper methods

```python
ready()

start()

complete()

fail()

cancel()
```

Lifecycle ownership will eventually move into LifecycleManager.

---



# Infrastructure Built

## EventBus

Implemented.

Responsibilities

- subscribe
- unsubscribe
- publish

Currently synchronous.

Future

- async
- persistence
- replay
- distributed bus

---



## ProcessTable

Implemented.

Owns all running Process objects.

Stores

```text
ProcessID

↓

Process
```

Supports

- add
- remove
- get
- exists
- iteration

Kernel owns ProcessTable.

---



## Scheduler

Implemented.

FIFO scheduler.

Stores only

```text
ProcessID
```

NOT Process objects.

Supports

- enqueue
- dequeue
- peek
- contains

Duplicate scheduling prevented.

---



## Executor

Implemented.

Owns Runner registry.

Delegates execution.

Never executes anything itself.

Responsibilities

- register runners
- lookup runner
- delegate execution

---



## Runner

Abstract interface.

```python
run(process)
```

Nothing else.

Runner never

- changes lifecycle
- publishes events
- schedules work

---



## PythonRunner

Implemented.

Loads

```text
module:function
```

using

```python
importlib.import_module(...)
```

Calls

```python
run(process)
```

---



## ProcessRegistry

Implemented.

Stores

```text
name

↓

ProcessDefinition
```

Currently used during boot.

Eventually Kernel will own it.

---



# Kernel

Implemented.

Responsibilities

- spawn Process
- register Process
- enqueue Process
- execute scheduled Process
- publish lifecycle events

Kernel delegates

Scheduler

↓

Executor

↓

Runner

---

Kernel currently looks approximately like

```text
spawn()

↓

ProcessTable.add()

↓

Scheduler.enqueue()

↓

publish(ProcessCreated)
```

and

```text
run()

↓

while scheduler has work

↓

dequeue

↓

start process

↓

Executor.execute()

↓

complete process

↓

publish events
```

---



# Boot Sequence

Current boot flow

```text
boot.py

↓

EventBus

↓

ProcessTable

↓

Scheduler

↓

Executor

↓

ProcessRegistry

↓

LifecycleManager

↓

register PythonRunner

↓

register ProcessDefinition

↓

construct Kernel

↓

spawn hello_world

↓

Kernel.run()
```

---



# Hello World Application

First working application.

Located at

```text
emergence/apps/hello_world.py
```

Loaded dynamically through

```python
importlib
```

Execution path

```text
Kernel

↓

Executor

↓

PythonRunner

↓

importlib

↓

hello_world.run(process)
```

This pipeline now works end-to-end.

---



# Dependency Graph

Current dependency graph

```text
                    boot.py
                       │
                       ▼
                    Kernel
          ┌──────────┼──────────┐
          ▼          ▼          ▼
   ProcessTable  Scheduler   Executor
          │                     │
          │                     ▼
          │                 Runner
          │                     │
          ▼                     ▼
      Process             PythonRunner
          │                     │
          ▼                     ▼
 ProcessDefinition      importlib
                                │
                                ▼
                     emergence.apps.*
```

---

Core dependency graph

```text
            core
              ▲
              │
   ┌──────────┼──────────┐
   │          │          │
 kernel   scheduler  executor
   │          │          │
   └──────────┼──────────┘
              │
           applications
```

Dependencies always point inward.

Nothing in core imports infrastructure.

---



# Architectural Decisions



## ProcessDefinition != Process

This distinction is fundamental.

Equivalent to

Executable

↓

Running process

---



## Event-first

Subsystems should eventually communicate through events.

Not direct method calls.

---



## Strongly typed IDs

We intentionally expose

```python
process.process_id

goal.goal_id

event.event_id
```

instead of generic `.id`.

Reason

Avoid passing incorrect IDs accidentally.

---



## Immutable Core Objects

IDs

Events

Budgets

Definitions

should remain immutable whenever possible.

---



## Small abstractions

We intentionally postponed

- planner
- memory
- checkpoints
- permissions
- capabilities
- distributed execution

We want infrastructure first.

---



# Architectural Issue Discovered

Current ProcessDefinition contains

```python
implementation
```

Executor currently uses

```python
implementation

↓

Runner lookup
```

PythonRunner also uses

```python
implementation

↓

module:function
```

One field currently represents two concepts.

Future design

```python
runner="python"

implementation="emergence.apps.hello_world:run"
```

or

```python
ExecutionSpec(
    runner="python",
    target="emergence.apps.hello_world:run"
)
```

This refactor should happen before additional runners are added.

---



# Current Status

Working

✅ IDs

✅ Events

✅ Budgets

✅ ProcessDefinition

✅ Process

✅ EventBus

✅ ProcessTable

✅ Scheduler

✅ Executor

✅ Runner

✅ PythonRunner

✅ ProcessRegistry

✅ Kernel

✅ Boot

✅ Dynamic Python process execution

System successfully executes

```text
Kernel

↓

Scheduler

↓

Executor

↓

PythonRunner

↓

HelloWorld
```

---



# Next Refactoring

Highest priority

Separate

```text
runner

implementation
```

inside ProcessDefinition.

---

Second

Move lifecycle ownership completely into LifecycleManager.

Kernel should only orchestrate.

---

Third

Kernel should own ProcessRegistry.

boot.py should simply

```python
kernel.boot()

kernel.run()
```

---

Fourth

Introduce ExecutionSpec.

Future

```python
ExecutionSpec(
    runner="python",
    target="emergence.apps.hello_world:run",
    config={}
)
```

This becomes the contract for every execution backend.

---



# After Infrastructure

Next major systems

```text
MemoryManager

CheckpointManager

CapabilityManager

Permission model

Event Store

ExecutionSpec

ExecutionContext

Local Ollama Runner

Workflow Runner

Human Runner

Planner

Reflection

Multi-process orchestration
```

Only after these infrastructure pieces are in place should LLM-powered intelligence be added.

---



## Overall Project State

EmergenceOS now has its first complete vertical slice. A process can be defined, registered, scheduled, executed through a runner, and coordinated by the kernel. The infrastructure is intentionally minimal but already reflects the operating system design principles. The next phase should focus on strengthening the architecture through a few targeted refactors before introducing additional execution backends or intelligent processes. This will keep the core clean, deterministic, and extensible.
# EmergenceOS Architecture

> An operating system for autonomous intelligence.

---

# Vision

EmergenceOS is an operating system whose processes are intelligent entities.

Unlike traditional operating systems that schedule CPU-bound programs, EmergenceOS schedules autonomous processes that may be powered by:

- Python code
- Large Language Models
- Workflows
- Humans
- Remote services
- Future execution backends

The operating system itself remains deterministic.

Its responsibility is coordination, not intelligence.

---

# Design Philosophy

EmergenceOS is inspired by operating systems such as Linux rather than existing AI agent frameworks.

The system is built around several core principles.

## Deterministic Infrastructure

Infrastructure components never perform reasoning.

The Kernel, Scheduler, Executor, Memory Manager, and Checkpoint Manager remain deterministic.

Reasoning belongs exclusively inside Processes.

---

## Separation of Concerns

Every subsystem owns one responsibility.

| Component | Responsibility |
|-----------|----------------|
| Kernel | Coordination |
| Scheduler | Scheduling |
| Executor | Execution delegation |
| Lifecycle Manager | Process lifecycle |
| Memory Manager | Memory ownership |
| Checkpoint Manager | Checkpoint ownership |
| Process | Reasoning |

No subsystem performs another subsystem's job.

---

## Event-Driven Architecture

Processes never communicate directly.

All communication occurs through immutable Events.

Examples include:

- ProcessCreated
- ProcessStarted
- ProcessCompleted
- ToolExecuted
- MemoryStored
- CheckpointCreated

The Event Bus forms the backbone of communication.

---

## Single Ownership

Every mutable object has exactly one owner.

Examples:

- Process lifecycle → Lifecycle Manager
- Scheduling queue → Scheduler
- Process registry → Kernel
- Execution → Executor
- Memory → Memory Manager
- Checkpoints → Checkpoint Manager

This constraint prevents architectural ambiguity.

---

## Declarative Core

Core objects describe the world.

Subsystems operate on those objects.

Examples:

- ProcessDefinition describes an executable.
- Process describes a running instance.
- Event describes something that occurred.

---

# System Overview

```
                    User
                      │
                      ▼
                    Goal
                      │
                      ▼
             ProcessDefinition
                      │
                      ▼
                  Process
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ProcessTable   Scheduler     EventBus
                        │
                        ▼
                     Executor
                        │
                        ▼
                     Runner
                        │
                        ▼
              Python / LLM / Human /
              Workflow / Docker
```

---

# Repository Structure

```
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

# Core Domain

The `core` package contains the language of the operating system.

Nothing in `core` depends on infrastructure.

Infrastructure depends on `core`.

Current objects include:

- Process
- ProcessDefinition
- Event
- ResourceBudget
- Strongly typed IDs
- Lifecycle States

---

## ProcessDefinition

Represents an executable.

Immutable.

Contains metadata describing how a Process should be created.

---

## Process

Represents a running instance of a ProcessDefinition.

Contains runtime state only.

Owns no scheduling, execution, memory, or checkpoint logic.

---

## Event

Immutable historical fact.

Events are never modified after creation.

---

## ResourceBudget

Immutable limits assigned to a Process.

Tracks limits rather than usage.

---

# Kernel

The Kernel coordinates the operating system.

Current responsibilities:

- Spawn processes
- Register processes
- Schedule processes
- Delegate execution
- Publish lifecycle events

The Kernel intentionally does **not**:

- Call LLMs
- Execute tools
- Plan
- Store memory
- Perform reasoning

---

# Scheduler

The Scheduler owns the ready queue.

It stores only ProcessIDs.

Current scheduling policy is FIFO.

Scheduling policies may change without affecting the Kernel.

---

# Process Table

The ProcessTable owns all running Process objects.

Responsibilities:

- Register processes
- Retrieve processes
- Remove processes

It is the runtime directory of the operating system.

---

# Executor

The Executor owns execution delegation.

Responsibilities:

- Register Runners
- Resolve execution backend
- Delegate execution

The Executor never executes work directly.

---

# Runner

A Runner performs execution.

Examples:

- PythonRunner
- OllamaRunner
- DockerRunner
- WorkflowRunner
- HumanRunner

The Runner must never:

- Modify process state
- Publish events
- Schedule work

Its responsibility is execution only.

---

# Event Bus

The Event Bus provides communication between subsystems.

Current implementation is synchronous.

Future versions may support:

- Async dispatch
- Event persistence
- Replay
- Distributed messaging

---

# Boot Sequence

Current boot flow:

```
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

Register Runners

↓

Register Applications

↓

Construct Kernel

↓

Spawn Initial Process

↓

Kernel.run()
```

---

# Dependency Graph

```
                boot.py
                   │
                   ▼
                Kernel
         ┌────────┼────────┐
         ▼        ▼        ▼
 ProcessTable Scheduler Executor
                            │
                            ▼
                         Runner
                            │
                            ▼
                    Application Process
```

Dependencies always point inward.

```
                core
                  ▲
                  │
     ┌────────────┼────────────┐
     │            │            │
 kernel      scheduler     executor
     │            │            │
     └────────────┼────────────┘
                  │
               applications
```

The `core` package has no infrastructure dependencies.

---

# Current Status

Implemented:

- Strongly typed IDs
- Lifecycle states
- Events
- Resource budgets
- Process definitions
- Runtime processes
- Event Bus
- Process Table
- Scheduler
- Executor
- Runner abstraction
- Python Runner
- Process Registry
- Kernel
- Boot sequence
- Dynamic Python process execution

The system successfully executes a Process from registration through completion.

---

# Current Vertical Slice

```
Kernel

↓

Scheduler

↓

Executor

↓

PythonRunner

↓

Dynamic import

↓

Application

↓

Completion
```

This is the first end-to-end execution pipeline.

---

# Architectural Debt

The following refactors are intentionally postponed.

## Execution Specification

Currently:

```
implementation
```

represents both:

- execution backend
- execution target

These should become separate concepts.

Future direction:

```
ExecutionSpec

runner = "python"

target = "emergence.apps.hello_world:run"

config = {}
```

---

## Lifecycle Ownership

Process lifecycle currently lives partly in the Process object.

Long-term ownership belongs in the Lifecycle Manager.

The Kernel should become a pure coordinator.

---

## Process Registry

Currently wired manually during boot.

Eventually owned directly by the Kernel.

---

# Roadmap

Infrastructure

- ExecutionSpec
- Lifecycle Manager
- Memory Manager
- Checkpoint Manager
- Capability model
- Event Store
- Permission system

Execution

- Ollama Runner
- Docker Runner
- Workflow Runner
- Human Runner

Intelligence

- Planner
- Researcher
- Reflection
- Evaluator
- Multi-process orchestration

Applications

- Research Assistant
- Software Engineering
- Personal OS
- Autonomous Company
- Scientific Discovery

---

# Long-Term Goal

EmergenceOS should make intelligent systems feel like operating systems rather than chatbots.

Users interact with Goals.

The operating system coordinates Processes.

Processes perform reasoning.

The Kernel remains deterministic.
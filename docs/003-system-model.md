I think this is the document that will make or break the project.

If someone reads only **one** document besides the Vision, I want it to be this one. It should be detailed enough that an engineer unfamiliar with the project could implement the kernel without guessing the architecture.

---

# 003 - System Model

> *"Everything that exists within EmergenceOS and the rules governing their interactions."*

---

# Purpose

The System Model defines the ontology of EmergenceOS.

It specifies:

- what entities exist
- what each entity is responsible for
- who owns each entity
- how entities communicate
- what invariants must always hold
- what operations are permitted

This document is normative.

Implementations should conform to this model rather than redefine it.

---



# Architectural Layers

EmergenceOS consists of four logical layers.

```text
┌────────────────────────────────────────────┐
│                Applications                │
│                                            │
│ Research Assistant, Coding Swarm, etc.     │
└────────────────────────────────────────────┘
                    │
┌────────────────────────────────────────────┐
│          Cognitive Processes               │
│                                            │
│ Planner                                    │
│ Researcher                                 │
│ Evaluator                                  │
│ Reflector                                  │
└────────────────────────────────────────────┘
                    │
┌────────────────────────────────────────────┐
│               Kernel Services              │
│                                            │
│ Scheduler                                  │
│ Event Bus                                  │
│ Memory Manager                             │
│ Executor                                   │
│ Checkpoint Manager                         │
│ Security Manager                           │
└────────────────────────────────────────────┘
                    │
┌────────────────────────────────────────────┐
│              Infrastructure                │
│                                            │
│ SQLite                                     │
│ Filesystem                                 │
│ Ollama                                     │
│ HTTP                                       │
└────────────────────────────────────────────┘
```

Only adjacent layers communicate directly.

---



# Fundamental Entities

These are the only first-class entities recognized by the kernel.

```
Kernel
Process Definition
Process Instance
Goal
Plan
Task
Event
Message
Scheduler
Executor
Memory
Checkpoint
Capability
Permission
Resource Budget
```

Every higher-level abstraction must ultimately be composed from these entities.

---



# Entity Specifications



## Kernel



### Description

The kernel coordinates the execution of autonomous intelligence.

It owns every subsystem.

It owns no application logic.

---



### Responsibilities

- process lifecycle
- scheduler coordination
- event routing
- checkpoint coordination
- capability enforcement
- resource accounting
- observability

---



### Does NOT

- call language models
- plan
- evaluate outputs
- invoke tools directly
- store business logic

---



### Owns

```
Scheduler

Process Table

Memory Manager

Executor

Event Bus

Checkpoint Manager

Security Manager
```

---



## Process Definition

Equivalent to a program on disk.

Immutable.

Describes how a process behaves.

Contains

```
identifier

version

configuration schema

required capabilities

supported events

entrypoint
```

---



## Process Instance

A running process.

Equivalent to an operating system process.

Contains

```
PID

parent PID

goal reference

task reference

current state

working memory

checkpoint pointer

budget

permissions

metrics
```

Multiple instances may originate from one Process Definition.

---



## Goal

Represents an intended outcome.

Example

```
Write a technical report.

Implement a REST API.

Analyze quarterly revenue.
```

Goals are created by users or other processes.

Goals are immutable.

---



## Plan

A decomposition of a goal.

Contains

```
tasks

dependencies

constraints

priority

revision history
```

Plans evolve.

Goals do not.

---



## Task

Smallest schedulable unit of work.

Properties

```
identifier

parent plan

assigned process

status

dependencies

expected output
```

Tasks never invoke tools.

Processes execute tasks.

---



## Event

Immutable fact describing something that happened.

Examples

```
TaskCreated

PlanUpdated

CheckpointSaved

MemoryStored

ProcessStarted

ToolExecutionCompleted
```

Events are append-only.

---



## Message

Structured payload attached to an event.

The event expresses intent.

The message contains data.

---



## Memory

Represents retained information.

Categories

```
Working

Semantic

Episodic

Persistent
```

Memory is owned by the Memory Manager.

Never by processes.

---



## Checkpoint

Snapshot of recoverable state.

Includes

```
process state

working memory

event offset

resource usage

timestamps
```

A checkpoint must contain sufficient information to resume execution.

---



## Capability

Named operation exposed by the kernel.

Examples

```
Create Process

Publish Event

Store Memory

Retrieve Memory

Execute Tool

Create Checkpoint
```

Capabilities are granted through permissions.

---



## Permission

Authorization to invoke capabilities.

Examples

```
Filesystem

Network

Shell

Database

Tool Execution

Memory Write
```

Permissions are explicit.

Never implicit.

---



## Resource Budget

Defines execution limits.

Examples

```
Token Budget

Execution Time

Memory

API Calls

Cost

Retries
```

Every process has exactly one resource budget.

---



# Ownership Model

Every mutable entity has exactly one owner.


| Entity              | Owner              |
| ------------------- | ------------------ |
| Process lifecycle   | Kernel             |
| Process state       | Kernel             |
| Scheduling          | Scheduler          |
| Events              | Event Bus          |
| Memory              | Memory Manager     |
| Tool execution      | Executor           |
| Checkpoints         | Checkpoint Manager |
| Permissions         | Security Manager   |
| Resource accounting | Kernel             |


No entity may have multiple owners.

---



# Communication Model

Processes never communicate directly.

Instead

```
Process A

↓

Publish Event

↓

Event Bus

↓

Process B
```

This enables

- replay
- asynchronous execution
- loose coupling
- tracing

---



# State Model

Each process exists in one lifecycle state.

```
CREATED

READY

RUNNING

WAITING

BLOCKED

COMPLETED

FAILED

CANCELLED
```

A process cannot exist in multiple states simultaneously.

---

Allowed transitions

```
CREATED → READY

READY → RUNNING

RUNNING → WAITING

WAITING → READY

RUNNING → COMPLETED

RUNNING → FAILED

READY → CANCELLED

WAITING → CANCELLED
```

All transitions occur through the kernel.

---



# Process Hierarchy

Processes may spawn child processes.

```
Planner

├── Research

├── Coding

├── Evaluation

└── Reflection
```

Children inherit

- permissions
- budgets
- tracing context

unless explicitly overridden.

---



# Resource Model

Every process consumes resources.

```
Reasoning

↓

Tokens

↓

Cost

↓

Latency
```

Budgets are enforced before execution.

A scheduler may deny execution if sufficient resources are unavailable.

---



# Event Model

Events are immutable.

Every event contains

```
Event ID

Timestamp

Source PID

Event Type

Payload

Correlation ID

Causation ID
```

Events cannot be modified.

Corrections require publishing a new event.

---



# Memory Model

Processes never store memory directly.

Instead

```
Process

↓

Memory Request

↓

Memory Manager

↓

Memory Store
```

This allows

- centralized indexing
- eviction
- summarization
- retrieval policies

---



# Execution Model

Processes do not invoke tools.

Instead

```
Process

↓

Execution Request

↓

Executor

↓

Tool

↓

Result Event
```

Execution always returns through events.

---



# Failure Model

Failures are expected.

Recoverable failures include

```
Timeout

Tool Failure

Model Failure

Permission Denied

Resource Exhaustion
```

The kernel determines the recovery policy.

Possible actions

- retry
- rollback
- replan
- escalate
- terminate

---



# Security Model

Processes execute with least privilege.

Permissions are granted explicitly.

Capabilities are validated before execution.

No process bypasses the security manager.

---



# Invariants

The following statements must always hold.

### Identity

Every process has exactly one PID.

Every event has exactly one identifier.

Every task belongs to exactly one plan.

---



### Ownership

Every mutable entity has one owner.

Ownership never overlaps.

---



### Communication

Processes never invoke one another directly.

All communication passes through the event bus.

---



### Execution

Only the Executor invokes tools.

---



### Memory

Only the Memory Manager modifies memory.

---



### Scheduling

Only the Scheduler decides execution order.

---



### Lifecycle

Only the Kernel changes process states.

---



### Events

Events are immutable.

---



### Persistence

Every recoverable process has at least one checkpoint.

---



### Observability

Every state transition generates an event.

---



# System Sequence

A typical execution proceeds as follows:

```
User
 │
 ▼
Goal
 │
 ▼
Kernel
 │
 ▼
Planner Process
 │
 ▼
Plan
 │
 ▼
Scheduler
 │
 ▼
Research Process
 │
 ▼
Executor
 │
 ▼
Tool
 │
 ▼
Event Bus
 │
 ▼
Evaluator Process
 │
 ▼
Checkpoint
 │
 ▼
Completed Goal
```

---



# Design Implications

This model intentionally separates **coordination** from **cognition**.

The kernel coordinates execution but never reasons.

Processes reason but never coordinate the system.

This separation enables deterministic infrastructure, independent evolution of cognitive components, replayable execution, and robust failure recovery.

All future architectural decisions should reinforce this distinction rather than blur it.
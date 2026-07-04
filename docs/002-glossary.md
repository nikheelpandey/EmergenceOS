# 002 - Glossary

> *"Precise systems require precise language."*

---

# Purpose

This document defines the canonical terminology used throughout EmergenceOS.

The goal is to ensure that every architectural document, API, implementation, and discussion uses the same vocabulary.

Terms defined here have a single authoritative meaning within the project.

---

# Core Concepts

## Kernel

The deterministic runtime responsible for managing the lifecycle of intelligent processes.

The kernel never performs reasoning. It coordinates execution, allocates resources, manages state, and provides system services.

Responsibilities include:

* process lifecycle management
* scheduling
* event routing
* persistence
* checkpointing
* permissions
* resource accounting
* observability

The kernel is analogous to an operating system kernel.

---

## Process

The fundamental unit of intelligent work.

A process encapsulates a single cognitive responsibility.

Examples include:

* planning
* research
* code generation
* evaluation
* memory consolidation
* summarization

Every process has:

* a unique identifier
* executable logic
* internal state
* resource limits
* permissions
* lifecycle state
* checkpoint history

Processes are independent and replaceable.

---

## Process Definition

A process definition describes how a process behaves.

It is analogous to a program on disk.

It specifies:

* executable implementation
* required inputs
* expected outputs
* permissions
* configuration
* supported events

Multiple process instances may be created from a single process definition.

---

## Process Instance

A running execution of a process definition.

Each instance maintains its own:

* state
* memory
* resource usage
* lifecycle
* checkpoints

Multiple instances of the same process definition may execute concurrently.

---

## Scheduler

The subsystem responsible for deciding which processes execute and when.

The scheduler considers factors such as:

* priority
* dependencies
* deadlines
* waiting state
* resource availability
* token budgets

The scheduler never performs reasoning.

---

## Event

An immutable record describing something that has occurred.

Examples:

```text
TaskCreated

ResearchCompleted

ToolExecutionFailed

PlanUpdated

CheckpointCreated

UserApproved
```

Events are published to the event bus and may be consumed by one or many processes.

Events are append-only.

They are never modified after creation.

---

## Event Bus

The communication backbone of EmergenceOS.

Processes exchange information exclusively through events.

The event bus enables:

* asynchronous communication
* loose coupling
* replay
* monitoring
* auditing

Processes never invoke each other directly.

---

## Message

The payload carried by an event.

A message contains structured data describing the event.

For example:

```json
{
    "task_id": "...",
    "status": "completed",
    "duration_ms": 1342
}
```

The event describes *what happened*.

The message contains *the associated data*.

---

## Task

A unit of work assigned to a process.

Tasks are created during planning and executed by processes.

A process may execute multiple tasks during its lifetime.

Tasks are application-level concepts.

Processes are operating system concepts.

---

## Goal

The desired outcome requested by a user or another process.

Goals are intentionally high level.

Example:

> Produce a technical report comparing retrieval strategies.

Goals are decomposed into tasks through planning.

---

## Plan

A structured decomposition of a goal into executable tasks.

Plans may evolve over time.

They are expected to change as new information becomes available.

---

## Dependency

A relationship indicating that one process or task cannot begin until another has completed.

Dependencies form a directed execution graph.

The scheduler uses dependency information to determine execution order.

---

# State

## Process State

The current lifecycle status of a process.

Example states include:

* Created
* Ready
* Running
* Waiting
* Blocked
* Completed
* Failed
* Cancelled

State transitions are explicit.

---

## Working State

Short-lived internal information required during execution.

Examples include:

* temporary variables
* intermediate reasoning
* cached tool outputs

Working state may change frequently.

---

## Persistent State

Information that survives process restarts.

Persistent state enables recovery after interruptions.

---

## Checkpoint

A durable snapshot of a process at a specific moment in time.

A checkpoint includes sufficient information to resume execution without repeating completed work.

---

## Recovery

The act of restoring execution from one or more checkpoints.

Recovery should preserve correctness while minimizing repeated computation.

---

# Memory

## Memory

Stored information that may influence future reasoning.

Memory is managed by the operating system rather than individual processes.

---

## Working Memory

Short-term information immediately available during execution.

Working memory is analogous to RAM.

---

## Episodic Memory

Records of previous executions.

Examples include:

* completed tasks
* previous plans
* execution history
* tool usage

---

## Semantic Memory

Structured knowledge accumulated over time.

Examples include:

* documentation
* retrieved facts
* indexed knowledge
* embeddings

---

## Memory Store

The subsystem responsible for storing and retrieving memories.

Its implementation is independent of process execution.

---

# Resources

## Resource Budget

The maximum amount of resources allocated to a process.

Budgets may include:

* tokens
* execution time
* API calls
* memory
* cost

Processes exceeding their budget may be interrupted or terminated.

---

## Token Budget

The maximum number of language model tokens a process may consume.

The scheduler uses token budgets during resource allocation.

---

## Priority

A scheduling attribute indicating the relative importance of a process.

Priority influences execution order but does not guarantee execution.

---

## Timeout

The maximum permitted execution duration for a process.

Processes exceeding their timeout may transition to the Failed state.

---

# Execution

## Executor

The subsystem responsible for invoking external capabilities.

Examples include:

* language models
* shell commands
* databases
* HTTP APIs
* Python functions
* search engines

The executor performs actions.

It does not decide which actions should occur.

---

## Tool

An external capability available to a process.

Examples include:

* filesystem
* shell
* Git
* web search
* SQL database
* vector database

Tools are invoked through the executor.

---

## Capability

A named operation provided by the operating system.

Examples include:

* publish event
* create process
* store memory
* create checkpoint
* invoke tool

Capabilities define what processes are allowed to do.

---

# Security

## Permission

An explicit authorization allowing a process to perform a specific operation.

Examples include:

* filesystem access
* internet access
* shell execution
* database access

Permissions follow the principle of least privilege.

---

## Sandbox

An isolated execution environment restricting process behavior.

Sandboxes protect the operating system from unsafe or unintended actions.

---

# Observability

## Log

A chronological record describing internal system activity.

Logs are intended primarily for debugging and diagnostics.

---

## Trace

A complete execution path spanning multiple processes.

Traces connect related events across the system.

---

## Metrics

Numerical measurements describing system behavior.

Examples include:

* active processes
* average latency
* token consumption
* scheduler utilization
* checkpoint frequency

---

## Audit Trail

A complete historical record of system activity.

The audit trail should allow developers to reconstruct the execution of any process.

---

# Cognitive Concepts

## Reasoning

The process of producing new information from existing information.

Reasoning is performed exclusively by user-space processes.

The kernel never reasons.

---

## Reflection

A reasoning process that evaluates previous reasoning.

Reflection may produce improvements, corrections, or recommendations.

---

## Evaluation

The process of measuring whether an output satisfies predefined criteria.

Evaluation may trigger retries or replanning.

---

## Replanning

The modification of an existing plan in response to new information, failures, or changing constraints.

Replanning is expected behavior rather than an exceptional condition.

---

# Design Philosophy

Throughout EmergenceOS, terminology intentionally follows operating system conventions wherever practical.

Words such as *process*, *kernel*, *scheduler*, *event*, *resource*, *permission*, *checkpoint*, and *lifecycle* are preferred because they describe infrastructure concerns rather than model-specific behaviors.

Terms such as *agent*, *chain*, or *workflow* are intentionally avoided in the core architecture. While useful in other contexts, they often imply implementation choices or carry inconsistent meanings across frameworks.

By grounding the architecture in well-established systems concepts, EmergenceOS aims to provide a vocabulary that is stable, precise, and independent of any particular language model or AI paradigm.

---
id: SK-16
type: story
title: Refresh the graphify graph after a QA merge
status: done
blocked: false
---

## Description
The context provider `graphify query "$TICKET_TITLE"` only reads a graph; nothing builds or updates it. In the first real test project every stage got `graph file not found`. After `merge()` succeeds in `cmd_finish` for qa, run `graphify update .` on the base branch when graphify is installed and the project uses it (graphify in `context`, or `graphify-out/` exists). It's AST-only, zero tokens. A failure must not fail the ticket: log a warning. Also consider building the graph once at setup when graphify is selected and the project has code.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: after a successful QA merge, the runner runs `graphify update .` on the base branch when graphify is installed and the project uses it (`graphify-out/` exists or a context command calls graphify). A failure prints and logs a WARN; the ticket still goes to done. Setup and Settings build the graph once (`wizard.build_graph`) when a graphify context command is selected and there's no graph yet.
- **Tests**: `check_qa()` puts a fake `graphify` on PATH and checks it's called with `update .` after the merge.

## Review notes

## QA notes

## Log
- 2026-10-24T22:35 created → backlog
- 2026-10-25T11:18 backlog → done (built by hand while bootstrapping)

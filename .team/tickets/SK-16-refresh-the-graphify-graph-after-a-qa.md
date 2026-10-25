---
id: SK-16
type: story
title: Refresh the graphify graph after a QA merge
status: backlog
blocked: false
---

## Description
The context provider `graphify query "$TICKET_TITLE"` only reads a graph; nothing builds or updates it. In the first real test project every stage got `graph file not found`. After `merge()` succeeds in `cmd_finish` for qa, run `graphify update .` on the base branch when graphify is installed and the project uses it (graphify in `context`, or `graphify-out/` exists). It's AST-only, zero tokens. A failure must not fail the ticket: log a warning. Also consider building the graph once at setup when graphify is selected and the project has code.

## Acceptance criteria

## Technical notes

## Implementation notes

## Review notes

## QA notes

## Log
- 2026-10-24T22:35 created → backlog

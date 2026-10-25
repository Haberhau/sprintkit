---
id: SK-9
type: story
title: Block code edits when no ticket is in progress
status: done
blocked: false
---

## Description
A PreToolUse hook that refuses Edit/Write outside .team/ unless a ticket is in-progress. The core 'work like a team' guard from the original pitch; make it warn or block via config.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: `sprintkit/hooks/hooks.json` registers a PreToolUse hook on Edit|Write|MultiEdit|NotebookEdit that runs `scripts/guard.py`. The guard finds the project by walking up from the edited file to `.team/config.json`; outside sprintkit projects and inside `.team/` it's silent. With no ticket `in-progress` (build) or `testing` (qa): `"guard": "warn"` (default) adds context telling Claude the edit is outside the process, `"block"` refuses it (exit 2 with the reason), `"off"` does nothing. README and contract updated. This repo sets `"guard": "off"` while its own tickets are still built by hand.
- **Decisions**: warn by default, so installing the plugin never stops anyone's work unasked. `testing` counts as an editing stage because QA commits tests.
- **Tests**: `check_guard()` covers non-sprintkit folder, ticket file, warn, block, a ticket in build, and off.
- **Not verified**: the hook firing inside a real Claude Code session (part of SK-4).

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-25T11:22 backlog → done (built by hand while bootstrapping)

---
id: SK-18
type: story
title: Flag missing context tools and suggest common ones in setup
status: backlog
blocked: false
---

## Description
The Checks step (setup and Settings) only detects graphify, and shows no warning for context commands whose tool isn't installed. Someone without graphify sees "Nothing detected"; someone who uninstalled it later still has it listed as "from your config", and every stage silently gets the error text as context.

- Mark a context command whose first word isn't on PATH (e.g. "graphify not found: this command will fail") and leave it unticked by default for new setups.
- Suggest a couple of common tools when they're installed, e.g. `rg -l -i "$TICKET_TITLE"` (ripgrep), next to graphify.
- The add-command label lists only $TICKET_ID, $TICKET_TITLE, $TICKET_PATH; also name $TICKET_TYPE and $TICKET_BRANCH.

Relevant code: `discover()` in sprintkit/scripts/wizard.py (context detection), the Checks step in sprintkit/scripts/setup.html.

## Acceptance criteria

## Technical notes

## Implementation notes

## Review notes

## QA notes

## Log
- 2026-10-25T11:12 created → backlog

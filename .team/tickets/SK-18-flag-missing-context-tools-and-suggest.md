---
id: SK-18
type: story
title: Flag missing context tools and suggest common ones in setup
status: done
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
- **Changes**: `wizard.tool_missing()` checks a context command's program against PATH (skips `VAR=x` prefixes; unparsable commands count as present). `discover()` returns `contextMissing` for detected and configured commands, and offers `git log --oneline -15` as an unticked suggestion in git repos. setup.html shows a red "isn't installed" line under missing commands, leaves them unticked in new setups, and the add-command label names all five ticket variables.
- **Decisions**: suggested `git log` instead of ripgrep: a title search with rg rarely matches code, while recent commits are always available and useful. Commands typed into the field are checked on the next load, not live.
- **Tests**: `check_setup()` asserts a configured command with a missing tool shows up in `contextMissing`.

## Review notes

## QA notes

## Log
- 2026-10-25T11:12 created → backlog
- 2026-10-25T11:15 backlog → done (built by hand while bootstrapping)

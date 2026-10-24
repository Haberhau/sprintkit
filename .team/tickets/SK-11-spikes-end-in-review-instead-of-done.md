---
id: SK-11
type: bug
title: Spikes end in review instead of done
status: done
blocked: false
---

## Description
Contract §5 says spikes end at `done` and are never released. Today build moves every ticket to in-review, spikes included. Fix together with the review stage.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: the pass status now comes from the ticket's flow (`passed_status()` in `team.py`): the status the next stage waits in, or `done` after the last stage. Spikes and chores end at `done`, stories go to `in-review`, bugs to `in-qa`.
- **Tests**: `check_review()` checks spike and chore builds end at `done`.

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-24T16:59 backlog → done (built by hand while bootstrapping, before the review stage existed)

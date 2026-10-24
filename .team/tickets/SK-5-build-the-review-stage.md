---
id: SK-5
type: story
title: Build the review stage
status: done
blocked: false
---

## Description
Specified in docs/stage-contract.md §4: reviewer executor writes Review notes ending in `VERDICT: approve|changes`; approve → in-qa, changes → back to refined with notes for the next build.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: `review` stage in `team.py` (status `reviewing`, checks out the branch, prints the diff stat, verdict gate on the last line of Review notes); new `agents/reviewer.md` and `skills/review/SKILL.md`; reviewer is the default in DEFAULT_CONFIG, wizard and setup screen; board knows `reviewing`, `in-qa`, `done`.
- **Decisions**: a missing verdict goes back to `in-review` (rerun review) instead of `refined`, so an unfinished review doesn't trigger a rebuild. Contract updated. The autopilot counts failures across all stages, so build/review ping-pong gets blocked after `max_attempts`.
- **Tests**: `check_review()` in `test_team.py` covers no verdict, changes → bounce-back with notes, block after repeated rejections, approve → in-qa.
- **Not verified**: the reviewer agent in a real Claude Code session (SK-4).

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-24T16:59 backlog → done (built by hand while bootstrapping, before the review stage existed)

---
id: SK-12
type: story
title: Tell setup failures apart from failing tests in gates
status: done
blocked: false
---

## Description
In the thought-dump test, two gate failures were a wrong simulator (exit 70) and one a flaky simulator launch (exit 65), all shown like test failures. Options: show the exit code meaning, retry once on infrastructure exit codes.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: `gate_setup_problem()` in team.py classifies a failed user gate as an environment problem on exit 127/126, or on output only the environment produces (`Unable to find a destination matching`, simulator/test-runner launch failures). Flaky launches are retried once (`RETRY:` line). In block mode a setup problem blocks the ticket (status unchanged, dequeued, not counted as a failed attempt) instead of bouncing it; in warn mode the WARN message is labelled "setup problem, not a test failure". Skills and the contract explain the new BLOCKED case.
- **Decisions**: no classification by exit code 65/70 alone: xcodebuild returns 65 for failing tests too, so only output patterns that can't come from a failing test are used.
- **Tests**: `check_gate_setup()`: missing command → blocked; failing test → normal FAIL; flaky simulator launch → retried and passes.

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-25T11:19 backlog → done (built by hand while bootstrapping)

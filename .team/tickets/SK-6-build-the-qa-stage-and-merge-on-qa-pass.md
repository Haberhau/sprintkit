---
id: SK-6
type: story
title: Build the QA stage and merge on QA pass
status: done
blocked: false
---

## Description
Contract §4: executor writes tests per acceptance criterion and ticks the boxes; gate runs the user's test command; pass merges the branch into the base branch → done; fail → back to refined.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: `qa` stage in `team.py` (status `testing`, checks out the branch). Gate: ≥1 AC item and all ticked, QA notes non-empty, clean tree, then the user's qa gate. On pass the runner merges the branch into the base branch with `--no-ff` (`merge()`) → `done`. New `agents/qa-engineer.md` and `skills/qa/SKILL.md`; qa-engineer is the default in config, wizard and setup screen; board knows `testing`.
- **Decisions**: a merge conflict aborts the merge and blocks the ticket in `in-qa` instead of failing the gate, since rerunning QA can't fix it. Bugs skip refine, so QA writes their AC if there are none (contract updated). SK-13 isn't needed first: tickets are never committed on feature branches, so merges don't touch `.team/`.
- **Tests**: `check_qa()` covers bounce-back on unticked AC, uncommitted tests, merge commit on pass, conflict → blocked with main untouched. Also fixed a flaky prefix assertion in `check_setup()` (random temp folder names).
- **Not verified**: the qa-engineer agent in a real Claude Code session (SK-4).

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-24T21:18 backlog → done (built by hand while bootstrapping, before the qa stage existed)

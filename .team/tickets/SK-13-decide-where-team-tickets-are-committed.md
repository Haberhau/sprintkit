---
id: SK-13
type: spike
title: Decide where .team/ tickets are committed
status: done
blocked: false
---

## Description
Ticket files change on feature branches while status lives in them, so they can drift between branches. Options: commit only on the base branch, keep .team/ out of feature branches, or move status out of the files.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Decision record**: `docs/decisions/SK-13-where-team-tickets-are-committed.md`. Reproduced the drift: with `.team/` tracked, committing tickets on main while a ticket branch is open makes `git checkout <branch>` fail on the edited ticket file, which kills `start review`/`start qa` mid-stage. Ignored `.team/` never conflicts. Compared four options (ignore, track on base only, status in a separate file, orphan branch/worktree).
- **Recommendation, implemented**: `.team/` is git-ignored by default. `wizard.ignore_team()` adds `.team/` to `.gitignore` at setup and `team.py init`, unless the project already tracks `.team` on purpose (like this repo, where all ticket commits happen on main).
- **Follow-ups**: if shared tickets across machines are ever needed, revisit "status in an ignored file, ticket text tracked".

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-25T11:21 backlog → done (built by hand while bootstrapping)

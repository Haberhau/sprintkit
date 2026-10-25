---
id: SK-17
type: bug
title: Build gate forces committing pre-existing untracked files
status: done
blocked: false
---

## Description
The build and qa gates fail on any `git status --porcelain` output outside .team/, including untracked files that existed before the ticket. In the first real test project, its first ticket's developer had to commit unrelated `docs/`, `tools/`, `.gitignore` and `.claude/settings.json` on the ticket branch. Expected: only changes made by the stage count (e.g. modified tracked files, or untracked files not present when the stage started). Options: snapshot untracked files at `start` and ignore those at `finish`, or have setup commit or ignore existing files once.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: `start` for build and qa records the untracked files that already exist in `.team/untracked.json` (not on resume, so a retry doesn't adopt files from the failed attempt). The clean-tree gate (`uncommitted()`) now flags edited tracked files plus untracked files new since start, and names them. Developer and QA agents are told to leave pre-existing untracked files alone.
- **Decisions**: snapshot at start rather than a setup-time commit: it also covers files that appear between tickets, and never commits anything on the user's behalf.
- **Tests**: `check_qa()`: a file untracked before build starts passes, a file created during build fails with its name.

## Review notes

## QA notes

## Log
- 2026-10-24T22:35 created → backlog
- 2026-10-25T11:18 backlog → done (built by hand while bootstrapping)

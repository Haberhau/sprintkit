---
id: SK-17
type: bug
title: Build gate forces committing pre-existing untracked files
status: backlog
blocked: false
---

## Description
The build and qa gates fail on any `git status --porcelain` output outside .team/, including untracked files that existed before the ticket. In the first real test project, its first ticket's developer had to commit unrelated `docs/`, `tools/`, `.gitignore` and `.claude/settings.json` on the ticket branch. Expected: only changes made by the stage count (e.g. modified tracked files, or untracked files not present when the stage started). Options: snapshot untracked files at `start` and ignore those at `finish`, or have setup commit or ignore existing files once.

## Acceptance criteria

## Technical notes

## Implementation notes

## Review notes

## QA notes

## Log
- 2026-10-24T22:35 created → backlog

---
id: SK-2
type: chore
title: Fill in the author field in plugin.json
status: done
blocked: false
---

## Description
`claude plugin validate` warns that `author` is missing in `sprintkit/.claude-plugin/plugin.json`. Add name (and optionally email/url).

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: `author` (name, GitHub url) in `sprintkit/.claude-plugin/plugin.json`. No email, since the repo is going public.
- **Criteria**: `claude plugin validate ./sprintkit` passes without warnings.

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-25T11:14 backlog → done (built by hand while bootstrapping)

---
id: SK-8
type: story
title: Build the sprint retro
status: done
blocked: false
---

## Description
Contract §4: reads the Log sections of the sprint's tickets (bounce-backs, gate failures, durations) and writes sprints/<n>/retro.md with one concrete process change.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: `team.py retro start|finish [version]`, `scrum-master` agent, `/sprintkit:retro` skill. Start computes per-ticket numbers from the Logs with zero tokens (`ticket_stats`: bounce-backs, gate failures, warnings, blocks, hours from first refine/build start to done) and prints them with the Logs; finish requires `.team/retros/<version>.md` with a non-empty `## Process change` and logs it on the release file. The skill asks before applying the proposed change. Retro is an executor slot in setup/Settings.
- **Decisions**: per release, not per sprint: there are no sprint objects (the autopilot works a queue), and a release is the batch actually finished together. Agent named scrum-master instead of the contract's product-owner, which never existed. Contract updated.
- **Tests**: in `check_release()`: stats row for a ticket with one review bounce and 3.5 h cycle time, released-only tickets, missing file and missing process change fail, unknown version refused.

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-25T11:26 backlog → done (built by hand while bootstrapping)

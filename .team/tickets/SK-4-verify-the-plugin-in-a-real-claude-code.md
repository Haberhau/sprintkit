---
id: SK-4
type: chore
title: Verify the plugin in a real Claude Code session
status: backlog
blocked: false
---

## Description
All tests so far ran the skills' steps by hand because the headless CLI was signed out. Check in a real session: skills resolve `${CLAUDE_PLUGIN_ROOT}`, `/sprintkit:refine` dispatches to the `sprintkit:tech-lead` agent, `/sprintkit:sprint` loops without asking.

## Acceptance criteria
- [ ] After a restart, `/sprintkit:` in the Claude Code app's prompt box lists init, ticket, board, refine, build, review, qa, sprint, release and retro.
- [ ] `/sprintkit:init` in a fresh folder runs the runner without asking where `team.py` is (`${CLAUDE_PLUGIN_ROOT}` resolves), and the setup screen opens in the app's browser pane.
- [ ] `/sprintkit:refine <ID>` dispatches an Agent call with `subagent_type: sprintkit:tech-lead` (not general-purpose), and the same holds for build/developer, review/reviewer, qa/qa-engineer.
- [ ] The runner's Bash calls don't ask for permission each time (the skills' `allowed-tools`); note it if they do.
- [ ] `/sprintkit:sprint` with 2–3 queued tickets (a story, a bug, a spike) loops without asking between tickets, and the board shows the cards moving.
- [ ] With no ticket in progress, asking Claude to edit a code file shows the guard's warning (default `"guard": "warn"`).
- [ ] `/sprintkit:release` then `/sprintkit:retro` produce a tag, a CHANGELOG.md entry and `.team/retros/<version>.md`.

## Technical notes
Run it in a new session (not one with a long history: stages inherit nothing from it, but the main side still pays for its context). Install state: `sprintkit@sprintkit` from the local marketplace at this repo, user scope; after changing the plugin, bump `version` in `sprintkit/.claude-plugin/plugin.json`, run `claude plugin marketplace update sprintkit` and `claude plugin update sprintkit@sprintkit`, then restart the app.
Good test project: a tiny one with a real test command, e.g. a Python module plus pytest, with `python3 -m pytest` as a blocking build and qa gate. Write down what breaks as new tickets.

## Implementation notes

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog

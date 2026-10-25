---
id: SK-4
type: chore
title: Verify the plugin in a real Claude Code session
status: done
blocked: false
---

## Description
All tests so far ran the skills' steps by hand because the headless CLI was signed out. Check in a real session: skills resolve `${CLAUDE_PLUGIN_ROOT}`, `/sprintkit:refine` dispatches to the `sprintkit:tech-lead` agent, `/sprintkit:sprint` loops without asking.

## Acceptance criteria
- [x] After a restart, `/sprintkit:` in the Claude Code app's prompt box lists init, ticket, board, refine, build, review, qa, sprint, release and retro.
- [x] `/sprintkit:init` in a fresh folder runs the runner without asking where `team.py` is (`${CLAUDE_PLUGIN_ROOT}` resolves), and the setup screen opens in the app's browser pane.
- [x] `/sprintkit:refine <ID>` dispatches an Agent call with `subagent_type: sprintkit:tech-lead` (not general-purpose), and the same holds for build/developer, review/reviewer, qa/qa-engineer.
- [x] The runner's Bash calls don't ask for permission each time (the skills' `allowed-tools`); note it if they do.
- [x] `/sprintkit:sprint` with 2–3 queued tickets (a story, a bug, a spike) loops without asking between tickets, and the board shows the cards moving.
- [x] With no ticket in progress, asking Claude to edit a code file shows the guard's warning (default `"guard": "warn"`).
- [x] `/sprintkit:release` then `/sprintkit:retro` produce a tag, a CHANGELOG.md entry and `.team/retros/<version>.md`.

## Technical notes
Run it in a new session (not one with a long history: stages inherit nothing from it, but the main side still pays for its context). Install state: `sprintkit@sprintkit` from the local marketplace at this repo, user scope; after changing the plugin, bump `version` in `sprintkit/.claude-plugin/plugin.json`, run `claude plugin marketplace update sprintkit` and `claude plugin update sprintkit@sprintkit`, then restart the app.
Good test project: a tiny one with a real test command, e.g. a Python module plus pytest, with `python3 -m pytest` as a blocking build and qa gate. Write down what breaks as new tickets.

## Implementation notes
- **Ran**: a real test in the Claude Code desktop app on 2026-10-25, with sprintkit installed from the local marketplace (0.2.1 → 0.2.5 during the run). Part 1 in the authoring session: the installed skills loaded and `${CLAUDE_PLUGIN_ROOT}` resolved; `/sprintkit:init` and the setup screen worked in the app's browser pane (config, `.team/` ignored, graph built); `/sprintkit:ticket` worked. Part 2 in a fresh app session ([[sk4-app-test]]) on `apptest/` (story, bug, spike, blocking unittest gates): all six `sprintkit:*` agents registered and every stage dispatched to them (no general-purpose fallback); no permission prompts for the runner; `/sprintkit:sprint` ran the queue without questions; APPT-1 and APPT-2 went through to merge; the guard hook warned on an out-of-process edit; `/sprintkit:release` tagged v0.1.0 with a committed changelog; `/sprintkit:retro` wrote a retro with one process change.
- **Bugs found and fixed during the run**: setup left a tracked `.gitignore` edited (now committed by setup); agents of a plugin installed mid-session aren't registered (skills fall back to general-purpose with the agent file); new `graphify-out/` files failed the clean-tree gate (now excluded); a ticket blocked in build held the one-at-a-time slot and deadlocked the autopilot (blocked tickets free it, `next` skips unstartable builds); a resumed stage reran its executor on already-passing output (`READY: yes` skips it); refine redirected the spike's decision record into the git-ignored ticket (tech-lead now points to `docs/decisions/`); spikes and chores reached done without their branch being merged (the runner now merges whenever a ticket reaches done); the retro counted the `blocked:` line as a gate failure.
- **Not covered**: a push to a real remote (tags stay local by design), and a project with a long-running gate (xcodebuild); the first real Swift project covers the latter once it updates.

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-25T12:18 backlog → done (built by hand while bootstrapping)

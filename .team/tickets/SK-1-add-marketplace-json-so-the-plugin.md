---
id: SK-1
type: chore
title: Add marketplace.json so the plugin installs from GitHub
status: done
blocked: false
---

## Description
The plugin lives in `sprintkit/`, and Claude Code installs plugins from a marketplace. Add `.claude-plugin/marketplace.json` at the repo root pointing at `./sprintkit`, then check `/plugin marketplace add Haberhau/sprintkit` and `/plugin install sprintkit@...` work.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: `.claude-plugin/marketplace.json` at the repo root, one plugin with `source: ./sprintkit`.
- **Criteria**: `claude plugin validate .` passes. Installed locally with `claude plugin marketplace add <repo path>` and `claude plugin install sprintkit@sprintkit`: it lands in `~/.claude/plugins/cache/sprintkit/…`, is enabled in user scope, and so loads in the desktop app too, unlike `--plugin-dir`. From GitHub: `/plugin marketplace add Haberhau/sprintkit` once the repo is public (SK-3).
- **For review/QA**: a local install copies the working tree. After changes, bump the version and run `claude plugin update sprintkit@sprintkit`, then restart.

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-25T11:14 backlog → done (built by hand while bootstrapping)

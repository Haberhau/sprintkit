---
id: SK-7
type: story
title: Build the release stages: sanity and deploy
status: done
blocked: false
---

## Description
Contract §4: release-level, batches all done tickets. Sanity runs the user's smoke command on the base branch; deploy writes a changelog, tags, runs the deploy command → released.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: `team.py sanity [--version]` and `team.py deploy start|finish`, a `release-manager` agent and the `/sprintkit:release` skill. Sanity: base branch must be clean, runs `gates.sanity` with `RELEASE_VERSION`; pass writes `.team/releases/<version>.md` and moves non-spike done tickets to release-candidate; fail changes nothing and offers a bug ticket. Deploy: start prints the tickets and commits since the last tag for the changelog executor; finish requires the committed CHANGELOG.md to mention the version, runs `gates.deploy`, then creates an annotated tag and marks tickets released. Deploy is the default executor slot in setup/Settings; the board treats release-candidate and released as real columns.
- **Decisions**: version = last `v*` tag bumped (minor with a story, patch otherwise, first `v0.1.0`), overridable. The deploy gate always blocks, since a failed deploy isn't a release. The tag is created after the deploy command succeeds and is never pushed by the runner. No sanity/deploy command configured → WARN and continue, so a project without deploys can still cut tagged releases.
- **Tests**: `check_release()`: sanity fail/pass, spikes stay done, missing changelog, failing deploy, tag + released, patch bump.

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-25T11:24 backlog → done (built by hand while bootstrapping)

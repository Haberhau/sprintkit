---
id: SK-14
type: chore
title: Test creating a GitHub repo from the setup wizard
status: done
blocked: false
---

## Description
The 'Create a new repository' path (gh repo create --source . --push) has only been validated, never run. Run it once against a throwaway repo and delete it afterwards.

## Acceptance criteria

## Technical notes

## Implementation notes
- **Ran**: POST /api/setup with `github: {mode: create, name: sprintkit-wizard-test, visibility: private}` on a scratch folder holding one untracked `app.py`. All steps ok: git init, initial commit, config, `.team/` added to `.gitignore`, `gh repo create … --source . --remote origin --push`. `gh repo view` confirmed a private repo with `main`, and origin points at it.
- **Observed**: the pushed repo holds only the empty initial commit; existing files and the new `.gitignore` stay untracked. That matches SK-17 (sprintkit never commits the user's files), but a user expecting their code on GitHub has to commit and push once. Worth one line on the setup screen if it confuses anyone.
- **Cleanup**: `gh repo delete` needs the `delete_repo` scope, which the gh token lacks; the owner deletes Haberhau/sprintkit-wizard-test (`gh auth refresh -h github.com -s delete_repo`, then `gh repo delete Haberhau/sprintkit-wizard-test --yes`, or on GitHub).

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-25T11:35 backlog → done (built by hand while bootstrapping)

# sprintkit

Run solo projects the way a real dev team does: tickets, stages, quality gates.
sprintkit owns the **process**. You choose **who** does each stage: the shipped agents, your own agents and skills, a shell command, or yourself.

```
backlog ─refine─▶ refined ─build─▶ in-review ─review─▶ in-qa ─qa─▶ done ─sanity─▶ ─deploy─▶ released
```

MVP status: `refine`, `build`, `review`, `qa` (merges into the base branch on pass), `sanity` + `deploy` (`/sprintkit:release`), `retro`, the live board and the sprint autopilot work end to end. The full contract is in [docs/stage-contract.md](../docs/stage-contract.md).

## Try it

Install (works in the Claude Code app and the terminal):
```
/plugin marketplace add Haberhau/sprintkit
/plugin install sprintkit@sprintkit
```
For development, `claude --plugin-dir ./sprintkit` loads it straight from a checkout, in the terminal only: the desktop app ignores `--plugin-dir`.

Then, in your project:
```
/sprintkit:init                      (or: /sprintkit:init new my-app)
/sprintkit:ticket story Users can switch to dark mode
/sprintkit:refine APP-1
/sprintkit:build APP-1
/sprintkit:review APP-1
/sprintkit:qa APP-1
/sprintkit:release
/sprintkit:retro
/sprintkit:board
```

## Setup

`/sprintkit:init` takes care of the folder (a browser can't pick one), then opens a setup screen:

1. **Project**: folder, git status (runs `git init` and an empty first commit if needed), ticket prefix.
2. **GitHub**: keep the existing remote, link a repo, create one with `gh` (pushes the current commits), or skip.
3. **Team**: who runs each stage. Every agent and skill you have installed is offered, grouped by plugin, plus "me". Plugins you don't need here can be switched off for this project. That's written to `.claude/settings.json` and merged with what's already there.
4. **Checks**: detected context providers (graphify) and a build gate guessed from the project (`npm test`, `pytest`, `cargo test`, `go test`, `make test`, or `xcodebuild` on the newest iPhone simulator by ID), in warn or block mode.
5. **Review**: shows exactly what will be written before anything changes.

Afterwards the same page is the board. Setup runs once.

**Settings** (button on the board) reopens the same screens on one page to change who runs each stage, plugins, context, the build gate, autopilot attempts, and GitHub (if not connected yet).
Anything the screen doesn't show is kept as you wrote it: `flows`, gates for other stages, custom executors such as `{"command": "./qa.sh"}`. The ticket prefix and base branch are fixed after setup, because existing tickets and branches depend on them.

## The board

`/sprintkit:board` starts a local board at `http://127.0.0.1:7700` (`/sprintkit:board text` for the terminal version).

- Cards move by themselves as stages run, with a highlight when they arrive.
- A failed gate shows on the card in red, with the reason.
- **New ticket** creates tickets. Click a card for its full history.
- The ▶ button on a card copies the next command, e.g. `/sprintkit:build APP-3`, to paste into Claude Code.
- Cards can't be dragged between stages. They only move when a stage passes its gate.

## Sprint autopilot

Drag cards into the **Sprint queue** lane (or click "+ Add to sprint queue"), then run `/sprintkit:sprint`.
It works through the queue in order, running each ticket's next stage with the configured executors, without asking in between.
Watch the cards move on the board.

- A ticket leaves the queue once the autopilot can't take it further (for now: once it's `done`).
- A ticket that fails the same stage's gate twice is marked **blocked** and skipped (`"autopilot": {"max_attempts": 2}`). Re-queueing it means "try again".
- A ticket the reviewer sends back goes to build again with the review notes. Review rejections count as failures, so a ticket that keeps bouncing gets blocked too.
- A ticket that passes QA but conflicts with the base branch is blocked; nothing is merged.
- Stages set to `{"human": true}` are blocked, not guessed at.
- Every build branch starts from the base branch, so tickets never stack on each other's unreviewed work.

The server only listens on 127.0.0.1, rejects other `Host` headers, and only accepts JSON posts, so other websites can't create tickets.

## Releases

`/sprintkit:release` ships every `done` ticket (spikes are never released):
1. **Sanity** runs `gates.sanity` (e.g. `npm run build && npm run smoke`) on the base branch. Pass → the tickets become release candidates, listed in `.team/releases/<version>.md`. Fail → nothing changes, and you're offered a bug ticket with the output.
2. **Deploy**: the release-manager agent writes and commits a `CHANGELOG.md` entry, then the runner runs `gates.deploy`, tags the version and marks the tickets released. The tag isn't pushed.

The version is the last `v*` tag bumped: minor when a story is included, patch otherwise, or `/sprintkit:release v2.0.0`. Release commands get `RELEASE_VERSION` in their environment.

`/sprintkit:retro` looks back on the latest release: the runner counts bounce-backs, gate failures, blocks and hours per ticket from their Logs, and the scrum-master agent writes `.team/retros/<version>.md` with one concrete process change, which you can apply or not.

## Guard

A hook checks every Edit/Write in a sprintkit project: code changes are expected while a ticket is being built or tested. Without one, Claude is told the edit happens outside the process. Ticket files in `.team/` are always fine, and projects without `.team/config.json` are never touched.
`"guard": "warn"` (default), `"block"` (the edit is refused), or `"off"` in `.team/config.json`.

## Bring your own team

`.team/config.json`:
```json
{
  "prefix": "APP",
  "base_branch": "main",
  "stages": {
    "build": { "agent": "my-dev", "skills": ["incremental-implementation"] }
  },
  "context": ["graphify query \"$TICKET_TITLE\""],
  "gates": { "build": { "run": "npm test", "mode": "block" } }
}
```

Executors: `{"agent": …}`, `{"skill": …}`, `{"command": …}`, `{"human": true}`.
Context commands and gates get ticket data as env vars only (`TICKET_ID`, `TICKET_TITLE`, `TICKET_PATH`, `TICKET_BRANCH`, `TICKET_TYPE`).

## What costs tokens

Only the thinking work: refining, building, reviewing and QA. Ticket bookkeeping, the board, branches and gates run in `scripts/team.py`, which uses only the Python standard library and costs zero tokens.

## Development

```bash
python3 sprintkit/scripts/test_team.py
```

# sprintkit

Run solo projects the way a real dev team does: tickets, stages, quality gates.
sprintkit owns the **process**. You choose **who** does each stage: the shipped agents, your own agents and skills, a shell command, or yourself.

```
backlog ─refine─▶ refined ─build─▶ in-review ─review─▶ in-qa ─qa─▶ done ─sanity─▶ ─deploy─▶ released
```

MVP status: `refine` and `build` work end to end. `review`, `qa`, `sanity`, `deploy` and `retro` are specified in [docs/stage-contract.md](../docs/stage-contract.md) and not built yet.

## Try it

```bash
claude --plugin-dir ./sprintkit
```
Then, in your project:
```
/sprintkit:init --prefix APP
/sprintkit:ticket story Users can switch to dark mode
/sprintkit:refine APP-1
/sprintkit:build APP-1
/sprintkit:board
```

## The board

`/sprintkit:board` starts a local board at `http://127.0.0.1:7700` (`/sprintkit:board text` for the terminal version).

- Cards move by themselves as stages run, with a highlight when they arrive.
- A failed gate shows on the card in red, with the reason.
- **New ticket** creates tickets. Click a card for its full history.
- The ▶ button on a card copies the next command, e.g. `/sprintkit:build APP-3`, to paste into Claude Code.
- Cards can't be dragged between stages. They only move when a stage passes its gate.

The server only listens on 127.0.0.1, rejects other `Host` headers, and only accepts JSON posts, so other websites can't create tickets.

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

Only the thinking work: refining and building. Ticket bookkeeping, the board, branches and gates run in `scripts/team.py`, which uses only the Python standard library and costs zero tokens.

## Development

```bash
python3 sprintkit/scripts/test_team.py
```

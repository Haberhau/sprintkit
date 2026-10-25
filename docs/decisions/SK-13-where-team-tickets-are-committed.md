# SK-13: Where `.team/` tickets are committed

**Decision:** `.team/` is local working state and git-ignored by default. Setup adds it to `.gitignore` unless the project already tracks it. Projects that want their backlog in git (this repo does) can keep tracking it, as long as tickets are committed on the base branch only while no ticket branch is open.

## The problem

Status lives in the ticket files, and the runner edits them while a ticket branch is checked out. Executors never commit `.team/`, so those edits sit uncommitted in the working tree and travel along when the runner switches branches. That works only while the ticket files are identical in every commit involved.

Reproduced in a scratch repo: track `.team/`, cut ticket branch B, then commit a ticket change on `main` (e.g. after another ticket was merged) and edit B's ticket again. `git checkout B` then fails with "Your local changes to the following files would be overwritten by checkout: .team/B.md". The runner's `start review`/`start qa` dies in the middle of the stage. With `.team/` in `.gitignore`, the same steps switch branches without complaint, because git never touches ignored files.

## Options

| Option | Branch switching | History / sharing | Cost |
|---|---|---|---|
| **A. Ignore `.team/`** (chosen default) | Always works | None: tickets live on one machine | One `.gitignore` line |
| B. Track `.team/`, commit only on the base branch | Breaks as soon as tickets are committed on main while a branch is open (above) | Full history | User discipline, or the runner would have to commit tickets itself at the right moments |
| C. Move status out of the ticket files (e.g. `.team/status.json`, ignored) | Works | Ticket text tracked, status not | Every reader of `status:` changes (runner, board, tests, contract §3) and tickets lose their self-contained Log |
| D. Tickets on a separate orphan branch or worktree | Works | Full history | Extra git machinery the solo user has to understand; the board would read from another checkout |

## Why A

- The target user is a solo developer on one machine. History of the code is in git already; the ticket Log section records the process history inside each file.
- It's the only option with no failure mode and no extra moving parts. C and D buy history at the cost of a bigger change, and nobody has asked for shared tickets yet.
- The first real test project already ended up with `.team/` untracked by accident, which is A without the safety of the ignore entry.

## Follow-ups

- If someone needs tickets shared across machines, revisit C (status in an ignored file, ticket text tracked).
- `queue.json` and `untracked.json` are runner state and belong in the ignored folder either way.

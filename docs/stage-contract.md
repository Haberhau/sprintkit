# Stage Contract — v0.1 (draft)

The plugin owns **what** happens and **when**. The user owns **who** does it.
This document is the contract between the two. Everything else (default agents,
commands, board) is an implementation of it.

---

## 1. Concepts

| Term | Meaning |
|---|---|
| **Ticket** | A markdown file in `.team/tickets/` (flat; status lives in frontmatter, not in folders) with simple `key: value` frontmatter. The single source of truth for one unit of work. |
| **Stage** | A step in the lifecycle (`refine`, `build`, …). Defines required inputs, required outputs and a gate. |
| **Executor** | Whatever does the stage's work: an agent, a skill, a shell command, or the human. Pluggable per stage. |
| **Gate** | A check that runs after the executor. Pass → ticket advances. Fail → ticket goes back or stays. |
| **Context provider** | A command that runs before an executor and feeds it extra context (e.g. graphify). |
| **Flow** | The ordered list of stages a ticket type goes through. |
| **Release** | A batch of `done` tickets that goes through `sanity` → `deploy` together. |

**Rule of thumb:** bookkeeping is shell scripts (zero tokens), thinking is executors (tokens).

---

## 2. Two levels: ticket stages vs release stages

```
TICKET LEVEL (one ticket at a time)
backlog ─refine─▶ refined ─build─▶ in-review ─review─▶ in-qa ─qa─▶ done
                     ▲                  │                 │
                     └──── fail ────────┴───── fail ──────┘ (back to build with notes)

RELEASE LEVEL (all `done` tickets since last release)
done ─sanity─▶ release-candidate ─deploy─▶ released
```

QA checks one ticket against its acceptance criteria. Sanity checks the integrated
main branch with all tickets merged. They are deliberately different stages.

`plan` (creates tickets, fills sprint) and `retro` (after release) sit outside the
ticket lifecycle — they read/write many tickets at once.

---

## 3. Ticket schema

```markdown
---
id: PROJ-12                # required, unique, prefix from config
type: story                # story | bug | spike | chore
title: Login form          # required
status: refined            # see §2; set only by scripts, never by executors
blocked: false
sprint: sprint-01          # optional
points: 3                  # optional, set in refine
branch: PROJ-12-login-form # set by build
---

## Description            ← plan
## Acceptance criteria    ← plan (draft), refine (final). Checkbox list.
- [ ] …
## Technical notes        ← refine
## Implementation notes   ← build
## Review notes           ← review
## QA notes               ← qa
## Log                    ← scripts only, append-only
- 2026-10-22T14:03 refined → in-progress (build: my-dev)
```

Every stage advances a ticket to the status the next stage of its flow (§5) waits in, or to `done` after the flow's last stage.

**Ownership rule:** each section is written by exactly one stage (exception: QA ticks AC boxes, and writes a bug's AC if it has none). Executors may
read everything, but write only their own section (plus code for `build`, tests for `qa`).
Executors never touch `status` or `## Log` — that's the runner's job.

---

## 4. Stage definitions

Every stage follows the same run sequence:

```
1. runner checks preconditions (status + required inputs)  → script
2. runner sets status to "in-<stage>", appends Log          → script
3. context providers run, output collected                  → script
4. executor runs with ticket + context                      → tokens
5. gate runs                                                → script
6. pass → advance status | fail → apply on_fail, append Log → script
```

### `plan` (sprint-level)
| | |
|---|---|
| **Input** | Idea / goal text from the user, existing backlog |
| **Output** | New ticket files in `backlog/` with Description + draft AC; `sprints/<n>/sprint.md` with goal + committed IDs |
| **Default executor** | `product-owner` agent |
| **Built-in gate** | every new ticket has `title`, `type`, ≥1 AC item |

### `refine`
| | |
|---|---|
| **Precondition** | `status: backlog` |
| **Output** | Final AC, `## Technical notes`, `points`; optional split into child tickets |
| **Default executor** | `tech-lead` agent |
| **Built-in gate** | AC has ≥1 item, Technical notes non-empty, `points` set |
| **Pass →** | `refined` |
| **Fail →** | stays `backlog`, gate output appended to Log |

### `build`
| | |
|---|---|
| **Precondition** | `status: refined` (or returned from review/qa) |
| **Runner prep** | creates/checks out `branch` |
| **Output** | Code on the branch, commits referencing the ticket ID, `## Implementation notes` |
| **Default executor** | `developer` agent |
| **Built-in gate** | branch has ≥1 commit containing the ID; working tree clean; user gate (e.g. `npm run lint`) |
| **Pass →** | the status the next stage of the flow waits in (`in-review` for a story, `in-qa` for a bug), or `done` if build is the last stage (spike, chore) |
| **Fail →** | stays `in-progress` |

### `review`
| | |
|---|---|
| **Precondition** | `status: in-review` |
| **Runner prep** | checks out `branch`; status `reviewing` while it runs |
| **Input** | Diff of `branch` vs main + ticket |
| **Output** | `## Review notes` ending in a verdict line: `VERDICT: approve` or `VERDICT: changes` |
| **Default executor** | `reviewer` agent |
| **Built-in gate** | verdict line present and `approve` |
| **Pass →** | `in-qa` |
| **Fail →** | `changes`: back to `refined` → next `build` run gets Review notes as input. No verdict: back to `in-review`, the review reruns |

### `qa`
| | |
|---|---|
| **Precondition** | `status: in-qa` |
| **Runner prep** | checks out `branch`; status `testing` while it runs |
| **Output** | Tests covering each AC item (committed on the branch), AC boxes ticked, `## QA notes`; out-of-scope bugs filed as new `bug` tickets. A `bug` has no refine, so QA writes its AC first if there are none |
| **Default executor** | `qa-engineer` agent |
| **Built-in gate** | ≥1 AC item and all ticked; QA notes non-empty; working tree clean; user gate (e.g. `npm test`) |
| **Pass →** | runner merges `branch` into main (`--no-ff`) → `done`. On a merge conflict the merge is aborted and the ticket stays `in-qa`, blocked |
| **Fail →** | back to `refined` with QA notes |

### `sanity` (release-level)
| | |
|---|---|
| **Precondition** | ≥1 ticket `done` since last release |
| **Output** | `releases/<version>.md` with included tickets + sanity result |
| **Default executor** | none — pure gate (shell) |
| **Gate** | user command, e.g. `npm run build && npm run smoke` |
| **Pass →** | all included tickets → `release-candidate` |
| **Fail →** | release blocked; runner offers to open a `bug` ticket with the output |

### `deploy` (release-level)
| | |
|---|---|
| **Output** | Changelog entry, git tag, deploy executed |
| **Default executor** | `release-manager` agent writes changelog; deploy itself is the user's command |
| **Gate** | deploy command exit 0 (+ optional health check command) |
| **Pass →** | tickets → `released` |

### `retro` (sprint-level, optional)
| | |
|---|---|
| **Input** | `## Log` sections of all sprint tickets (bounce-backs, gate failures, durations) |
| **Output** | `sprints/<n>/retro.md`: what went well, what bounced, one concrete process change |
| **Default executor** | `product-owner` agent |
| **Gate** | none |

---

## 5. Flows per ticket type

Not every ticket needs every stage. Solo devs abandon processes that are heavier than the work.

| Type | Flow |
|---|---|
| `story` | refine → build → review → qa → (release) |
| `bug` | build → qa → (release) |
| `chore` | build → (release) |
| `spike` | refine → build, where build output is a decision note, not code; ends at `done`, never released |

Configurable via `flows:` in config (§7).

---

## 6. Executor contract

What any executor (default or user-supplied) can rely on, and must do.

**Receives**
- `TICKET_PATH` — path to the ticket file
- Collected context-provider output
- For `build` after a bounce: the latest Review/QA notes are highlighted
- For `review`: the diff

**Must**
- Write only its own section(s) from §3
- Not change `status` or `## Log`
- Leave the repo in a state the gate can check (e.g. committed, not staged)

**May**
- Use any tools, skills, sub-agents it likes
- Create new tickets (via the `/ticket new` script, not by hand)

That's the whole interface. If an executor meets it, the gate decides — nothing
else cares how the work was done.

### Executor kinds in config
```yaml
build: { agent: my-dev }                    # Claude Code subagent by name
build: { skill: agent-skills:build }        # skill by name
build: { command: ./scripts/codegen.sh }    # shell, ticket via env vars
build: { human: true }                      # pauses, user does the work, then runs /advance
```

---

## 7. Config (`.team/config.json`)

Shown as YAML for readability; the MVP uses JSON so the runner needs only the Python stdlib.

```yaml
prefix: PROJ

stages:                         # omit a stage → shipped default
  build:  { agent: my-dev, skills: [incremental-implementation] }
  review: { skill: code-review }

context:                        # runs before every executor
  - graphify query "$TICKET_TITLE"
context_by_stage:               # extra, per stage
  review: [ "git diff main...$TICKET_BRANCH --stat" ]

gates:
  build:  { run: "npm run lint",                 mode: block }
  qa:     { run: "npm test",                     mode: block }
  sanity: { run: "npm run build && npm run smoke", mode: block }
  deploy: { run: "./deploy.sh",                  mode: block }

gate_default_mode: warn         # warn = log failure, advance anyway

flows:                          # override §5
  bug: [build, qa]
```

**Setup failures aren't test failures.** Exit 127/126, or output that can only come from the environment (xcodebuild can't find the destination, the simulator or test runner fails to start), is reported as a setup problem. A flaky simulator start is retried once. In `block` mode a setup problem blocks the ticket for a human instead of bouncing it, and doesn't count as a failed attempt.

**Ticket data is passed to commands as env vars only** (`TICKET_ID`, `TICKET_TITLE`,
`TICKET_PATH`, `TICKET_BRANCH`, `TICKET_TYPE`), never string-interpolated into the
command. A title like `"; rm -rf ~` must stay a harmless string.

**Context output cap:** each provider's output is truncated at a configurable size
(default 4k chars) so a noisy provider can't blow up token use.

---

## 8. What costs tokens and what doesn't

| Zero tokens (scripts) | Tokens (executors) |
|---|---|
| status transitions, Log | plan, refine |
| `/board` | build |
| precondition + built-in gate checks | review |
| user gate commands | qa (writing tests) |
| branch create / merge / tag | release notes, retro |
| context providers | |

---

## 9. Decisions and open questions

- **Decided: merge on `qa` pass.** Main only ever holds QA'd work.
- **Decided: user gates default to `warn`.** Built-in structural gates (§4) always block — the next stage can't work without their outputs.

1. **Parallel tickets** — allow >1 ticket `in-progress`? Solo default: one at a time, enforced by the edit-blocking hook.
2. **Token budget per stage** — add `max_turns` per executor? Skip until someone hits it.
3. **External boards** (Jira/Linear/GitHub Issues) — one-way mirror of status from files, or two-way? One-way is far simpler; files stay the source of truth.

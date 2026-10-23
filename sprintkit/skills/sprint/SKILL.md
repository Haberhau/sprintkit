---
name: sprint
description: Autopilot - work through the sprint queue ticket by ticket, running each ticket's next stage until the queue is empty. Tickets that keep failing a gate get blocked and skipped.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/team.py *)
---

You are running the sprint on autopilot. Don't ask the user anything between tickets. The queue and the gates decide what happens.

Loop:

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" next`.
   - It may print `DEQUEUED: …` (ticket has gone as far as the autopilot can take it) or `BLOCKED: …` (gate failed too often, or the stage needs a human) lines first. Mention each in one line.
   - `NEXT: none`: go to step 3.
   - `NEXT: <stage> <ID>`: go to step 2.

2. Run that stage on that ticket by invoking the `sprintkit:<stage>` skill with the ticket ID, and follow it fully: start, executor, finish. Autopilot overrides one thing in it: on FAIL, don't offer to rerun or wait for the user. Just say what failed in one line. The next loop round retries, and the runner blocks the ticket once it has failed too often. Then go back to step 1.

3. Done. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" board` and finish with a short summary: what passed, what's blocked and why, and what's waiting on stages the autopilot can't run yet (review onward).

Stop early, and tell the user why, only if something is broken outside the stage contract: a git conflict, the runner crashing, an executor that can't run at all. A failed gate is not a reason to stop.

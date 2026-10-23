---
name: init
description: Set up sprintkit in the current project - creates .team/ with tickets folder and config.json.
argument-hint: "[--prefix PROJ]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/team.py *)
---

Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" init $ARGUMENTS` from the project root and show the output.

Then tell the user, briefly:
- Tickets live in `.team/tickets/` and should be committed like code.
- `.team/config.json` maps each stage to an executor. Defaults are `sprintkit:tech-lead` (refine) and `sprintkit:developer` (build). Swap in their own with `{"agent": "name"}`, `{"skill": "name"}`, `{"command": "..."}` or `{"human": true}`.
- `"context": ["graphify query \"$TICKET_TITLE\""]` runs before every stage. Ticket data comes in as env vars (TICKET_ID, TICKET_TITLE, TICKET_PATH, TICKET_BRANCH, TICKET_TYPE).
- `"gates": {"build": {"run": "npm test", "mode": "block"}}` adds a check. Mode defaults to warn.
- Next: `/sprintkit:ticket story "..."`.

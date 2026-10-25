---
name: qa
description: Run the qa stage on one sprintkit ticket - precondition check, executor, gates, and merge into the base branch on pass.
argument-hint: "<ticket ID>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/team.py *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" *)
---

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" start qa $ARGUMENTS`. If it errors, show the error and stop.

2. If the output has `READY: yes`, an earlier attempt's output already passes the gate: skip to step 3. Otherwise read `EXECUTOR` from the output and hand the work over. The executor must produce: tests committed with the ticket ID, every Acceptance criteria box ticked once proven, and QA notes. It must not edit product code, `status`, `branch` or `## Log`.
   - `{"agent": "X"}`: call the Agent tool with `subagent_type: X`. The prompt is the full output of step 1 plus "Do the qa stage for this ticket." If the executor also lists `"skills"`, tell the agent to use them.
     If the Agent tool says that agent type doesn't exist and X starts with `sprintkit:` (the plugin was installed or updated after this session started, so its agents aren't registered yet), call it with `subagent_type: general-purpose` instead, and put the full text of `${CLAUDE_PLUGIN_ROOT}/agents/<name after "sprintkit:">.md` (without its frontmatter) at the top of the prompt. Mention once that a new session would load the agents directly.
   - `{"skill": "X"}`: invoke skill X with the ticket path as its argument, and do the work it describes yourself, writing only the outputs above.
   - `{"command": "C"}`: run C with TICKET_ID, TICKET_PATH, TICKET_TITLE, TICKET_TYPE and TICKET_BRANCH exported from step 1's output.
   - `{"human": true}`: if `RESUMED: no`, tell the user what the stage must produce and to run `/sprintkit:qa <ID>` again when they're done, then stop. If `RESUMED: yes`, go straight to step 3.
   - `{}` or missing: no executor is configured. Tell the user and stop.

3. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" finish qa $ARGUMENTS`.
   - PASS: the branch is merged into the base branch and the ticket is done. Say so in one line.
   - FAIL: list the problems. The ticket is back in `refined`; the next build gets the QA notes. Offer `/sprintkit:build <ID>`.
   - BLOCKED: either QA passed but the merge conflicts (show the conflicting files and the runner's instructions; nothing was merged), or the gate command couldn't run (missing tool, wrong simulator): show the reason and say the gate or environment needs fixing.
   - WARN lines: mention them. The ticket advanced anyway because that gate's mode is warn.

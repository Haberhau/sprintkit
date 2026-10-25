---
name: refine
description: Run the refine stage on one sprintkit ticket - precondition check, context, executor, gate.
argument-hint: "<ticket ID>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/team.py *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" *)
---

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" start refine $ARGUMENTS`. If it errors, show the error and stop.

2. Read `EXECUTOR` from the output and hand the work over. The executor must produce: Acceptance criteria, Technical notes and the `points` field. It must not edit `status`, `branch` or `## Log`.
   - `{"agent": "X"}`: call the Agent tool with `subagent_type: X`. The prompt is the full output of step 1 plus "Do the refine stage for this ticket." If the executor also lists `"skills"`, tell the agent to use them.
     If the Agent tool says that agent type doesn't exist and X starts with `sprintkit:` (the plugin was installed or updated after this session started, so its agents aren't registered yet), call it with `subagent_type: general-purpose` instead, and put the full text of `${CLAUDE_PLUGIN_ROOT}/agents/<name after "sprintkit:">.md` (without its frontmatter) at the top of the prompt. Mention once that a new session would load the agents directly.
   - `{"skill": "X"}`: invoke skill X with the ticket path as its argument, and do the work it describes yourself, writing only the outputs above.
   - `{"command": "C"}`: run C with TICKET_ID, TICKET_PATH, TICKET_TITLE, TICKET_TYPE and TICKET_BRANCH exported from step 1's output.
   - `{"human": true}`: if `RESUMED: no`, tell the user what the stage must produce and to run `/sprintkit:refine <ID>` again when they're done, then stop. If `RESUMED: yes`, go straight to step 3.
   - `{}` or missing: no executor is configured. Tell the user and stop.

3. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" finish refine $ARGUMENTS`.
   - PASS: say so in one line and name the `NEXT:` command from the output.
   - FAIL: list the problems. The ticket has already been moved to its fail status. Offer to run the stage again.
   - BLOCKED: the gate command couldn't run (missing tool, wrong simulator), so it's not the executor's fault. Show the reason and say the gate in `.team/config.json` or the environment needs fixing.
   - WARN lines: mention them. The ticket advanced anyway because that gate's mode is warn.

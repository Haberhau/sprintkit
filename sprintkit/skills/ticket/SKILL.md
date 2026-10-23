---
name: ticket
description: Create a sprintkit ticket (story, bug, chore or spike) from a short description.
argument-hint: "<story|bug|chore|spike> <what it is about>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/team.py *)
---

Arguments: $ARGUMENTS

1. Pick the type (first word if it is story/bug/chore/spike, otherwise infer it) and a short title (under 60 chars).
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" new <type> "<title>"`. It prints the new ticket's path.
3. In that file, fill only **Description** (what and why, from the user's words; for a bug: steps to reproduce, expected, actual). Add draft **Acceptance criteria** as `- [ ] …` items only if the user stated them.
4. Don't touch the frontmatter or `## Log`. Reply with the ticket ID and its next stage: `/sprintkit:refine <ID>` for story/spike, `/sprintkit:build <ID>` for bug/chore.

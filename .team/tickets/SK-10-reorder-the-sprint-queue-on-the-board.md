---
id: SK-10
type: story
title: Reorder the sprint queue on the board
status: done
blocked: false
---

## Description
Cards can be added to and removed from the queue, not reordered. Drag chips within the queue lane; keyboard alternative (move up/down).

## Acceptance criteria

## Technical notes

## Implementation notes
- **Changes**: `queue_move()` in team.py, exposed as `POST /api/queue {"action": "move", "to": <0-based>}` and `team.py queue move <ID> <position>`. On the board, queue chips are draggable within the lane (drop before a chip, or on empty lane space for the end; an accent bar marks the drop spot), and each chip has ‹ › buttons with aria-labels as the keyboard alternative. Cards dragged into the lane are still added.
- **Criteria**: checked in the browser on a demo project: ‹ › reorder, drag to the front, forward, and to the end, and dragging a card in still adds it. Native drag was driven with dispatched DragEvents, since synthetic mouse drags don't start HTML5 drag-and-drop.
- **Tests**: `check_server()`: move via API, bad `to` and an unqueued id are 400, CLI move.

## Review notes

## QA notes

## Log
- 2026-10-23T20:05 created → backlog
- 2026-10-25T11:29 backlog → done (built by hand while bootstrapping)

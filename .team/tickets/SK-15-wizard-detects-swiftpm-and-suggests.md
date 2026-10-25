---
id: SK-15
type: story
title: Wizard detects SwiftPM and suggests swift test as a gate
status: backlog
blocked: false
---

## Description
`detect_checks()` in wizard.py knows npm, pytest, cargo, go, make and xcodebuild, but not a Swift package. In the first real test project (a Swift app) the project became a SwiftPM package during TR-1 and ended up with `"gates": {}`, so nothing enforced `swift test`. Suggest `swift test` when `Package.swift` exists (before xcodebuild, which needs an .xcodeproj). Since the wizard only runs at setup, also consider showing the suggestion in Settings for projects whose stack appeared later.

## Acceptance criteria

## Technical notes

## Implementation notes

## Review notes

## QA notes

## Log
- 2026-10-24T22:35 created → backlog

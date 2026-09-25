---
plan_format: 1
mode: full
branch: feature/x
created: 2026-09-25
affects_workspaces: [app]
---

## Tasks

- [ ] Task 1: Change the process
  - kind: config
  - files: app/FM/_PROCESS/Case/process.xml
- [ ] Task 2: A new helper
  - kind: code
  - reason: no EventBase verb reads the callback
  - files: app/js/new-helper.js

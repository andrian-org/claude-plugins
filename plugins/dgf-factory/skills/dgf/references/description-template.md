# {{ESTATE_NAME}} — DGF estate

> Written by `/dgf` on {{DATE}}, which owns this file; re-run `/dgf` to refresh it. Every other
> dgf-* skill reads it and never writes it.

## Purpose

{{PURPOSE}}

## DGF version

- **Declared:** `{{DGF_VERSION}}` — `dgf.version` in `.dgf-factory/config.yaml`.
- **Shipped knowledge read at:** `{{KNOWLEDGE_STAMP}}` — the `KNOWLEDGE:` line of the inventory.
{{VERSION_NOTE}}

## Workspaces root

- **Root:** `{{ROOT}}`
- **Git:** {{GIT_LINE}}

| Workspace | Role | Processes | Workflows | Components | Forms | Settings | Views | Options | Form scripts | Global scripts | Global styles |
|---|---|---|---|---|---|---|---|---|---|---|---|
{{WORKSPACE_ROWS}}

**Not workspaces:**

{{NOT_WORKSPACE_LINES}}

{{INVENTORY_WARNINGS}}

## Stack

Sign-in has no default: it is what this estate chose from `basic`, `dgpass` and `azure`, or
`none`. The test stack is a default, not an invariant, and this estate's answer wins where it
differs.

| Topic | Default | This estate |
|---|---|---|
| Sign-in methods | none — chosen at setup | {{AUTH}} |
| Test stack | xUnit + FluentAssertions + Moq/NSubstitute (backend); Jest and Playwright (frontend) | {{TESTS}} |

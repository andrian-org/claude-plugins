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

The plugin ships two stack defaults. They are defaults, not invariants, and this estate's
answer wins where it differs.

| Topic | Default | This estate |
|---|---|---|
| Auth | JWT Bearer plus OIDC via Azure AD and DGPass | {{AUTH}} |
| Test stack | xUnit + FluentAssertions + Moq/NSubstitute (backend); Jest and Playwright (frontend) | {{TESTS}} |

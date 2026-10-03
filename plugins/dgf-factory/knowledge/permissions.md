---
dgf_version: "1.1.11"
read_date: 2026-09-27
---

# Permissions — where a workspaces root names a role, and what declares one

Structural facts: stamp only. Where the configuration in a workspaces root names roles and claims,
how the runtime reads each name, and why nothing in the root can be checked against a list of roles.
The files read are in the maintainer provenance ledger for this file.

## 1. Roles are database rows

**Nothing in a workspaces root declares a role.** Roles are ASP.NET Identity rows (`AspNetRoles`),
created in code at first start by `ApplicationDbContextSeed`: the five built-in names —
`Administrators`, `Members`, `Anonymous`, `Registered Users` and `PortalUser` (`UserRoleConstants`) —
plus the role of each seeded account, and after that whatever the estate's administrators add. The
root only **names** roles, as strings, in the places §2 lists. A name that matches no role row is not
an error anywhere: the check it feeds simply never passes.

## 2. Where the root names a role

<!-- machine-read: role-sources -->
| Source | File | Element | Attribute | Separator | Meaning |
|---|---|---|---|---|---|
| `sitemap-roles` | `_application.sitemap` | `mapNode` | `roles` | `,` | the roles allowed the node; empty allows anyone; exactly `Members` allows any signed-in user |
| `sitemap-deny` | `_application.sitemap` | `mapNode` | `deny` | `,` | the roles denied the node |
| `sitemap-claims` | `FM/_COMPONENTS/sitemap.json` | `metaData.requireClaims` | `name` | — | a claim a route requires — a claim, not a role |
| `profile-group` | `FM/_PROFILE/*/*/_tree.xml` | (folder) | — | — | the role group whose tree a user of that role sees |
| `task-role` | `FM/_PROCESS/*/process.xml` | `Task` | `role` | — | the role a process task is assigned to |
| `taskgroup-role` | `FM/_PROCESS/*/*.xml` | `TaskGroup` | `role` | — | the role of a MultiTask group |

How to read a row:

- **`File`** is a path under a workspace, `*` standing for one folder name. `_application.sitemap` sits
  at the **workspace root, beside `FM/`** (`ApplicationMap.GetConfigPath`), and only the selected
  workspace's is read. `sitemap.json` is read from the selected workspace's `FM/_COMPONENTS/`, and from
  `webasm`'s when the application has none (`ComponentFileLoadService.LoadSiteMapAsJsonAsync`; the file
  name is `SiteMapOptions.FileName`, `sitemap.json` by default). A MultiTask file is a `<State>.xml`
  whose root is `MultiTaskSettings` ([`process-model.md`](process-model.md) §2.7).
- **`Element`** is an XML element, at any depth; `metaData.requireClaims` is a key path in the JSON,
  at any depth, holding a list of objects; `(folder)` means the name of the folder that holds the file.
- **`Separator`**, when not `—`, splits the value into several names.

### 2.1 How the sitemap reads `roles` and `deny`

`SiteMapManager.CheckPermissions(roles, deny)`:

- **Splits on `,` with no trimming.** `roles="A, B"` tests the roles `A` and ` B` — with its leading
  space — and no role is named ` B`. A name is therefore listed exactly as the runtime tests it,
  spaces included.
- **An empty `roles` allows anyone**, signed in or not. **A `roles` of exactly `Members`** — the whole
  value, case-sensitive — allows any signed-in user. `Members` inside a list is tested as an ordinary
  role name.
- **`deny` wins**: a user holding any denied role is refused, whatever `roles` allows.
- A route whose node has a non-empty `roles` requires authorisation; a user who fails the check loses
  the route, not only its menu link.

### 2.2 How a profile group is chosen

`TreeManager` reads `FM/_PROFILE/<Profile>/<Group>/_tree.xml`, where the group is the signed-in user's
current role name — the entity's role name for a corporate user (`ProfileHelper`). An empty group, or
a group with no `_tree.xml`, falls back to `Members`. A profile name containing `:` (`BASE:<Profile>`)
reads `webasm`'s `_PROFILE`. So a group folder names a role, and `Members` is the default tree.

### 2.3 Required claims

`sitemap.json` routes may carry `metaData.requireClaims`: a list of `{name, hasNoValue, value}`. A
signed-in user keeps the route only when each named claim is present — with the given value, compared
ignoring case, when one is set — or, with `hasNoValue`, is absent or blank. A claim is a property of
the user's identity, not a role; it is listed beside the roles because it gates the same routes.

## 3. What a root's role names tell you

- **The names are data, not declarations.** A workflow that compares a value with the literal
  `Applicant` (44 sample workflows), or a file that reads `SM_CurrentRole` (303 sample files), uses a
  role name the root cannot define.
- **Spelling drifts unseen.** In DGF's samples the sitemaps name `Case Officer` while a process task
  names `CaseOfficer`; nothing reports it, because nothing in the root lists the roles that exist.
- In the samples: 24 distinct `roles`/`deny` tokens across the two `_application.sitemap` files, two of
  them empty; profile groups `Members` (31), `Administrators` (17), `Support` (6) and others; and one
  named process `Task/@role`.

## See Also

- [`README.md`](README.md) — the stamping convention and the machine-read table contract (§7)
- [`process-model.md`](process-model.md) — the process model, `Task` and MultiTask settings
- [`data-model.md`](data-model.md) — entities, and what else is a database row

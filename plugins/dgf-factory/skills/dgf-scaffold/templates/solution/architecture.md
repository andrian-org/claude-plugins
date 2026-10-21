# Architecture

{{app.title}} is a DotGov Framework application: configuration in a workspaces root, run by a host built on the
DGF.API package, over a SQL Server database.

## Instances

An instance is a `WorkspaceName` with its own row in `aspnet_Applications`; the framework partitions its own rows
by that row's id.

{{#if shared}}
This application uses **one shared workspace**, `{{first_workspace}}`, mounted under each instance's name. Each instance
has its own `_application-<instance>.sitemap`, bind-mounted over `_application.sitemap`, so its map can differ
while its configuration is one.
{{else}}
This application gives **each instance its own workspace directory**, named after it.
{{/if}}

| Instance | Workspace name | Directory | Application id |
|---|---|---|---|
{{#each instances}}
| {{title}} | {{name}} | workspaces/{{workspace}} | {{application_id}} |
{{/each}}

The application ids are derived from the application and instance names, so a re-generation reproduces them.

## Hosts

A host is one API process for one instance. A front office and a back office are one host deployed twice with
different settings; DGF has no back-office concept.

| Deployment | API | Instance | Sign-in |
|---|---|---|---|
{{#each deployments}}
| {{name}} | {{api}} | {{instance}} | {{#each auth}}{{this}} {{/each}} |
{{/each}}

Each host reads `appsettings.json`, then `appsettings.<Deployment>.json` (selected by the environment name), then
the environment: a double underscore in a variable name overrides the JSON key it names.

## Workspaces

Every workspace carries the minimum a new application needs: a route table (`sitemap.json`) whose landing route is
first and is not `/`, a `/login` route with a local login page, an `_application.sitemap`, the pages the routes point
at, and a profile tree for each router. Nothing in it uses a `BASE:` reference, so it stands alone whatever base is
supplied.

## Database

`{{database.project}}` is an SDK-style `Microsoft.Build.Sql` project holding the application's tables and two
idempotent post-deployment scripts: one `aspnet_Applications` row per instance, and the roles. It is published into
the database the framework's baseline created, after the baseline, and never drops what it does not own.

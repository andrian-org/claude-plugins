# dotGov Claude Code Plugins

Internal plugin marketplace for dotGov Solutions. Hosted in Azure DevOps — access is controlled by
the `dotgov` project's repo permissions, so only teammates who can clone this repo can install
from it.

Clone URL: `https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins`

## For teammates: one-time setup

Run the first command in a **normal interactive terminal**, not inside a Claude Code session —
Git Credential Manager may need to prompt for Azure DevOps sign-in:

```bash
claude plugin marketplace add https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins
claude plugin install doc-coverage-audit@dotgov
```

Restart Claude Code, then confirm:

```bash
claude plugin list
```

If the `add` fails with `unable to get password from user`, you are running non-interactively.
Do `git clone <url>` once by hand so GCM caches the credential, then retry.

## Automatic provisioning (recommended)

Any project repo can declare this marketplace so teammates get the plugin with no setup at all.
Let the CLI write the entry rather than hand-authoring it:

```bash
cd /path/to/your/project
claude plugin marketplace add https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins --scope project
```

That produces `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "dotgov": {
      "source": {
        "source": "git",
        "url": "https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins"
      }
    }
  },
  "enabledPlugins": ["doc-coverage-audit@dotgov"]
}
```

Add `enabledPlugins` yourself. Commit the file — a fresh clone is then ready to go.

## Plugins

| Plugin | What it does |
|---|---|
| `doc-coverage-audit` | Maps a deliverables checklist to the documents that actually exist, with verified links and gap analysis. Built for close-out, hand-over, due diligence and audit evidence. |
| `zamconnect` | ZamConnect tenant lifecycle: scaffolding, upstream and shared e-Services integration, drift audit, test generation, and the contractual delivery package (OpenAPI, Word API Specification, Postman). |

## Contributing a plugin

```
plugins/<your-plugin>/
  .claude-plugin/plugin.json      # name, description, version, author
  skills/<skill-name>/SKILL.md    # frontmatter: name + description
  commands/  agents/  hooks/      # optional
```

The nesting matters: `skills/<skill-name>/SKILL.md`, not `skills/SKILL.md`. A flattened copy
(easy to cause with `cp -R`) will not load.

1. Scaffold with `claude plugin init <name>` for a starting point.
2. Add an entry to `.claude-plugin/marketplace.json` (`source: "./plugins/<your-plugin>"`).
3. Validate **both** manifests before opening a PR:

   ```bash
   claude plugin validate .
   claude plugin validate plugins/<your-plugin>
   ```

4. Test locally as a directory marketplace before pushing:

   ```bash
   claude plugin marketplace add /path/to/this/repo
   claude plugin install <your-plugin>@dotgov
   claude plugin details <your-plugin>@dotgov      # check token cost
   ```

5. If you also keep a copy in `~/.claude/skills/`, delete it — two registrations of the same
   skill name collide.

### Writing the `description`

The `description` in `SKILL.md` frontmatter is the **only** thing Claude sees when deciding
whether to load your skill. Write it as trigger phrases people actually type, not as a summary of
the implementation. Review descriptions in PRs more carefully than implementations — a good skill
with a vague description never fires.

### Keep an eye on token cost

`claude plugin details <name>@dotgov` reports always-on cost, which every session pays. Keep
`SKILL.md` lean and push detail into `references/` files that load only when needed.

### Versioning and releases

Bump `version` in `plugin.json`, then:

```bash
claude plugin tag plugins/<your-plugin>
```

This creates `<name>--v<version>` and validates that `plugin.json` agrees with the marketplace
entry. Teammates update with `claude plugin update <name>` (restart required).

## Secrets

Never commit tokens, `.pfx`/`.jks`/`.pem` files, tenant credentials or client document content.
Skills must acquire credentials at runtime and cache them outside the repo — see `.gitignore`.

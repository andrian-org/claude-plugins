# dotGov Claude Code Plugins

Internal plugin marketplace for dotGov Solutions. Private repo — access is controlled by GitHub
permissions, so only teammates who can clone this repo can install from it.

## For teammates: one-time setup

```bash
claude plugin marketplace add dotgovsolutions/dotgov-claude-plugins
claude plugin install doc-coverage-audit@dotgov
```

Then restart Claude Code. Verify with `/plugin` or:

```bash
claude plugin list
```

Private-repo access uses your existing git/`gh` credentials. If the `add` fails, confirm
`gh auth status` works and that you can `git clone` this repo.

## Automatic provisioning (recommended)

Any repo can declare this marketplace so teammates get it without running anything. Commit to
that repo's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "dotgov": {
      "source": {
        "source": "github",
        "repo": "dotgovsolutions/dotgov-claude-plugins"
      }
    }
  },
  "enabledPlugins": ["doc-coverage-audit@dotgov"]
}
```

`extraKnownMarketplaces` makes the source available; `enabledPlugins` turns the plugin on.
Both are read from checked-in project settings, so a fresh clone is ready to go.

## Plugins

| Plugin | What it does |
|---|---|
| `doc-coverage-audit` | Maps a deliverables checklist to the documents that actually exist, with verified links and gap analysis. Built for close-out, hand-over, due diligence and audit evidence. |

## Contributing a plugin

```
plugins/<your-plugin>/
  .claude-plugin/plugin.json      # name, description, version, author
  skills/<skill-name>/SKILL.md    # frontmatter: name + description
  commands/  agents/  hooks/      # optional
```

1. Scaffold with `claude plugin init <name>` if you want a starting point.
2. Add an entry to `.claude-plugin/marketplace.json` (`source: "./plugins/<your-plugin>"`).
3. Validate **both** manifests before opening a PR:

   ```bash
   claude plugin validate .
   claude plugin validate plugins/<your-plugin>
   ```

4. Test it locally as a directory marketplace before pushing:

   ```bash
   claude plugin marketplace add /path/to/this/repo
   claude plugin install <your-plugin>@dotgov
   ```

### Writing the `description`

The `description` in `SKILL.md` frontmatter is the **only** thing Claude sees when deciding
whether to load your skill. Write it as trigger phrases people actually type, not as a summary of
the implementation. Vague descriptions mean the skill never fires.

### Versioning and releases

Bump `version` in `plugin.json`, then tag:

```bash
claude plugin tag plugins/<your-plugin>
```

This creates `<name>--v<version>` and checks that `plugin.json` agrees with the marketplace entry.
Teammates pick up changes with `claude plugin update <name>` (restart required).

## Secrets

Never commit tokens, `.pfx`/`.jks`/`.pem` files, tenant-specific credentials or client document
content. Skills should acquire credentials at runtime and cache them outside the repo.

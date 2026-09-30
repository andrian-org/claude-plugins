# dotGov Claude Code Plugins

Internal plugin marketplace for dotGov Solutions. Hosted in a private GitHub repository — access is
controlled by the repo's permissions, so only teammates who can read this repo can install from it.

Repository: `https://github.com/andrian-org/claude-plugins`

The marketplace is named `dotgov` (the `name` in `.claude-plugin/marketplace.json`), independent of
the repo name — install ids are `<plugin>@dotgov`.

## For teammates: one-time setup

Claude Code runs `git` with interactive prompts turned off, so it needs a credential that is
already stored for GitHub. Sign in once with the GitHub CLI:

```bash
gh auth login
gh auth setup-git
```

An SSH key loaded in `ssh-agent` works too. Then add the marketplace and install:

```bash
claude plugin marketplace add andrian-org/claude-plugins
claude plugin install doc-coverage-audit@dotgov
```

Restart Claude Code, then confirm:

```bash
claude plugin list
```

If the `add` fails with an authentication error (for example `could not read Username`), no
credential is stored yet: run the two `gh` commands above and retry. On a machine with no GitHub
SSH key, set `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` to skip the SSH attempt. The same stored
credential is what lets Claude Code refresh the marketplace in the background — a `GITHUB_TOKEN`
environment variable alone does not.

## Automatic provisioning (recommended)

Any project repo can declare this marketplace so teammates get the plugin with no setup at all.
Let the CLI write the entry rather than hand-authoring it:

```bash
cd /path/to/your/project
claude plugin marketplace add andrian-org/claude-plugins --scope project
```

That produces `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "dotgov": {
      "source": {
        "source": "github",
        "repo": "andrian-org/claude-plugins"
      }
    }
  },
  "enabledPlugins": {
    "doc-coverage-audit@dotgov": true
  }
}
```

Add `enabledPlugins` yourself. Commit the file — a fresh clone is then ready to go, once the
teammate has read access to the repo and the GitHub credential from the setup above.

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

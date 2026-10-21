# Configuration

Every value that is a secret, a host, a feed, a registry or an image is a `${VAR}` in the generated files, and is
declared once here and in [docker/.env.example](../docker/.env.example). A secret is marked, and has no example
value.

The hosts read them through `appsettings.json`, where each key holds its `${VAR}` as a placeholder, and through the
environment: the compose file sets the same key, spelled with a double underscore, from the variable.

{{#each vars}}
- **{{ref|raw}}**{{#if secret}} (secret){{/if}} — {{description|raw}} (group: {{group|raw}}){{#if example}} Example: `{{example|raw}}`.{{/if}}
{{/each}}

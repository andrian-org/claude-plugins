# tables

<!-- machine-read: instance-models -->
| Model | Mounts | Sitemap | Applications row | Fact |
|---|---|---|---|---|
| `shared-workspace` | shared | override | per-instance | One directory mounted under each instance's name; a per-instance `_application-<instance>.sitemap` is bind-mounted over `_application.sitemap` |
| `own-workspace` | own | own | per-instance | One workspace directory per instance, each with its own `_application.sitemap`; the same `WorkspaceName` rule and the same row per instance |

<!-- machine-read: auth-schemes -->
| Provider | Section | Keys | Fact |
|---|---|---|---|
| `basic` | Authentication:Basic | Enabled | Local username and password. The `dgf` sample and the local stack use it alone. An account is seeded from `AdminSeedOptions`, never from this section |
| `dgpass` | Authentication:DGPassOIDC | Authority ClientId ClientSecret CallbackPath PostLogoutRedirectUri BackChannelLogoutUri Scopes ClockSkew ClientCredentialStyle MetadataUrl | OpenID Connect, code flow with PKCE. `Authority`, `ClientId` and `ClientSecret` have no default and no validation; the others default to `/signin-oidc`, `/signout-callback-oidc`, none, `openid profile`, 60 seconds, `PostBody` and a metadata address derived from the authority |
| `azure` | Authentication:AzureOIDC | TenantId Authority ClientId ClientSecret CallbackPath PostLogoutRedirectUri Scopes | OpenID Connect against `<Authority>/<TenantId>/v2.0`. Sets no metadata address, no `offline` scope, no clock skew and no token refresh |

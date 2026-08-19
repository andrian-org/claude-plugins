# SharePoint / Microsoft Graph access — the auth ladder

Getting read access is usually the hardest part of the audit. Work down this ladder and stop at
the first rung that works. Do not skip to rung 4 (tenant changes) because rung 3 is unfamiliar —
rung 3 is very often the answer.

---

## Rung 1 — Is Azure CLI already logged in?

```bash
az account show -o json
```

Gives you tenant ID, tenant domain and the signed-in user. Then:

```bash
az account get-access-token --resource https://graph.microsoft.com -o tsv --query accessToken > tok.txt
curl -s -H "Authorization: Bearer $(cat tok.txt)" \
  "https://graph.microsoft.com/v1.0/me?\$select=displayName,userPrincipalName"
```

`/me` succeeding proves nothing about SharePoint. **Always test the actual capability you need:**

```bash
curl -s -H "Authorization: Bearer $(cat tok.txt)" \
  "https://graph.microsoft.com/v1.0/sites/<tenant>.sharepoint.com:/"        # usually works
curl -s -H "Authorization: Bearer $(cat tok.txt)" \
  "https://graph.microsoft.com/v1.0/sites/<siteId>/drive"                   # the real test
```

### Always decode the token before theorising

```bash
python3 -c "
import base64,json
t=open('tok.txt').read().strip().split('.')[1]; t+='='*(-len(t)%4)
d=json.loads(base64.urlsafe_b64decode(t))
print('appid:',d.get('appid'),d.get('app_displayname'))
print('scp:',d.get('scp'))
"
```

This answers the question in one step instead of guessing from error messages. Azure CLI
typically carries `Directory.AccessAsUser.All`, `User.ReadWrite.All`, `Group.ReadWrite.All`,
`Application.ReadWrite.All`, `AppRoleAssignment.ReadWrite.All` — and **no `Sites.*` or
`Files.*`**. So SharePoint is out of reach even though the login looks healthy.

Note the side benefit: a token holding `Application.ReadWrite.All` +
`AppRoleAssignment.ReadWrite.All` implies the user is a **privileged admin**, which tells you
rung 4 is technically available to them.

---

## Known dead ends — recognise these instantly

| Attempt | Error | Meaning |
|---|---|---|
| Graph `/sites/{id}/drive` with an az token | `{"error":{"code":"accessDenied"}}` | No `Sites.Read.All`. `/lists` may return an empty array instead of erroring — an empty result is **not** proof of an empty library. |
| `az account get-access-token --scope https://graph.microsoft.com/Sites.Read.All` | `AADSTS65002: Consent between first party application … must be configured via preauthorization` | Azure CLI cannot request arbitrary Graph scopes. Unfixable. |
| SharePoint REST `_api/web` with an az SPO-resource token | HTTP 401, header `x-ms-diagnostics: 3001003;reason="App is not allowed to call SPO with user_impersonation scope"` | The token issues fine and is still useless. **Read `www-authenticate` and `x-ms-diagnostics` with `curl -i`** — the JSON body says only `{"error":"invalid_request"}`. |

Lesson: `az account get-access-token --resource <anything>` frequently **succeeds** and returns a
token the resource then rejects. A returned token is not proof of access.

---

## Rung 3 — Find a pre-consented first-party app (usually the winner)

Before proposing any tenant change, ask what the tenant already trusts. The az token's
`Directory.AccessAsUser.All` is enough to read this.

```bash
SP_ID=$(curl -s -H "Authorization: Bearer $T" \
  "https://graph.microsoft.com/v1.0/servicePrincipals?\$filter=appId%20eq%20'14d82eec-204b-4c2f-b7e8-296a70dab67e'&\$select=id" \
  | jq -r '.value[0].id')

curl -s -H "Authorization: Bearer $T" \
  "https://graph.microsoft.com/v1.0/oauth2PermissionGrants?\$filter=clientId%20eq%20'$SP_ID'" \
  | jq -c '.value[] | {consentType, scope}'
```

`"consentType":"AllPrincipals"` means **org-wide consent already exists** — any user can get
those scopes with no admin involvement and no tenant change.

Useful public-client app IDs (all support device code):

| App | Client ID |
|---|---|
| Microsoft Graph Command Line Tools | `14d82eec-204b-4c2f-b7e8-296a70dab67e` |
| Azure CLI | `04b07795-8ddb-461a-bbee-02f9e1bf7b46` |
| Microsoft Office | `d3590ed6-52b3-4102-aeff-aad2292ab01c` |

In the source session, *Graph Command Line Tools* already had `AllPrincipals` consent for
`Files.Read.All Sites.Read.All` — so the whole problem collapsed to one device-code sign-in with
zero configuration change. **Always check this before suggesting an app registration.**

### Device code flow

```bash
TEN=<tenant-id>; CID=14d82eec-204b-4c2f-b7e8-296a70dab67e
curl -s -X POST "https://login.microsoftonline.com/$TEN/oauth2/v2.0/devicecode" \
  -d "client_id=$CID" \
  --data-urlencode "scope=https://graph.microsoft.com/Sites.Read.All https://graph.microsoft.com/Files.Read.All offline_access" \
  -o dc.json
jq -r '"CODE: \(.user_code)\nURL:  \(.verification_uri)"' dc.json
```

Show the user the code and URL, then poll (`grant_type=urn:ietf:params:oauth:grant-type:device_code`).
Treat `authorization_pending` as "keep waiting"; any other error is terminal. Codes expire in
~15 min. **Save the `refresh_token`** — see below.

Two operational notes:

- **The auth POST may be blocked by a permission classifier.** That is correct behaviour, not an
  obstacle to route around. Explain what you need and which option you recommend, and let the
  user approve. Never pivot to scanning the filesystem or keychain for cached credentials.
- **Poll with a real wait**, not a busy loop. On macOS `sleep` may be blocked in the foreground;
  use `perl -e 'select(undef,undef,undef,5)'`.

### Refresh before the long walk, not after

Access tokens last ~1 h; a deep enumeration can outlive one. Write this first:

```bash
R=$(curl -s -X POST "https://login.microsoftonline.com/$TEN/oauth2/v2.0/token" \
  -d "grant_type=refresh_token" -d "client_id=$CID" \
  --data-urlencode "scope=https://graph.microsoft.com/Sites.Read.All https://graph.microsoft.com/Files.Read.All offline_access" \
  --data-urlencode "refresh_token=$(cat grefresh.txt)")
echo "$R" | jq -r .access_token  > gtok.txt
echo "$R" | jq -r .refresh_token > grefresh.txt
```

Background walkers read the token **once at startup**, so refreshing mid-walk does not rescue an
already-running process. For very large trees, either re-read the token file per request or
split the walk into subtree chunks.

---

## Rung 4 — Tenant changes (ask first)

Only when rungs 1–3 all fail. Present the options with their blast radius and let the user pick:

| Option | Blast radius |
|---|---|
| Add `Sites.Read.All` to an existing first-party SP's grant | Tenant-wide change to a Microsoft app |
| New app registration + delegated scopes + device code | New app; user-scoped data access |
| New app registration + application scopes + secret | New app with **read access to every site**; fully non-interactive |
| Authorise a hosted connector | Depends on connector; needs an interactive session |

---

## Graph endpoints worth knowing

```
GET /sites/{host}:/                                    # root site by hostname
GET /sites/{host}:/sites/{path}                        # site by server-relative path
GET /sites?search={q}                                  # DISCOVERS SITES YOU DID NOT KNOW EXIST
GET /sites/{siteId}/drives?$select=id,name,webUrl      # document libraries
GET /drives/{driveId}/root:/{urlEncodedPath}           # item by path
GET /drives/{driveId}/root:/{path}:/children?$top=200  # list children (follow @odata.nextLink)
GET /drives/{driveId}/items/{itemId}/children?$top=200
GET /drives/{driveId}/root/search(q='term')?$top=200   # single-library search
POST /search/query                                     # tenant-wide, supports KQL
GET /me/memberOf?$select=displayName                   # group names hint at project sites
```

`/sites?search=` is the single highest-value discovery call — it is how you find the dedicated
team site nobody mentioned.

---

## Search: use KQL, and prefer filenames

`POST /search/query` with `entityTypes:["driveItem"]` defaults to full-text, which is far too
noisy for building a candidate pool: a bare term returned **1000+ paged hits** where
`filename:` returned ~35 usable ones.

```
filename:zamconnect
filename:"Test Plan" OR filename:"Test Cases" OR filename:"Test Strategy"
filename:test AND path:"Project Alpha"
filename:UAT
```

Body shape:

```json
{"requests":[{"entityTypes":["driveItem"],
              "query":{"queryString":"filename:foo"},
              "from":0,"size":100,
              "fields":["name","webUrl","lastModifiedDateTime","size","parentLink"]}]}
```

Page with `from` until `hitsContainers[0].moreResultsAvailable` is false. Cap total pages —
full-text queries will happily page forever.

**Search hits usually do not populate `parentReference.path`.** Recover the location from
`webUrl` instead:

```python
import urllib.parse
p = urllib.parse.unquote(hit['resource']['webUrl'])
p = p.replace('https://tenant.sharepoint.com/Shared Documents/', '/')
```

Also note: some hits point at `…/Shared Documents/Forms/DispForm.aspx?ID=NNN` (a list-item form,
not a file path) and others at `…-my.sharepoint.com/personal/…` (**OneDrive personal**). Personal
copies are usually *not* valid deliverables — cite the shared-library copy and treat a
personal-only document as a finding.

---

## URLs: build clean paths, do not reuse viewer URLs

Graph returns `webUrl` for Office files as:

```
https://tenant.sharepoint.com/_layouts/15/Doc.aspx?sourcedoc=%7BGUID%7D&file=Name.docx&action=edit
```

Functional but opaque and unreviewable. Prefer a path-based URL:

```python
import urllib.parse
BASE = "https://tenant.sharepoint.com/Shared%20Documents/"                       # root site
BASE = "https://tenant.sharepoint.com/sites/<Site>/Shared%20Documents/"          # team site
url  = BASE + urllib.parse.quote(relative_path)
```

Both resolve. Path URLs are readable, diff-friendly and let a human spot a wrong link by eye.

**Then verify them.** Turn each URL back into a `GET /drives/{driveId}/root:/{path}` call and
confirm 200. In the source session this caught 2 wrong links out of 112 — both from paths
reconstructed by hand out of search output instead of taken from an enumeration result.
Take paths from the index; never retype them.

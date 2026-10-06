---
name: payment-callback
description: Add a ZamPay / DotGovPay payment callback destination to the GOVZM tenant, so that paid receipts for a destination code are forwarded to the agency's system. Writes the callback client under `src/Tenants/GOVZM/Endpoints/`, the `case "<CODE>"` in the `PayController` transaction-callback switch, the `Endpoints:<Client>` section in both GOVZM appsettings files, and a forwarding test in `GOVZM.Tests`. Also maps an extra destination code onto an existing callback client. Use when the user says "add <SYSTEM> payment callback", "send ZamPay callbacks to <system>", "add callback destination <CODE> to GOVZM", "map service code <CODE> to the <X> callback", or types /payment-callback.
argument-hint: "<DestinationCode> [--system <Name>] [--kind rest|zampoint|alias] [--alias-of <Client>] [--path </payment/callback>] [--auth Basic|JWT|Custom|None] [--auth-header <name>] [--test-url <url>] [--no-tests] [--auto] [--dry-run] [--help]"
allowed-tools: Read Write Edit Glob Grep Bash(grep *) Bash(awk *) Bash(ls *) Bash(mkdir *) Bash(dotnet *) AskUserQuestion
disable-model-invocation: false
---

# GOVZM Payment Callback Destination

ZamPay posts every paid receipt to `POST /Pay/transaction/callback` on GOVZM, with a `destinationCode` header. `PayController.TransactionCallback` checks the caller's `services` / `scope` claims, then resolves an `ITransactionCallback` client from that code. It converts the receipt to the legacy format and forwards it with `TransactionCallback(payload)`. An unknown code returns `400 "Invalid Target"`.

A new destination always touches the same four files, as in PR 49802 (NPDD), 48880 (PO, ZABS), 47590 (OSHSD) and 47419 (PAMS):

| File | Change |
|---|---|
| `src/Tenants/GOVZM/Endpoints/<Client>.cs` | New client that implements `ITransactionCallback` |
| `src/Tenants/GOVZM/Controllers/PayController.cs` | One `case "<CODE>":` in the `TransactionCallback` switch |
| `src/Tenants/GOVZM/appsettings.json` | `Endpoints:<Client>` with `__Token__` placeholders |
| `src/Tenants/GOVZM/appsettings.Development.json` | The same section, test `BaseUrl`, credential placeholders |

`RegisterEndpoints` registers every `IRestEndpoint` in the assembly, but **only when `Endpoints:<Client>` exists in config**. Without the section it logs `Endpoint <Client> is not configured`, and the callback fails at run time on `GetRequiredService`. The config section is not optional.

All paths are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`). Every question follows `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`. Shared facts — usings and namespace (C1), `Username` casing (C3), token naming (C4), file hygiene (C6), committed-secrets baseline (C7), `ENVIRONMENT-VARIABLES.json` (C9), local-only scope (C10) — live in `${CLAUDE_PLUGIN_ROOT}/references/zamconnect-conventions.md`. Read it before writing.

## Arguments

| Argument | Meaning |
|---|---|
| `<DestinationCode>` | The `destinationCode` header value ZamPay sends, e.g. `NPDD`. Required. Upper case, `^[A-Z][A-Z0-9]{1,15}$`. When omitted, asked first in plain text (R2 exception: nothing on disk to offer). `--auto` stops with `missing <DestinationCode>` |
| `--system <Name>` | PascalCase system name for the client class. Default: the code with only its first letter upper case (`NPDD` → `Npdd`). Pass it when the agency name differs from the code (`PAMS` → `--system MihudPams`) |
| `--kind rest\|zampoint\|alias` | `rest` (default): a new `<System>Api : RestEndpoint, ITransactionCallback`. `zampoint`: a new `ZamPoint<System> : ZamPointEndpoint`, for an agency on the ZamPoint platform. `alias`: map the code onto an existing client, nothing new is written but the `case` |
| `--alias-of <Client>` | With `--kind alias`, the existing client class the code joins, e.g. `ZamPointMota`. Implies `--kind alias` |
| `--path <path>` | Callback path on the agency system, absolute from the host root. Default `/payment/callback`. `rest` only; `ZamPointEndpoint` fixes it to `/payment/callback` |
| `--auth Basic\|JWT\|Custom\|None` | Auth on the agency's callback endpoint. Default `Basic`, the scheme of every destination added since 2023. `None` only when passed or picked explicitly |
| `--auth-header <name>` | With `--auth Custom`, the header name, e.g. `X-Api-Key`. Asked when missing |
| `--test-url <url>` | Development `BaseUrl`. Default by convention: `https://<code>api.test.gsb.gov.zm` (`rest`), `https://zampoint<code>.test.gsb.gov.zm` (`zampoint`), code in lower case |
| `--no-tests` | Skip step 8 |
| `--gate <n>/<N>`, `--recommend proceed\|skip` | Gate mode, set by `tenant-pipeline` |
| `--auto` | No questions. Every default above; stops only on a missing `<DestinationCode>`, or on `--kind alias` without `--alias-of` |
| `--dry-run` | Stop after the step 3 review. Write nothing |
| `--help` | Print the arguments and examples, then stop. Asks and writes nothing (R14) |

## Gate

Only with `--gate <n>/<N>`. If `<DestinationCode>` wasn't passed, ask it in plain text first. Run the step 1 checks; if one stops the skill, print the reason and emit `GATE-RESULT: failed <reason>` without asking. Otherwise make one call:

| Header | Question | Options |
|---|---|---|
| `Step <n>/<N>` | `/payment-callback <CODE>` — forward ZamPay receipts for `<CODE>` from GOVZM to the agency system. Run it? | `Proceed` — REST client `<System>Api`, Basic auth, `/payment/callback`, convention test URL, forwarding test · `Customize…` — also choose client kind, auth, path, test URL · `Skip` · `Stop` |

`(Recommended)` goes on `Proceed` with `--recommend proceed`, and on `Skip` with `--recommend skip`. `Skip` → `GATE-RESULT: skipped`. `Stop` → `GATE-RESULT: stopped`. `Proceed` goes straight to step 3 with the defaults. `Customize…` asks step 2 first.

## 1. Read GOVZM

Re-derive everything; the switch grows with every destination.

```bash
# Codes already mapped, and the client each one resolves
awk '/public async Task TransactionCallback\(/{f=1} f && /case "|GetRequiredService</{print NR": "$0} f && /default:/{exit}' src/Tenants/GOVZM/Controllers/PayController.cs
# Existing callback clients, direct or through ZamPointEndpoint
grep -lE 'ITransactionCallback|:[[:space:]]*ZamPointEndpoint' src/Tenants/GOVZM/Endpoints/*.cs
# Callback paths in use, most common first
grep -ohE 'Post\("[^"]+", payload' src/Tenants/GOVZM/Endpoints/*.cs | sort | uniq -c | sort -rn
# Section names only, never their values
grep -nE '^ {8}"[A-Za-z0-9]+": \{' src/Tenants/GOVZM/appsettings.json
```

Stop with the reason when:

- The code already has a `case` (`case "<CODE>"` or `or "<CODE>"`). Name the client it maps to. Changing it is a hand edit, not this skill.
- `--kind rest|zampoint` and the derived client class already exists: `ls src/Tenants/GOVZM/Endpoints/<Client>.cs`, or `grep -rlE "class <Client>\b" src/Tenants/GOVZM`. Suggest `--system <OtherName>`, or `--alias-of <Client>` when it's the same agency.
- `--kind alias` and `--alias-of` names a class with no `case` in the switch, or one that doesn't implement `ITransactionCallback`.
- `Endpoints:<Client>` already exists in either appsettings file for a new client.

## 2. Collect inputs

Skip every question whose flag was passed (R1). One `AskUserQuestion` call, at most four questions:

| Header | Question | Options | → flag |
|---|---|---|---|
| `Client` | How should GOVZM reach `<CODE>`? | `New REST client <System>Api (Recommended)` — `RestEndpoint` with its own path · `ZamPoint client ZamPoint<System>` — agency on the ZamPoint platform, `/payment/callback` · `Existing client` — map `<CODE>` onto a client that already has a case | `--kind` |
| `Auth` | How does the agency authenticate the callback? | `Basic (Recommended)` · `Custom header` · `JWT bearer` · `None — open endpoint` | `--auth` |
| `Path` | Callback path on the agency system — or paste a path in Other. | The distinct paths from the step 1 grep, most used first, `(Recommended)` on the first. Ignored for `zampoint` and `alias` | `--path` |
| `Test URL` | Development base URL — or paste a URL in Other. | `https://<code>api.test.gsb.gov.zm (Recommended)` · `https://zampoint<code>.test.gsb.gov.zm`. Ignored for `alias` | `--test-url` |

Follow-ups, one call each, only when needed:

- `Existing client` → header `Client`, which client `<CODE>` joins. Options: up to 3 clients from the step 1 list whose name or existing codes share a prefix with `<CODE>`, then "…or type the class name in Other". Check the answer as in step 1.
- `Custom header` without `--auth-header` → header `Header`, options `X-Api-Key` · `Authorization`, or Other.

Echo the interpretation (R11): "Read as: REST client `NpddApi`, Basic auth, `POST /payment/callback`, test URL `https://npddapi.test.gsb.gov.zm`".

## 3. Review before writing

One call (R6), header `Review`. The question text holds the plan:

```
GOVZM payment callback NPDD
  add     src/Tenants/GOVZM/Endpoints/NpddApi.cs                  RestEndpoint, ITransactionCallback, POST /payment/callback
  change  src/Tenants/GOVZM/Controllers/PayController.cs          case "NPDD" → NpddApi
  change  src/Tenants/GOVZM/appsettings.json                      Endpoints:NpddApi, Basic, 3 tokens
  change  src/Tenants/GOVZM/appsettings.Development.json          Endpoints:NpddApi, https://npddapi.test.gsb.gov.zm
  change  src/Tests/GOVZM.Tests/Endpoints/TransactionCallbackEndpointTests.cs   + NpddApi row
Command: /payment-callback NPDD --system Npdd --kind rest --auth Basic --path /payment/callback --test-url https://npddapi.test.gsb.gov.zm
```

Options: `Apply (Recommended)` · `Adjust` · `Cancel`. `Adjust` asks one `multiSelect` with the step 2 questions plus `Class name`, then re-asks only the ones picked. With `--dry-run`, print the plan and stop here.

## 4. Write the client

Skip for `alias`. Primary-constructor shape, matching the newest clients (`NpddApi`, `PoApi`, `ZabsApi`):

`rest` — `src/Tenants/GOVZM/Endpoints/<System>Api.cs`:

```csharp
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Internal.Clients;

namespace GOVZM.Endpoints;

public class <System>Api(HttpClient client) : RestEndpoint(client), ITransactionCallback
{
    public async Task<HttpResponseMessage> TransactionCallback(string payload, CancellationToken cancellationToken) =>
        await Post("<path>", payload, cancellationToken);
}
```

`zampoint` — `src/Tenants/GOVZM/Endpoints/ZamPoint<System>.cs`. `ZamPointEndpoint` already implements `TransactionCallback` (and `DataExchange`):

```csharp
using System.Net.Http;

namespace GOVZM.Endpoints;

public class ZamPoint<System>(HttpClient client) : ZamPointEndpoint(client);
```

`<path>` is absolute: `Post` with a leading `/` drops any path in `BaseUrl`. When the agency's callback sits under a base path, put the whole path in `--path` and keep `BaseUrl` host-only.

## 5. Map the destination code

Read only the lines around the anchor, found with the step 1 `awk`. Don't open the whole controller.

New client: insert the case **before** `default:` in the `TransactionCallback` switch, with the switch's indentation (16 spaces for `case`, 20 for the body). The `Log.ForContext("type", "DotGovPay.GOVZM")` / `Invalid Transaction Callback target` lines below `default:` make the `Edit` anchor unique:

```csharp
                case "<CODE>":
                    endpoint = serviceProvider.GetRequiredService<<Client>>();
                    break;
```

`alias`: extend the existing case line of `<Client>` with `or "<CODE>"`, following PR 46108 (`case "MOTA" or "DNPW" or "DOT" or "ZTA":`). When that client still uses stacked labels (`case "MAL":` / `case "DAM":`), add one more stacked label above its body instead.

## 6. Configure both appsettings files

Skip for `alias`. GOVZM's appsettings files are JSONC: `appsettings.Development.json` holds `//` comments, so a JSON parser rejects it. Edit them as text with `Edit`, never by re-serialising.

Find the end of the `Endpoints` object without printing a value:

```bash
for f in appsettings.json appsettings.Development.json; do
  s=$(grep -nE '^ {4}"Endpoints": \{' src/Tenants/GOVZM/$f | cut -d: -f1)
  awk -v s="$s" -v f="$f" 'NR > s && /^    \}/ { print f": Endpoints closes at line "NR; exit }' src/Tenants/GOVZM/$f
done
```

`Read` only the closing line of the last entry, the `Endpoints` closing line, and the next top-level key (`offset` = close − 1, `limit` = 3). Those lines hold no credential. Replace them with the same three lines, a `,` after the last entry's `}`, and the new section between, at 8 spaces for the key and 12 for its members.

Key order follows `NpddApi`. Keys are `Username`, never `UserName` (C3):

| `--auth` | `appsettings.json` members | `appsettings.Development.json` differs only in |
|---|---|---|
| `Basic` | `"AuthenticationScheme": "Basic"`, `"Username": "__Endpoints.<Client>.Username__"`, `"Password": "__Endpoints.<Client>.Password__"`, `"BaseUrl": "__Endpoints.<Client>.BaseUrl__"` | `"BaseUrl": "<test-url>"` |
| `JWT` | `"AuthenticationScheme": "JWT"`, `"AuthHeaderValue": "__Endpoints.<Client>.AuthHeaderValue__"`, `"BaseUrl": "__Endpoints.<Client>.BaseUrl__"` | `"BaseUrl": "<test-url>"` |
| `Custom` | `"AuthenticationScheme": "Custom"`, `"AuthHeaderName": "<header>"`, `"AuthHeaderValue": "__Endpoints.<Client>.AuthHeaderValue__"`, `"BaseUrl": "__Endpoints.<Client>.BaseUrl__"` | `"BaseUrl": "<test-url>"` |
| `None` | `"BaseUrl": "__Endpoints.<Client>.BaseUrl__"` | `"BaseUrl": "<test-url>"` |

Credentials stay `__Token__` placeholders in the Development file too (C7). Older sections there hold `replaceme` or literal values; never copy either.

## 7. Environment variables

Skip for `alias`. The tokens written in step 6 need variables in `GSB.GOVZM.{DEV,STG,PROD}`, or `replacetokens` (`actionOnMissing: fail`) fails the GOVZM deploy (C4).

- When `src/Tenants/GOVZM/ENVIRONMENT-VARIABLES.json` exists, append one entry per token in the order they appear in `appsettings.json`, in the C9 format. `secret: true` for `Username`, `Password` and `AuthHeaderValue`; `value` always `""`.
- When it doesn't exist, don't create it. A file listing only the new tokens would fail `tenant-audit` Check 4, which needs every GOVZM token. List the names in the report instead.

## 8. Tests

Skip with `--no-tests`. `GOVZM.Tests` already exists and is in `ZamConnect.sln`. Its other fixtures call live systems, so run only this fixture.

`src/Tests/GOVZM.Tests/TestHelpers/MockHttpMessageHandler.cs` — create it when missing, as the **recording** variant from `src/Tests/APIS.Tests/TestHelpers/MockHttpMessageHandler.cs`, namespace `GOVZM.Tests.TestHelpers`.

`src/Tests/GOVZM.Tests/Endpoints/TransactionCallbackEndpointTests.cs` — create it on the first run. On later runs, add only one row to `Destinations`; for `alias`, add a row only when the client has none yet:

```csharp
using System;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using FluentAssertions;
using GOVZM.Endpoints;
using GOVZM.Tests.TestHelpers;
using Microsoft.Extensions.Configuration;
using NUnit.Framework;

namespace GOVZM.Tests.Endpoints;

[TestFixture]
public class TransactionCallbackEndpointTests
{
    private static readonly object[] Destinations =
    [
        new object[] { typeof(<Client>), "<path>" },
    ];

    [TestCaseSource(nameof(Destinations))]
    public async Task TransactionCallback_PostsPayloadToDestinationPath(Type endpointType, string path)
    {
        var handler = new MockHttpMessageHandler();
        var client = new HttpClient(handler) { BaseAddress = new Uri("http://callback-test") };
        var endpoint = (ITransactionCallback)Activator.CreateInstance(endpointType, client);
        const string payload = "{\"invoiceNumber\":\"INV-1\"}";

        var response = await endpoint.TransactionCallback(payload, CancellationToken.None);

        response.IsSuccessStatusCode.Should().BeTrue();
        handler.Requests.Should().ContainSingle();
        handler.Requests[0].Method.Should().Be(HttpMethod.Post);
        handler.Requests[0].RequestUri.AbsolutePath.Should().Be(path);
        handler.RequestBodies[0].Should().Be(payload);
    }

    [TestCaseSource(nameof(Destinations))]
    public void Endpoint_IsConfiguredInBothAppsettingsFiles(Type endpointType, string path)
    {
        foreach (var file in new[] { "appsettings.json", "appsettings.Development.json" })
        {
            var section = LoadTenantSettings(file).GetSection($"Endpoints:{endpointType.Name}");

            section.Exists().Should().BeTrue(
                $"{file} must hold Endpoints:{endpointType.Name}, or RegisterEndpoints skips the client and the callback fails at runtime");
            section["BaseUrl"].Should().NotBeNullOrWhiteSpace();
        }
    }

    private static IConfiguration LoadTenantSettings(string file)
    {
        var dir = new DirectoryInfo(TestContext.CurrentContext.TestDirectory);
        while (dir != null && !File.Exists(Path.Combine(dir.FullName, "ZamConnect.sln")))
            dir = dir.Parent;

        dir.Should().NotBeNull("the test runs inside the ZamConnect src tree");

        return new ConfigurationBuilder()
            .AddJsonFile(Path.Combine(dir.FullName, "Tenants", "GOVZM", file), optional: false)
            .Build();
    }
}
```

The configuration builder reads the JSONC files as they are; it skips comments. The test reads only `BaseUrl` and never a credential. The `path` value for a `zampoint` client is `/payment/callback`.

## 9. Verify

```bash
dotnet build src/Tenants/GOVZM/GOVZM.csproj -v q --nologo
dotnet test src/Tests/GOVZM.Tests/GOVZM.Tests.csproj --filter "FullyQualifiedName~TransactionCallbackEndpointTests" --nologo -v q
```

The build must report `0 Error(s)` and every fixture row must pass. Never weaken an assertion to make a row pass; fix the client, the case or the config. Then check without running the app:

- Exactly one `case` holds `"<CODE>"`: rerun the step 1 `awk`
- `Endpoints:<Client>` exists in both appsettings files, and its tokens are `__Endpoints.<Client>.<Key>__`
- `grep -nE '"UserName"|__[A-Za-z.]*UserName__' src/Tenants/GOVZM/appsettings*.json` finds nothing new
- The new Development section holds no literal credential

## Report

One line per file added or changed, then the destination: code → client → `POST <path>` → auth. Then what an administrator does by hand (C10):

- Add the variables to `GSB.GOVZM.DEV`, `GSB.GOVZM.STG` and `GSB.GOVZM.PROD`, names only: `Endpoints.<Client>.BaseUrl`, plus `.Username` / `.Password` (Basic) or `.AuthHeaderValue` (JWT, Custom). Without them the GOVZM deploy fails on `replacetokens`
- Confirm with the ZamPay service configuration that receipts for this agency are sent with `destinationCode: <CODE>`
- Confirm with the agency that its endpoint accepts the legacy receipt payload at `POST <path>`
- For `zampoint`: data exchange through `DataExchangeController` is a separate change; this skill maps only the payment callback

End with the equivalent command (R7), e.g. `/payment-callback NPDD --system Npdd --kind rest --auth Basic --path /payment/callback --test-url https://npddapi.test.gsb.gov.zm`, and these answers for the pipeline state: `code`, `kind`, `client`, `auth`, `path`. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>` when a step 1 check stops the skill, or the step 9 build or test fails.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints. The one exception is the test `BaseUrl`, which C7 allows.

- In generated config, a secret is a `__Token__` placeholder, in `appsettings.Development.json` too. Never write a registry, Helm, cluster, MongoDB, RA or ZamPass address (C10).
- GOVZM's `appsettings.Development.json` commits literal credentials for older destinations (C7). Never print a line of it beyond the anchor lines step 6 names, never `cat` or `sed` it whole, and never copy a value out of it. Report the literals as a baseline finding without printing them; rotation is a separate ticket.
- A credential passed as an argument is used nowhere. Never echo it, never write it to a file, and never put it in a commit message or a PR description.

---
name: data-exchange
description: Add a data-exchange target to the GOVZM tenant, so that `POST /DataExchange/SendData` with `"Target": "<CODE>"` forwards the `Obj` / `Xml` payload to the agency's system. Writes the client under `src/Tenants/GOVZM/Endpoints/` (or reuses the agency's existing one), the `case "<CODE>"` in the `DataExchangeController.SendData` switch, the `Endpoints:<Client>` section in both GOVZM appsettings files, and a routing test in `GOVZM.Tests`. Also maps an extra target code onto an existing client. Use when the user says "add <SYSTEM> data exchange", "send data exchange to <system>", "add DataExchange target <CODE>", "route SendData for <CODE> to GOVZM", "ZamPoint <agency> data exchange", or types /data-exchange.
argument-hint: "<TargetCode> [--system <Name>] [--kind zampoint|rest|alias] [--alias-of <Client>] [--path </DataExchange/SetData>] [--auth Basic|JWT|Custom|None] [--auth-header <name>] [--test-url <url>] [--no-tests] [--auto] [--dry-run] [--help]"
allowed-tools: Read Write Edit Glob Grep Bash(grep *) Bash(awk *) Bash(ls *) Bash(mkdir *) Bash(dotnet *) AskUserQuestion
disable-model-invocation: false
---

# GOVZM Data Exchange Target

The ZamPoint platform posts case data to `POST /t/govzm/DataExchange/SendData` (route `data_exchange`, Basic auth at the gateway). The body is `SendDataDetails { Obj, Xml, Target }`. `DataExchangeController.SendData` upper-cases `Target`, resolves an `IDataExchangeEndpoint` client from it, serialises the whole body with `System.Text.Json` and forwards it with `DataExchange(payload)`. An unknown target returns `400 "Invalid Target"` and logs a `GSB.DataExchange` warning. The controller checks no claim; the gateway route is the only access control.

`ZamPointEndpoint` implements both `IDataExchangeEndpoint` (`POST /DataExchange/SetData`) and `ITransactionCallback` (`POST /payment/callback`). Every target since 2022 except `DOC` uses it. A new target touches the same four files as `bec6da41` (ZDA) and `d0844faa` (MFL):

| File | Change |
|---|---|
| `src/Tenants/GOVZM/Endpoints/<Client>.cs` | New client that implements `IDataExchangeEndpoint` |
| `src/Tenants/GOVZM/Controllers/DataExchangeController.cs` | One `case "<CODE>":` in the `SendData` switch |
| `src/Tenants/GOVZM/appsettings.json` | `Endpoints:<Client>` with `__Token__` placeholders |
| `src/Tenants/GOVZM/appsettings.Development.json` | The same section, test `BaseUrl`, credential placeholders |

`RegisterEndpoints` registers every `IRestEndpoint` in the assembly, but **only when `Endpoints:<Client>` exists in config**. Without the section it logs `Endpoint <Client> is not configured`, and `SendData` fails at run time on `GetRequiredService`. The config section is not optional.

The `SendData` switch and the `PayController.TransactionCallback` switch are independent. The same code can resolve different clients in each (`DOC` → `ZamPointDoc` here, `DocFeApi` there). Never align them; this skill touches only `SendData`.

All paths are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`). Every question follows `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`. Shared facts — usings and namespace (C1), `Username` casing (C3), token naming (C4), file hygiene (C6), committed-secrets baseline (C7), `ENVIRONMENT-VARIABLES.json` (C9), local-only scope (C10) — live in `${CLAUDE_PLUGIN_ROOT}/references/zamconnect-conventions.md`. Read it before writing.

## Arguments

| Argument | Meaning |
|---|---|
| `<TargetCode>` | The `Target` value the ZamPoint platform sends, e.g. `ERS`. Required. Upper case, `^[A-Z][A-Z0-9]{1,15}$`. When omitted, asked first in plain text (R2 exception: nothing on disk to offer). `--auto` stops with `missing <TargetCode>` |
| `--system <Name>` | PascalCase system name for the client class. Default: the code with only its first letter upper case (`ZICTA` → `Zicta`). Pass it when the agency name differs from the code (`MGEE` → `--system Forestry`) |
| `--kind zampoint\|rest\|alias` | `zampoint` (default): a new `ZamPoint<System> : ZamPointEndpoint`. `rest`: a new `<System>Api : RestEndpoint, IDataExchangeEndpoint` with its own path, the `ZamPointDoc` shape, for an agency not on ZamPoint. `alias`: reuse an existing GOVZM client, see step 5 |
| `--alias-of <Client>` | With `--kind alias`, the existing client class, e.g. `ZamPointErs`. Implies `--kind alias` |
| `--path <path>` | Data-exchange path on the agency system, absolute from the host root. Default `/DataExchange/SetData`. Used by `rest`, and by `alias` when the client gains the interface; `ZamPointEndpoint` fixes it |
| `--auth Basic\|JWT\|Custom\|None` | Auth on the agency's endpoint. Default `Basic`, the scheme of every ZamPoint section but one. `None` only when passed or picked explicitly. New clients only |
| `--auth-header <name>` | With `--auth Custom`, the header name, e.g. `X-Api-Key`. Asked when missing |
| `--test-url <url>` | Development `BaseUrl`. Default by convention: `https://zampoint<code>.test.gsb.gov.zm` (`zampoint`), `https://<code>api.test.gsb.gov.zm` (`rest`), code in lower case. New clients only |
| `--no-tests` | Skip step 8 |
| `--gate <n>/<N>`, `--recommend proceed\|skip` | Gate mode, as in the interaction contract |
| `--auto` | No questions. Takes the `(Recommended)` client from step 2 and every default above; stops only on a missing `<TargetCode>` |
| `--dry-run` | Stop after the step 3 review. Write nothing |
| `--help` | Print the arguments and examples, then stop. Asks and writes nothing (R14) |

## Gate

Only with `--gate <n>/<N>`. If `<TargetCode>` wasn't passed, ask it in plain text first. Run the step 1 checks; if one stops the skill, print the reason and emit `GATE-RESULT: failed <reason>` without asking. Otherwise make one call:

| Header | Question | Options |
|---|---|---|
| `Step <n>/<N>` | `/data-exchange <CODE>` — forward ZamPoint data exchange for `<CODE>` from GOVZM to the agency system. Run it? | `Proceed` — the step 2 `(Recommended)` client, Basic auth, convention test URL, routing test · `Customize…` — also choose client, auth, path, test URL · `Skip` · `Stop` |

`(Recommended)` goes on `Proceed` with `--recommend proceed`, and on `Skip` with `--recommend skip`. `Skip` → `GATE-RESULT: skipped`. `Stop` → `GATE-RESULT: stopped`. `Proceed` goes straight to step 3 with the defaults. `Customize…` asks step 2 first.

## 1. Read GOVZM

Re-derive everything; both switches grow with every agency.

```bash
# Targets already mapped, and the client each one resolves
awk '/public async Task SendData\(/{f=1} f && /case "|GetRequiredService</{print NR": "$(0)} f && /default:/{exit}' src/Tenants/GOVZM/Controllers/DataExchangeController.cs
# Payment-callback codes: the agency's client may already exist
awk '/public async Task TransactionCallback\(/{f=1} f && /case "|GetRequiredService</{print NR": "$(0)} f && /default:/{exit}' src/Tenants/GOVZM/Controllers/PayController.cs
# Clients that already implement data exchange, directly or through ZamPointEndpoint
grep -lE 'IDataExchangeEndpoint|:[[:space:]]*ZamPointEndpoint' src/Tenants/GOVZM/Endpoints/*.cs | grep -vE '/(ZamPointEndpoint|IDataExchangeEndpoint)\.cs$'
# Section names only, never their values
grep -nE '^ {8}"[A-Za-z0-9]+": \{' src/Tenants/GOVZM/appsettings.json
```

From these, find the **agency client**: the client of `<CODE>`'s `PayController` case, else an existing `ZamPoint<System>.cs` or `<System>Api.cs`. Classify it:

| Agency client | Meaning |
|---|---|
| Implements `IDataExchangeEndpoint` (directly or via `ZamPointEndpoint`) | Ready: only the `case` is missing. Today `ZamPointErs`, `ZamPointMprs`, `ZamPointMmmd`, … — derive, don't trust this list |
| `RestEndpoint` without the interface | Extendable: gains `IDataExchangeEndpoint` and one `DataExchange` method |
| Anything else (`GsbEndpoint`, SOAP, …) | Not usable; a new client is needed |

Stop with the reason when:

- The code already has a `case` in `SendData` (`case "<CODE>"` or `or "<CODE>"`). Name the client it maps to. Changing it is a hand edit, not this skill.
- `--kind zampoint|rest` and the derived client class already exists: `ls src/Tenants/GOVZM/Endpoints/<Client>.cs`, or `grep -rlE "class <Client>\b" src/Tenants/GOVZM`. Suggest `--alias-of <Client>` when it's the same agency, or `--system <OtherName>`.
- `--kind alias` and `--alias-of` names a class that doesn't exist, or one that is neither ready nor extendable.
- `--kind alias` and `Endpoints:<Client>` is missing from either appsettings file. The client is already broken at run time; report it, and leave the fix to the developer.
- `Endpoints:<Client>` already exists in either appsettings file for a new client.

## 2. Collect inputs

Skip every question whose flag was passed (R1).

**Call 1**, header `Client`: "How should GOVZM reach `<CODE>`?" Build the options from step 1 (R5), at most four, in this order:

| Option | Shown when | → flags |
|---|---|---|
| `Existing client <Client>` — already forwards `<CODE>` payment callbacks / already on ZamPoint | Agency client is ready | `--alias-of <Client>` |
| `Extend <Client>` — add `IDataExchangeEndpoint` to the agency's REST client | Agency client is extendable | `--alias-of <Client>` |
| `New ZamPoint client ZamPoint<System>` — `POST /DataExchange/SetData` | Always | `--kind zampoint` |
| `New REST client <System>Api` — own path, `ZamPointDoc` shape | Always | `--kind rest` |
| `Other existing client` — reuse a client mapped to another code | No agency client found | `--kind alias` |

`(Recommended)` goes on `Existing client` when shown, otherwise on `New ZamPoint client`. `Extend` is never recommended: the agency's REST system may not take the ZamPoint payload.

**Call 2**, only the questions the answer needs, at most four:

| Header | Asked when | Question | Options | → flag |
|---|---|---|---|---|
| `Auth` | New client | How does the agency authenticate the data-exchange call? | `Basic (Recommended)` · `Custom header` · `JWT bearer` · `None — open endpoint` | `--auth` |
| `Test URL` | New client | Development base URL — or paste a URL in Other. | The convention URL for the kind `(Recommended)` · the other kind's convention URL | `--test-url` |
| `Path` | `rest`, or `Extend` | Data-exchange path on the agency system — or paste a path in Other. | `/DataExchange/SetData (Recommended)` — the ZamPoint contract · `/api/DataExchange/SetData` | `--path` |
| `Client` | `Other existing client` | Which client should `<CODE>` join — or type the class name in Other. | Up to 3 ready clients from step 1 whose name or codes share a prefix with `<CODE>` | `--alias-of` |
| `Header` | `Custom header` without `--auth-header` | Which header carries the key? | `X-Api-Key` · `Authorization` | `--auth-header` |

`Header` depends on `Auth`, so it goes in a third call when needed. Check an `Other existing client` answer as in step 1.

Echo the interpretation (R11): "Read as: new ZamPoint client `ZamPointZicta`, Basic auth, `POST /DataExchange/SetData`, test URL `https://zampointzicta.test.gsb.gov.zm`", or "Read as: existing client `ZamPointErs`, new `case "ERS"`".

## 3. Review before writing

One call (R6), header `Review`. The question text holds the plan:

```
GOVZM data exchange ZICTA
  add     src/Tenants/GOVZM/Endpoints/ZamPointZicta.cs                 ZamPointEndpoint, POST /DataExchange/SetData
  change  src/Tenants/GOVZM/Controllers/DataExchangeController.cs     case "ZICTA" → ZamPointZicta
  change  src/Tenants/GOVZM/appsettings.json                          Endpoints:ZamPointZicta, Basic, 3 tokens
  change  src/Tenants/GOVZM/appsettings.Development.json              Endpoints:ZamPointZicta, https://zampointzicta.test.gsb.gov.zm
  change  src/Tests/GOVZM.Tests/Controllers/DataExchangeControllerTests.cs   + ZICTA row
Command: /data-exchange ZICTA --system Zicta --kind zampoint --auth Basic --test-url https://zampointzicta.test.gsb.gov.zm
```

For a ready client, the plan holds only the controller and test lines. Options: `Apply (Recommended)` · `Adjust` · `Cancel`. `Adjust` asks one `multiSelect` with the step 2 questions plus `Class name`, then re-asks only the ones picked. With `--dry-run`, print the plan and stop here.

## 4. Write the client

`zampoint` — `src/Tenants/GOVZM/Endpoints/ZamPoint<System>.cs`, the primary-constructor shape of `ZimsApi`:

```csharp
using System.Net.Http;

namespace GOVZM.Endpoints;

public class ZamPoint<System>(HttpClient client) : ZamPointEndpoint(client);
```

`rest` — `src/Tenants/GOVZM/Endpoints/<System>Api.cs`, the shape of `ZamPointDoc`:

```csharp
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Internal.Clients;

namespace GOVZM.Endpoints;

public class <System>Api(HttpClient client) : RestEndpoint(client), IDataExchangeEndpoint
{
    public async Task<HttpResponseMessage> DataExchange(string payload, CancellationToken cancellationToken) =>
        await Post("<path>", payload, cancellationToken);
}
```

`alias` with an extendable client — edit the existing file. Append `, IDataExchangeEndpoint` to the class's base list, after `ITransactionCallback` when present. Add the `DataExchange` method above as the last member, in the file's own style: block or file-scoped namespace, its indentation, its constructor form. Add `System.Threading` and `System.Threading.Tasks` to the usings when missing (C1). Change nothing else in the file.

`alias` with a ready client — write nothing here.

`<path>` is absolute: `Post` with a leading `/` drops any path in `BaseUrl`. When the agency's endpoint sits under a base path, put the whole path in `--path` and keep `BaseUrl` host-only.

## 5. Map the target code

Read only the lines around the anchor, found with the step 1 `awk`. Don't open the whole controller.

New case — for a new client, and for an `alias` client with no `SendData` case yet. Insert it **before** `default:` in the `SendData` switch, with the switch's indentation (16 spaces for `case`, 20 for the body). The `Log.ForContext("type", "GSB.DataExchange")` line below `default:` makes the `Edit` anchor unique:

```csharp
                case "<CODE>":
                    endpoint = serviceProvider.GetRequiredService<<Client>>();
                    break;
```

`alias` client that already has a `SendData` case: this switch uses stacked labels (`case "MAL":` / `case "DAM":`), so add `case "<CODE>":` directly above that client's `endpoint =` line. When its case line already uses `or`, append `or "<CODE>"` instead.

## 6. Configure both appsettings files

Skip for `alias`: the client's section already exists (step 1 checked it). GOVZM's appsettings files are JSONC: `appsettings.Development.json` holds `//` comments, so a JSON parser rejects it. Edit them as text with `Edit`, never by re-serialising.

Find the end of the `Endpoints` object without printing a value:

```bash
for f in appsettings.json appsettings.Development.json; do
  s=$(grep -nE '^ {4}"Endpoints": \{' src/Tenants/GOVZM/$f | cut -d: -f1)
  awk -v s="$s" -v f="$f" 'NR > s && /^    \}/ { print f": Endpoints closes at line "NR; exit }' src/Tenants/GOVZM/$f
done
```

`Read` only the closing line of the last entry, the `Endpoints` closing line, and the next top-level key (`offset` = close − 1, `limit` = 3). Those lines hold no credential. Replace them with the same three lines, a `,` after the last entry's `}`, and the new section between, at 8 spaces for the key and 12 for its members.

Key order follows the `ZamPoint*` sections. Keys are `Username`, never `UserName` (C3):

| `--auth` | `appsettings.json` members | `appsettings.Development.json` differs only in |
|---|---|---|
| `Basic` | `"AuthenticationScheme": "Basic"`, `"Username": "__Endpoints.<Client>.Username__"`, `"Password": "__Endpoints.<Client>.Password__"`, `"BaseUrl": "__Endpoints.<Client>.BaseUrl__"` | `"BaseUrl": "<test-url>"` |
| `JWT` | `"AuthenticationScheme": "JWT"`, `"AuthHeaderValue": "__Endpoints.<Client>.AuthHeaderValue__"`, `"BaseUrl": "__Endpoints.<Client>.BaseUrl__"` | `"BaseUrl": "<test-url>"` |
| `Custom` | `"AuthenticationScheme": "Custom"`, `"AuthHeaderName": "<header>"`, `"AuthHeaderValue": "__Endpoints.<Client>.AuthHeaderValue__"`, `"BaseUrl": "__Endpoints.<Client>.BaseUrl__"` | `"BaseUrl": "<test-url>"` |
| `None` | `"BaseUrl": "__Endpoints.<Client>.BaseUrl__"` | `"BaseUrl": "<test-url>"` |

Credentials stay `__Token__` placeholders in the Development file too (C7). Older `ZamPoint*` sections there hold literal values; never copy one.

## 7. Environment variables

Skip for `alias`. The tokens written in step 6 need variables in `GSB.GOVZM.{DEV,STG,PROD}`, or `replacetokens` (`actionOnMissing: fail`) fails the GOVZM deploy (C4).

- When `src/Tenants/GOVZM/ENVIRONMENT-VARIABLES.json` exists, append one entry per token in the order they appear in `appsettings.json`, in the C9 format. `secret: true` for `Username`, `Password` and `AuthHeaderValue`; `value` always `""`.
- When it doesn't exist, don't create it. A file listing only the new tokens would fail `tenant-audit` Check 4, which needs every GOVZM token. List the names in the report instead.

## 8. Tests

Skip with `--no-tests`. `GOVZM.Tests` already exists and is in `ZamConnect.sln`. Its other fixtures call live systems, so run only this fixture. The project has no `ImplicitUsings`: every file carries its full `using` block (C1).

`src/Tests/GOVZM.Tests/TestHelpers/MockHttpMessageHandler.cs` — create it when missing. It is the recording variant of `src/Tests/APIS.Tests/TestHelpers/MockHttpMessageHandler.cs`, with explicit usings:

```csharp
using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;

namespace GOVZM.Tests.TestHelpers;

public class MockHttpMessageHandler : HttpMessageHandler
{
    public Func<HttpRequestMessage, HttpResponseMessage> Handler { get; set; } =
        _ => new HttpResponseMessage(HttpStatusCode.OK);

    public List<HttpRequestMessage> Requests { get; } = [];
    public List<string> RequestBodies { get; } = [];

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        Requests.Add(request);
        RequestBodies.Add(request.Content is null ? null : await request.Content.ReadAsStringAsync(cancellationToken));
        return Handler(request);
    }
}
```

`src/Tests/GOVZM.Tests/Controllers/DataExchangeControllerTests.cs` — create it on the first run. On later runs, add only one row to `Targets`. The fixture drives the real controller, so a row proves the `case`, the client and the path together:

```csharp
using System;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using FluentAssertions;
using GOVZM.Controllers;
using GOVZM.Endpoints;
using GOVZM.Models.DataExchange;
using GOVZM.Tests.TestHelpers;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using NUnit.Framework;

namespace GOVZM.Tests.Controllers;

[TestFixture]
public class DataExchangeControllerTests
{
    private static readonly object[] Targets =
    [
        new object[] { "<CODE>", typeof(<Client>), "<path>" },
    ];

    [TestCaseSource(nameof(Targets))]
    public async Task SendData_ForwardsPayloadToTargetClient(string target, Type clientType, string path)
    {
        var handler = new MockHttpMessageHandler();
        var client = Activator.CreateInstance(clientType, new HttpClient(handler) { BaseAddress = new Uri("http://dataexchange-test") });
        var services = new ServiceCollection().AddSingleton(clientType, client).BuildServiceProvider();
        var controller = CreateController();
        var details = new SendDataDetails { Obj = "Case", Xml = "<Root></Root>", Target = target };

        await controller.SendData(details, services);

        controller.Response.StatusCode.Should().Be(StatusCodes.Status200OK);
        handler.Requests.Should().ContainSingle();
        handler.Requests[0].Method.Should().Be(HttpMethod.Post);
        handler.Requests[0].RequestUri.AbsolutePath.Should().Be(path);
        JsonSerializer.Deserialize<SendDataDetails>(handler.RequestBodies[0]).Should().BeEquivalentTo(details);
    }

    [Test]
    public async Task SendData_UnknownTarget_ReturnsBadRequest()
    {
        var controller = CreateController();

        await controller.SendData(new SendDataDetails { Target = "NO-SUCH-TARGET" }, new ServiceCollection().BuildServiceProvider());

        controller.Response.StatusCode.Should().Be(StatusCodes.Status400BadRequest);
    }

    [TestCaseSource(nameof(Targets))]
    public void Client_IsConfiguredInBothAppsettingsFiles(string target, Type clientType, string path)
    {
        foreach (var file in new[] { "appsettings.json", "appsettings.Development.json" })
        {
            var section = LoadTenantSettings(file).GetSection($"Endpoints:{clientType.Name}");

            section.Exists().Should().BeTrue(
                $"{file} must hold Endpoints:{clientType.Name}, or RegisterEndpoints skips the client and SendData fails at runtime");
            section["BaseUrl"].Should().NotBeNullOrWhiteSpace();
        }
    }

    private static DataExchangeController CreateController() =>
        new() { ControllerContext = new ControllerContext { HttpContext = new DefaultHttpContext() } };

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

The `path` value is `/DataExchange/SetData` for a `ZamPointEndpoint` client, otherwise the client's `--path`. The configuration builder reads the JSONC files as they are; it skips comments. The test reads only `BaseUrl` and never a credential.

## 9. Verify

```bash
dotnet build src/Tenants/GOVZM/GOVZM.csproj -v q --nologo
dotnet test src/Tests/GOVZM.Tests/GOVZM.Tests.csproj --filter "FullyQualifiedName~DataExchangeControllerTests" --nologo -v q
```

The build must report `0 Error(s)` and every fixture row must pass. Never weaken an assertion to make a row pass; fix the client, the case or the config. Then check without running the app:

- Exactly one `case` in `SendData` holds `"<CODE>"`: rerun the step 1 `awk`
- `PayController.cs` is unchanged
- `Endpoints:<Client>` exists in both appsettings files, and a new section's tokens are `__Endpoints.<Client>.<Key>__`
- `grep -nE '"UserName"|__[A-Za-z.]*UserName__' src/Tenants/GOVZM/appsettings*.json` finds nothing new
- A new Development section holds no literal credential

## Report

One line per file added or changed, then the target: `Target: <CODE>` → client → `POST <path>` → auth. Then what an administrator does by hand (C10):

- New client only: add the variables to `GSB.GOVZM.DEV`, `GSB.GOVZM.STG` and `GSB.GOVZM.PROD`, names only: `Endpoints.<Client>.BaseUrl`, plus `.Username` / `.Password` (Basic) or `.AuthHeaderValue` (JWT, Custom). Without them the GOVZM deploy fails on `replacetokens`
- Confirm with the ZamPoint platform team that this agency's data is sent with `"Target": "<CODE>"`. The gateway route `data_exchange` already exists; no gateway change is needed
- Confirm with the agency that its system accepts the `{ "Obj", "Xml", "Target" }` JSON at `POST <path>`
- Payment callbacks are a separate mapping. When `<CODE>` has no `PayController` case and the client implements `ITransactionCallback`, suggest `/payment-callback <CODE> --alias-of <Client>`

End with the equivalent command (R7), e.g. `/data-exchange ZICTA --system Zicta --kind zampoint --auth Basic --test-url https://zampointzicta.test.gsb.gov.zm` or `/data-exchange ERS --alias-of ZamPointErs`, and these answers for the pipeline state: `code`, `kind`, `client`, `auth`, `path`. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>` when a step 1 check stops the skill, or the step 9 build or test fails.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints. The one exception is the test `BaseUrl`, which C7 allows.

- In generated config, a secret is a `__Token__` placeholder, in `appsettings.Development.json` too. Never write a registry, Helm, cluster, MongoDB, RA or ZamPass address (C10).
- GOVZM's `appsettings.Development.json` commits literal credentials for older targets (C7). Never print a line of it beyond the anchor lines step 6 names, never `cat` or `sed` it whole, and never copy a value out of it. Report the literals as a baseline finding without printing them; rotation is a separate ticket.
- A credential passed as an argument is used nowhere. Never echo it, never write it to a file, and never put it in a commit message or a PR description.

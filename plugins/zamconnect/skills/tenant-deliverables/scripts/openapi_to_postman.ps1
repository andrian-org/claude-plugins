<#
.SYNOPSIS
Converts a tenant's exported swagger.json into a Postman collection, using Postman's own
official openapi-to-postmanv2 converter, and writes it to the repo's existing
"postman collections/<Tenant>.postman_collection.json" convention (43 hand-maintained
collections already live there - this mechanizes that, it does not replace the convention).

.DESCRIPTION
After conversion the collection is reshaped to match the workspace's environment convention:

  * every request is addressed at {{zc_base_url}}, the variable each environment defines
    ("1. TEST - test.gsb.gov.zm" sets it to https://api.test.gsb.gov.zm), so switching
    environment switches the whole collection
  * collection-level Basic auth using {{username}} / {{password}}, inherited by every request
    rather than repeated per request with baked-in credentials
  * tab-indented CRLF formatting matching the hand-maintained collections, applied by
    format_collection.py (PowerShell's own ConvertTo-Json indents by column position)

The gateway route (/t/<tenant>) is NOT applied here - it belongs to the OpenAPI document, so
apply_gateway_route.py writes it once and both this and the DOCX renderer inherit it. This
script warns if it is handed a document that never had that step run.

.PARAMETER Tenant
Tenant name, e.g. "APIS". Used both for the output filename and the collection's info.name
(overriding the converter's raw title, which is Program.cs's OpenApiInfo.Title - the existing
hand-maintained collections are named after the tenant alone).

.PARAMETER SwaggerJson
Path to the exported OpenAPI document, after apply_gateway_route.py has run over it.

.PARAMETER OutputPath
Required. Where to write the collection. This script ships in a plugin rather than in the
target repository, so it cannot infer a repo root from its own location.

.NOTES
Invokes npx via node.exe's own directory rather than a bare "npx" call - on this machine
"npx" is rewritten by a token-optimization shell hook whose "intelligent routing" only
recognizes a handful of tools (tsc, eslint, prisma) and silently mishandles arbitrary
npm packages like openapi-to-postmanv2 (it produced npx's own --version output instead of
running the package). Resolving node.exe's path and calling npx.cmd next to it directly
sidesteps that hook entirely. Requires Node/npx on the machine running this script.
#>
param(
    [Parameter(Mandatory = $true)][string]$Tenant,
    [Parameter(Mandatory = $true)][string]$SwaggerJson,
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

$HostToken = '{{zc_base_url}}'

# The converter may render the server as its own {{baseUrl}} variable or inline the literal URL,
# depending on the shape of the document's `servers`. Both collapse to {{zc_base_url}} here.
$BaseTokens = @(
    '{{baseUrl}}',
    'https://api.test.gsb.gov.zm',
    'https://api.stage.gsb.gov.zm',
    'https://api.gsb.gov.zm'
)

function Set-GatewayHost {
    param($Items, $Tokens, $Replacement)

    foreach ($item in $Items) {
        if ($item.PSObject.Properties.Name -contains 'item') {
            Set-GatewayHost -Items $item.item -Tokens $Tokens -Replacement $Replacement
            continue
        }

        $url = $item.request.url
        if ($null -eq $url) { continue }

        $matched = $false
        foreach ($token in $Tokens) {
            if ($url.raw -and $url.raw.Contains($token)) {
                $url.raw = $url.raw.Replace($token, $Replacement)
                $matched = $true
            }
        }

        # A plain foreach, not ForEach-Object: assigning $matched inside a pipeline scriptblock
        # would create it in that child scope and leave the outer flag false, so a host-only
        # match (the usual case - the converter emits no "raw") would skip the protocol cleanup.
        if ($url.PSObject.Properties.Name -contains 'host') {
            $rewrittenHost = @()
            foreach ($segment in @($url.host)) {
                if ($Tokens -contains $segment) {
                    $rewrittenHost += $Replacement
                    $matched = $true
                }
                else {
                    $rewrittenHost += $segment
                }
            }
            $url.host = $rewrittenHost
        }

        # {{zc_base_url}} already carries its own scheme, so a leftover "protocol" would render
        # as https://{{zc_base_url}}/...
        if ($matched -and $url.PSObject.Properties.Name -contains 'protocol') {
            $url.PSObject.Properties.Remove('protocol')
        }

        # The converter emits host/path but no raw. Postman reconstructs the URL either way, but
        # every hand-maintained collection here carries raw, and it is what a reviewer reads in
        # the diff. Postman joins host segments with "." and path segments with "/".
        $rebuilt = "$($url.host -join '.')/$($url.path -join '/')"
        if ($url.query -and @($url.query).Count -gt 0) {
            $pairs = @($url.query | ForEach-Object { "$($_.key)=$($_.value)" }) -join '&'
            $rebuilt = "${rebuilt}?${pairs}"
        }
        if ($url.PSObject.Properties.Name -contains 'raw') { $url.raw = $rebuilt }
        else { $url | Add-Member -NotePropertyName raw -NotePropertyValue $rebuilt }

        # The converter names a request after the operation's summary, which reads as free text
        # in the sidebar ("Get a person by National Registration Card (NRC) number") and sorts
        # by whatever verb the summary happens to open with. Name it after the operation
        # instead, matching how the endpoints are headed in the DOCX. The summary is not lost -
        # it is already the request's description.
        $operationName = "$($item.request.method) /$($url.path -join '/')"
        if ($item.PSObject.Properties.Name -contains 'name') { $item.name = $operationName }
        if ($item.request.PSObject.Properties.Name -contains 'name') { $item.request.name = $operationName }

        # Every request inherits the collection's Basic auth, so no request should carry its own.
        # The converter emits a null "auth" for document-level security (ambiguous - may be read
        # as an explicit "no auth") and, for a document with per-operation security, a populated
        # one seeded with its own {{basicAuthUsername}}/{{basicAuthPassword}} placeholders that
        # would silently override the collection. Neither is wanted.
        if ($item.request.PSObject.Properties.Name -contains 'auth') {
            $item.request.PSObject.Properties.Remove('auth')
        }
    }
}

$ScriptDir = $PSScriptRoot

# This script lives in a plugin, not in the target repository, so it cannot infer a repo root
# from its own location the way the repo-local copy did. The caller says where the collection
# goes; build_package.py passes the deliverable's Tenant folder.
if (-not $OutputPath) {
    throw "-OutputPath is required: this script ships in a plugin and cannot locate the target repository on its own."
}
# GetUnresolvedProviderPathFromPSPath (not Resolve-Path) since the output file doesn't exist yet.
$OutputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputPath)

$SwaggerJson = (Resolve-Path $SwaggerJson).Path

$spec = Get-Content $SwaggerJson -Raw | ConvertFrom-Json
$specPaths = @($spec.paths.PSObject.Properties.Name)
$unprefixed = @($specPaths | Where-Object { -not $_.StartsWith('/t/') })
if ($unprefixed.Count -gt 0) {
    Write-Warning ("$($unprefixed.Count) of $($specPaths.Count) path(s) do not start with '/t/' " +
        "(e.g. '$($unprefixed[0])'). Run apply_gateway_route.py over the document first, or the " +
        "collection will address the tenant service directly instead of the gateway.")
}

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    throw "node.exe not found on PATH - Postman conversion requires Node/npx."
}
$npxCmd = Join-Path (Split-Path $nodeCmd.Source -Parent) "npx.cmd"
if (-not (Test-Path $npxCmd)) {
    throw "npx.cmd not found next to node.exe at '$npxCmd'."
}

# folderStrategy=Tags groups requests by their OpenAPI tag (.WithTags("PAXLST")). The default,
# Paths, builds one nested folder per URL segment - which since the gateway route moved into the
# document means every request buried under t > apis > ... instead of a flat, readable list.
& $npxCmd --yes -p openapi-to-postmanv2 openapi2postmanv2 -s $SwaggerJson -o $OutputPath -p -O folderStrategy=Tags
if ($LASTEXITCODE -ne 0) {
    throw "openapi2postmanv2 exited with code $LASTEXITCODE"
}

$collection = Get-Content $OutputPath -Raw | ConvertFrom-Json
$collection.info.name = $Tenant

Set-GatewayHost -Items $collection.item -Tokens $BaseTokens -Replacement $HostToken

$auth = [pscustomobject]@{
    type  = 'basic'
    basic = @(
        # "key" is Postman's own Basic-auth field name and is fixed; "value" is the workspace
        # variable the environments define, which happens to share the name.
        [pscustomobject]@{ key = 'username'; value = '{{username}}'; type = 'string' },
        [pscustomobject]@{ key = 'password'; value = '{{password}}'; type = 'string' }
    )
}
$collection | Add-Member -NotePropertyName auth -NotePropertyValue $auth -Force

# The converter's own baseUrl variable is dead once every request points at {{zc_base_url}};
# leaving it in invites someone to edit it and wonder why nothing changed.
if ($collection.PSObject.Properties.Name -contains 'variable') {
    $kept = @($collection.variable | Where-Object { $_.key -ne 'baseUrl' })
    if ($kept.Count -gt 0) { $collection.variable = $kept }
    else { $collection.PSObject.Properties.Remove('variable') }
}

$json = $collection | ConvertTo-Json -Depth 100
# Set-Content -Encoding utf8 always adds a BOM in Windows PowerShell 5.1; none of the existing
# hand-maintained collections have one, so write raw UTF-8 bytes via .NET instead.
[System.IO.File]::WriteAllText($OutputPath, $json, (New-Object System.Text.UTF8Encoding($false)))

# ConvertTo-Json indents by column position, not depth, so a nested collection walks off the
# right of the screen. Re-lay it out as tab-indented CRLF, matching the existing collections.
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd) {
    & $pythonCmd.Source (Join-Path $ScriptDir 'format_collection.py') $OutputPath
    if ($LASTEXITCODE -ne 0) {
        throw "format_collection.py exited with code $LASTEXITCODE"
    }
}
else {
    Write-Warning ("python not found on PATH - collection left in PowerShell's ConvertTo-Json " +
        "layout. Run scripts/format_collection.py over it before committing.")
}

Write-Output "Wrote: $OutputPath"
Write-Output "Host: $HostToken   Auth: basic {{username}}/{{password}}"

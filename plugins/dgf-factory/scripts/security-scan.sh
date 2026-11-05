#!/usr/bin/env bash
# Runs every check of the application security scan and writes one readable report per run.
# Runs on macOS, Linux and WSL. Exits 0 clean, 1 blocked, 2 warnings or a skipped check, 3 usage error.

set -uo pipefail

TRIVY_IMG="aquasec/trivy:0.76.1"
GITLEAKS_IMG="zricethezav/gitleaks:v8.30.1"
SEMGREP_IMG="semgrep/semgrep:1.181.1"
ZAP_IMG="zaproxy/zap-stable:2.17.0"
JQ_IMG="ghcr.io/jqlang/jq:1.7.1"
SKIP_DIRS="**/node_modules,**/bin,**/obj,**/dist,**/build,**/.next,**/.angular,**/packages,**/TestResults,**/security-reports,**/.dgf-factory/security,**/.dgf-factory/runtime/.venv"
MAXROWS=200

usage() {
  cat <<'EOF'
Usage: ./security-scan.sh [options]
  --path DIR          repository to scan (default: current directory)
  --image NAME[,...]  also scan these built container images and write their SBOMs (repeatable)
  --build             build an image from DIR/<dockerfile> first (tag: <folder>:scan) and scan it
  --dockerfile FILE   Dockerfile for --build, relative to DIR (default Dockerfile)
  --url URL           also run an OWASP ZAP baseline scan against this test URL
  --history N         commits of git history to scan for secrets (default 0 = all)
  --severity LIST     severities that fail the run (default HIGH,CRITICAL)
  --out DIR           folder for reports (default DIR/security-reports)
  --skip LIST         comma list of steps to skip: runtime,deps,secrets,config,code,image,dast,sbom
                      (each skipped step is a SKIP row, so the run exits 2)
  -h, --help          show this help and exit 0

.NET and Node.js runtimes are checked to the patch: a runtime is vulnerable when a later patch of the same line
fixed a CVE (for example .NET 10.0.13 after 10.0.14 shipped CVE fixes). Sources: Microsoft .NET release metadata
and the nodejs.org release index.

Writes <out>/<date>_<time>_security-report.md and the raw scanner output to <out>/<date>_<time>_raw/.
A report folder the scan creates gets a .gitignore of *, so its reports are never committed.
The last line is the verdict: CLEAN, WARNINGS or BLOCKED.

Exit codes:
  0  every check that ran passed, and none was skipped
  1  a blocking finding (a FAIL row)
  2  warnings: a WARN row, or a SKIP row (a check that did not run is never a pass)
  3  usage error, or a run that could not start (not a folder, no report folder)
EOF
}
fail() { printf '%s\n' "$2" >&2; exit "$1"; }
# An option that takes a value, given none, is a usage error rather than an unbound variable.
need() { [ $# -ge 2 ] || fail 3 "$1 needs a value (see --help)"; }

REPO="$PWD"; IMAGES=""; BUILD=0; DOCKERFILE="Dockerfile"; URL=""; HISTORY=0; SEVERITY="HIGH,CRITICAL"; REPORTS=""; SKIP=""
while [ $# -gt 0 ]; do
  case "$1" in
    --path) need "$@"; REPO="$2"; shift 2 ;;
    --image) need "$@"; IMAGES="$IMAGES $(echo "$2" | tr ',' ' ')"; shift 2 ;;
    --build) BUILD=1; shift ;;
    --dockerfile) need "$@"; DOCKERFILE="$2"; shift 2 ;;
    --url) need "$@"; URL="$2"; shift 2 ;;
    --history) need "$@"; HISTORY="$2"; shift 2 ;;
    --severity) need "$@"; SEVERITY="$(echo "$2" | tr 'a-z' 'A-Z')"; shift 2 ;;
    --out) need "$@"; REPORTS="$2"; shift 2 ;;
    --skip) need "$@"; SKIP="$(echo "$2" | tr 'A-Z' 'a-z' | tr -d ' ')"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail 3 "unknown option: $1 (see --help)" ;;
  esac
done
case "$HISTORY" in ''|*[!0-9]*) fail 3 "--history takes a number of commits: $HISTORY" ;; esac
# The list reaches scanner command lines, one of them inside `sh -c`: only comma-separated words pass.
[[ "$SEVERITY" =~ ^[A-Z]+(,[A-Z]+)*$ ]] || fail 3 "--severity takes a comma list of severities, such as HIGH,CRITICAL: $SEVERITY"

ABS="$(cd "$REPO" 2>/dev/null && pwd)" || fail 3 "not a folder: $REPO"
REPO="$ABS"
cd "$REPO" || fail 3 "cannot enter: $REPO"
REPORTS="${REPORTS:-$REPO/security-reports}"
NEW_REPORTS=0; [ -d "$REPORTS" ] || NEW_REPORTS=1
{ mkdir -p "$REPORTS" 2>/dev/null && REPORTS="$(cd "$REPORTS" && pwd)"; } || fail 3 "cannot create the report folder: $REPORTS"
# A report folder the scan creates is ignored whole, so no report reaches a commit by accident.
[ "$NEW_REPORTS" = 1 ] && printf '*\n' > "$REPORTS/.gitignore"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
REPORT="$REPORTS/${STAMP}_security-report.md"
RAWREL="${STAMP}_raw"
OUT="$REPORTS/$RAWREL"
REL="$OUT/.work"
mkdir -p "$OUT" "$REL"
ROWS="$OUT/.rows"; DETAILS="$OUT/.details"; TOOLS="$OUT/.tools"; T="$OUT/.table"
: > "$ROWS"; : > "$DETAILS"; : > "$TOOLS"
SEVTEXT="$(echo "$SEVERITY" | sed 's/,/, /g')"
FAILED=0; FAILS=0; WARNS=0; SKIPPED=0; PASSES=0; FAIL_STEPS=" "; STEP=0

has() { command -v "$1" >/dev/null 2>&1; }
skipped() { case ",$SKIP," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }
log() { printf '%s\n' "$*"; }
md() { printf '%s\n' "$@" >> "$DETAILS"; }
row() {
  local shown="$2"; [ "$2" = FAIL ] && shown="**FAIL**"
  printf '| %s | %s | %s |\n' "$1" "$shown" "$3" >> "$ROWS"
  case "$2" in
    FAIL) FAILED=1; FAILS=$((FAILS+1)); FAIL_STEPS="$FAIL_STEPS$STEP " ;;
    WARN) WARNS=$((WARNS+1)) ;;
    SKIP) SKIPPED=$((SKIPPED+1)) ;;
    PASS) PASSES=$((PASSES+1)) ;;
  esac
  case "$2" in PASS|SKIP) md "" "$1: $2, $3." ;; esac
  printf '  %-34s %-5s %s\n' "$1" "$2" "$3"
}
pl() { if [ "$1" = 1 ]; then echo "1 $2"; else echo "$1 ${3:-${2}s}"; fi; }
step_failed() { case "$FAIL_STEPS" in *" $1 "*) return 0 ;; *) return 1 ;; esac; }
section() { STEP="$1"; printf '\n== %s ==\n' "$2"; md "" "## $1. $2" "" "$3"; }
not_run() { md "" "_Not run: $1._"; log "  not run: $1"; }
# A step skipped with --skip is a check that did not run: a SKIP row, never a pass.
skip_step() { row "$1" SKIP "skipped with --skip $2"; }
# Capped so the report stays readable; the raw file keeps every row.
table() {
  local n; n="$(grep -c . "$2" 2>/dev/null)"; n="${n:-0}"
  [ "$n" -gt 0 ] || return 0
  md "" "$1" "$(printf '%s' "$1" | sed -E 's/[^|]+/ --- /g')"
  head -n "$MAXROWS" "$2" >> "$DETAILS"
  [ "$n" -gt "$MAXROWS" ] && md "" "Showing the first $MAXROWS of $n. All of them are in \`$RAWREL/$3\`."
  return 0
}
cell() { printf '%s' "$1" | sed 's/|/\\|/g'; }
clip() { awk -v n="$1" '{ if (length($0) > n) $0 = substr($0, 1, n - 3) "..."; print }'; }
# Lines on stdin, sorted and unique, as "a, b, c, +2 more".
few() { sort -u | awk 'NF { n++; if (n <= 5) s = s (n > 1 ? ", " : "") $0 } END { if (n > 5) s = s ", +" n - 5 " more"; print s }'; }
rel() {
  local p="$1" r; r="$(printf '%s/' "$REPO" | tr 'A-Z' 'a-z')"
  case "$(printf '%s' "$p" | tr 'A-Z' 'a-z')" in "$r"*) p="${p:${#r}}" ;; esac
  printf '%s' "${p#/src/}"
}

# macOS has no timeout command. A stalled advisory feed must end in SKIP, not hang the scan.
with_timeout() {
  local secs="$1" pid watcher rc; shift
  "$@" & pid=$!
  ( sleep "$secs"; pkill -P "$pid" 2>/dev/null; kill "$pid" 2>/dev/null
    sleep 5; pkill -9 -P "$pid" 2>/dev/null; kill -9 "$pid" 2>/dev/null ) & watcher=$!
  wait "$pid"; rc=$?
  pkill -P "$watcher" 2>/dev/null; kill "$watcher" 2>/dev/null; wait "$watcher" 2>/dev/null
  return "$rc"
}

# Docker images are the fallback, so a machine with only Docker can run every check.
# With every step skipped no scanner runs, so the daemon is not asked: such a run needs neither Docker nor the network.
ALL_SKIPPED=1; for s in runtime deps secrets config code image dast sbom; do skipped "$s" || ALL_SKIPPED=0; done
HAVE_DOCKER=0; [ "$ALL_SKIPPED" = 0 ] && has docker && with_timeout 20 docker info >/dev/null 2>&1 && HAVE_DOCKER=1
# Only an image scan needs the Docker socket (to read local images); the other scanners get no access to the daemon.
run_tool() {
  local socket=0 tool img sub sock=""; [ "$1" = --socket ] && { socket=1; shift; }
  tool="$1"; img="$2"; shift 2
  # Trivy stops after 5 minutes by default; a folder mounted into Docker Desktop reads slowly enough to hit that.
  if [ "$tool" = trivy ]; then sub="$1"; shift; set -- "$sub" --timeout 30m "$@"; fi
  if has "$tool"; then echo "$tool|installed|$(command -v "$tool")" >> "$TOOLS"; "$tool" "$@" >> "$OUT/$tool.log" 2>&1
  elif [ "$HAVE_DOCKER" = 1 ]; then
    echo "$tool|Docker|$img" >> "$TOOLS"
    # The Semgrep image has no entrypoint; the others start their tool directly.
    local entry=""; [ "$tool" = semgrep ] && entry=semgrep
    [ "$socket" = 1 ] && sock="-v /var/run/docker.sock:/var/run/docker.sock"
    # The repository is only read: mounted read-only, so no scanner can change it. Reports go to /out.
    # shellcheck disable=SC2086
    docker run --rm -v "$REPO":/src:ro -v "$OUT":/out -w /src $sock -v security-scan-cache:/root/.cache \
      -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
      "$img" $entry "$@" >> "$OUT/$tool.log" 2>&1
  else return 127; fi
}
# The scanner's own reason for producing no report, from its log, for the SKIP row.
tool_error() {
  local l
  [ -f "$OUT/$1.log" ] || { echo "no output"; return; }
  l="$(grep -E '(FATAL|ERROR|error:)' "$OUT/$1.log" | tail -1)"
  [ -n "$l" ] || { echo "see $RAWREL/$1.log"; return; }
  printf '%s\n' "$l" | awk 'match($0, /FATAL|ERROR/) { $0 = substr($0, RSTART + RLENGTH) } { gsub(/[[:space:]]+/, " "); sub(/^ /, ""); print }' | clip 160
}
# Paths inside Docker differ from the host; native runs use the host paths.
p_repo() { if has "$1"; then echo "$REPO"; else echo /src; fi; }
p_out()  { if has "$1"; then echo "$OUT"; else echo /out; fi; }
available() { has "$1" || [ "$HAVE_DOCKER" = 1 ]; }
has_jq() { available jq; }
jqx() { if has jq; then jq "$@"; elif [ "$HAVE_DOCKER" = 1 ]; then docker run --rm -i "$JQ_IMG" "$@"; else return 127; fi; }

JQDEF='def cell: tostring | gsub("<[^>]*>"; "") | gsub("\\s+"; " ") | gsub("^ | $"; "") | gsub("\\|"; "\\|");
def clip($n): if length > $n then .[0:$n - 3] + "..." else . end;
def rank: ascii_upcase | {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "MODERATE": 2, "LOW": 3, "INFORMATIONAL": 4}[.] // 5;
def blocking($s): ascii_upcase | (if . == "MODERATE" then "MEDIUM" else . end) as $v | ($s | split(",") | index($v)) != null;
def link($id; $url): if ($url // "") == "" then $id else "[\($id)](\($url))" end;
def rel($r): (if ascii_downcase | startswith(($r + "/") | ascii_downcase) then .[($r | length) + 1:] else . end) | ltrimstr("/src/");
def few: (.[0:5] | join(", ")) + (if length > 5 then ", +\(length - 5) more" else "" end);
def pl($n; $w): if $n == 1 then "1 \($w)" else "\($n) \($w)s" end;
def ver: [(capture("^(?<v>[0-9]+(\\.[0-9]+){1,3})").v // "") | split(".")[] | tonumber];'
q() { local file="$1" prog="$2"; shift 2; [ -s "$file" ] || return 1; jqx -r --arg s "$SEVERITY" --arg r "$REPO" "$@" "$JQDEF $prog" < "$file" 2>/dev/null; }
# The same as q, over several JSON files read as one array.
qall() { local prog="$1"; shift; cat "$@" 2>/dev/null | jqx -r -s --arg s "$SEVERITY" --arg r "$REPO" "$JQDEF $prog" 2>/dev/null; }

# Projects dotnet could not restore are still listed, with an error under "problems": they were not audited, they are not clean.
NUGET_OK='([.problems[]? | select(.level == "error") | .project]) as $b | .projects[]? | select(.path as $p | any($b[]; . == $p) | not)'
NUGET_LIST="[.[] | $NUGET_OK"'
  | (.path | rel($r)) as $proj | .frameworks[]?
  | (.topLevelPackages[]? | . + {t: "direct"}), (.transitivePackages[]? | . + {t: "transitive"})
  | . as $p | .vulnerabilities[]? | select(.severity | blocking($s))
  | {sev: (.severity | ascii_upcase), id: $p.id, ver: $p.resolvedVersion, url: .advisoryurl, t: $p.t, proj: $proj}]
  | group_by([.id, .ver, .url]) | map(.[0] + {t: (map(.t) | unique | join(", ")), p: (map(.proj) | unique | few)})
  | sort_by((.sev | rank), .id)'
NPM_LIST='[(.vulnerabilities // {})[] | select(.severity | blocking($s))] | sort_by((.severity | rank), .name)'
TRIVY_VULNS='[.Results[]? | .Target as $t | .Vulnerabilities[]?
  | {sev: .Severity, pkg: .PkgName, ver: .InstalledVersion, fix: (.FixedVersion // ""), id: .VulnerabilityID, url: (.PrimaryURL // ""), title: (.Title // ""), t: $t}]
  | group_by([.id, .pkg, .ver]) | map(.[0] + {t: (map(.t) | unique)}) | sort_by((.sev | rank), .pkg)'
TRIVY_VULN_ROW='.[] | "| \(.sev) | \(.pkg | cell) | \(.ver | cell) | \(if .fix == "" then "no fix yet" else (.fix | cell) end) | \(link(.id; .url)) \(.title | cell | clip(70)) | \(.t[0] | cell)\(if (.t | length) > 1 then " +\((.t | length) - 1) more" else "" end) |"'
TRIVY_VULN_HEAD="| Severity | Package | Installed | Fixed in | Issue | Found in |"
TRIVY_CFG='[.Results[]? | .Target as $t | .Misconfigurations[]? | select(.Status == "FAIL")
  | {sev: .Severity, id: (.ID // .AVDID), title: (.Title // ""), fix: (.Resolution // ""), url: (.PrimaryURL // ""),
     where: ($t + (if (.CauseMetadata.StartLine // 0) > 0 then ":\(.CauseMetadata.StartLine)" else "" end))}]
  | sort_by((.sev | rank), .where)'
LEAKS='map({rule: .RuleID, file: (.File | rel($r)), line: .StartLine, commit: ((.Commit // "")[0:8]), date: ((.Date // "")[0:10])}) | sort_by(.file, .line)'
LEAK_RULES='group_by(.RuleID) | map({r: .[0].RuleID, n: length}) | sort_by(-.n) | map("\(.r) (\(.n))") | join(", ")'
SEMGREP_LIST='[.results[]? | {sev: (.extra.severity | ascii_upcase | {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW"}[.] // .),
  rule: (.check_id | split(".") | last), file: (.path | rel($r)), line: .start.line, msg: (.extra.message // "")}] | sort_by((.sev | rank), .file, .line)'
ZAP_LIST='[.site[]? | .alerts[]? | {risk: (.riskdesc | split(" ")[0]), name: .name, n: (.count // ""), uri: (.instances[0].uri // ""), fix: (.solution // "")}]
  | sort_by((.risk | rank), .name)'
# The first document is Trivy's SBOM; the rest are dotnet's package lists, whose packages Trivy cannot see.
SBOM_MERGE='.[0] as $sb | [$sb.components[]? | select(.)] as $c | [$c[] | .purl // empty] as $have
  | [.[1:][] | .projects[]? | .frameworks[]? | (.topLevelPackages[]?, .transitivePackages[]?) | select(.resolvedVersion) | {id, v: .resolvedVersion}]
  | unique | map("pkg:nuget/\(.id)@\(.v)" as $p | select(any($have[]; . == $p) | not) | {"bom-ref": $p, type: "library", name: .id, version: .v, purl: $p})
  | $sb + {components: ($c + .)}'

# ---- Runtime patch levels ---------------------------------------------------------------------------------------------
# A runtime is safe only when no later patch of its line is a security release. Each verdict is one line,
# state<TAB>note<TAB>latest: state ok | vulnerable | eol | unknown, a note for the report, the latest patch of the line.
DOTNET_VERDICT='def rv($k): (if $k == "aspnet" then .["aspnetcore-runtime"].version else .runtime.version end) // "" | tostring;
.releases as $rels
| (if $kind == "sdk" then [$rels[] | select(any(.sdks[]?; .version == $v))][0] else null end) as $sr
| if $kind == "sdk" and $sr == null then "unknown\tSDK \($v) is not in the .NET release list\t-"
  else (if $kind == "sdk" then "runtime" else $kind end) as $k
  | (if $kind == "sdk" then ($sr | rv("runtime")) else $v end) as $ver
  | (if $kind == "sdk" then "SDK bundles runtime \($ver); " else "" end) as $via
  | ($rels[0] | rv($k)) as $latest
  | if $phase == "eol" then "eol\t\($via).NET \($chan) ended \($eol[0:10]), no more security fixes\t\($latest)"
    elif ($ver | test("-")) then "vulnerable\t\($via)preview build, not supported in production\t\($latest)"
    else [$rels[] | select(.security == true and (rv($k) | test("-") | not) and ((rv($k) | ver) > ($ver | ver)))] as $newer
    | if ($newer | length) > 0 then
        [$newer[] | .["cve-list"][]? | .["cve-id"] | select(.)] as $cves
        | (if ($cves | length) > 0 then "\(pl($cves | unique | length; "CVE")) fixed in later patches (\($cves | unique | few))"
           else pl($newer | length; "later security release") end) as $what
        | "vulnerable\t\($via)vulnerable: \($what); upgrade to \($newer[0] | rv($k)) or newer\t\($latest)"
      else "ok\t\($via)has every published security fix\(if ($ver | ver) < ($latest | ver) then " (\($latest) is out without security fixes)" else "" end)\t\($latest)"
      end
    end
  end'
NODE_VERDICT='($v | ver) as $cv
| [.[] | select(.version | startswith("v\($cv[0])."))] as $line
| (if ($line | length) > 0 then $line[0].version | ltrimstr("v") else "-" end) as $latest
| [$line[] | select(.security and ((.version | ltrimstr("v") | ver) > $cv))] as $newer
| if ($newer | length) > 0 then "vulnerable\tvulnerable: \(pl($newer | length; "later security release")); upgrade to \($newer[0].version | ltrimstr("v")) or newer\t\($latest)"
  elif $estate == "unknown" then "unknown\tpatch has every security fix, but \($enote)\t\($latest)"
  else "ok\t\($enote), has every published security fix\t\($latest)" end'

verdict() { printf '%s\t%s\t%s\n' "$1" "$2" "$3"; }
fetch() { [ -s "$2" ] || curl -fsS --max-time 60 --retry 2 -o "$2" "$1" 2>/dev/null; [ -s "$2" ]; }
eol_info() { # product cycle
  local body code out
  body="$(curl -sS --max-time 15 --retry 2 -w '\n%{http_code}' "https://endoflife.date/api/$1/$2.json" 2>/dev/null)"
  code="$(printf '%s' "$body" | tail -n 1)"
  if [ "$code" = 404 ]; then verdict unknown "not listed on endoflife.date" -; return; fi
  out="$(printf '%s' "$body" | sed '$d' | jqx -r --arg today "$(date +%Y-%m-%d)" '(.latest // "-" | tostring) as $l
    | if .eol == true then "eol\tend of life\t\($l)"
      elif .eol == false then "ok\tsupported, no end date announced\t\($l)"
      elif (.eol | type) == "string" then (if .eol[0:10] > $today then "ok\tsupported until \(.eol[0:10])\t\($l)" else "eol\tended \(.eol[0:10])\t\($l)" end)
      else error end' 2>/dev/null)"
  if [ -n "$out" ]; then printf '%s\n' "$out"; else verdict unknown "could not reach endoflife.date" -; fi
}
dotnet_channel() { # channel: sets DN_FILE, DN_PHASE and DN_EOL, fails when Microsoft has no release data for it
  local url=""
  DN_FILE=""; DN_PHASE=""; DN_EOL=""
  fetch https://builds.dotnet.microsoft.com/dotnet/release-metadata/releases-index.json "$REL/dotnet-index.json" || return 1
  IFS=$'\t' read -r url DN_PHASE DN_EOL <<EOF
$(q "$REL/dotnet-index.json" '.["releases-index"][] | select(.["channel-version"] == $c) | "\(.["releases.json"])\t\(.["support-phase"])\t\(.["eol-date"] // "")"' --arg c "$1")
EOF
  [ -n "$url" ] || return 1
  DN_FILE="$REL/dotnet-$1.json"
  fetch "$url" "$DN_FILE"
}
# kind: runtime (Microsoft.NETCore.App), aspnet (Microsoft.AspNetCore.App) or sdk (checked by the runtime it bundles).
dotnet_verdict() { # kind version
  local ch; ch="$(printf '%s' "$2" | grep -oE '^[0-9]+\.[0-9]+')"
  [ -n "$ch" ] || { verdict unknown "cannot read the version" -; return; }
  dotnet_channel "$ch" || { verdict unknown "no .NET release data for $ch" -; return; }
  q "$DN_FILE" "$DOTNET_VERDICT" --arg kind "$1" --arg v "$2" --arg chan "$ch" --arg phase "$DN_PHASE" --arg eol "$DN_EOL" \
    || verdict unknown "could not read the .NET release list" -
}
node_verdict() { # version
  local v="${1#v}" e st note latest
  printf '%s' "$v" | grep -qE '^[0-9]+\.[0-9]+' || { verdict unknown "cannot read the version" -; return; }
  e="$(eol_info nodejs "${v%%.*}")"
  IFS=$'\t' read -r st note latest <<EOF
$e
EOF
  [ "$st" = eol ] && { printf '%s\n' "$e"; return; }
  fetch https://nodejs.org/dist/index.json "$REL/node-index.json" \
    || { verdict unknown "$note; could not reach nodejs.org to check the patch" "$latest"; return; }
  q "$REL/node-index.json" "$NODE_VERDICT" --arg v "$v" --arg estate "$st" --arg enote "$note" \
    || verdict unknown "$note; could not read the nodejs.org release list" "$latest"
}
# .NET and Node.js runtimes inside an image, as name<TAB>version<TAB>kind: the shared framework folders,
# or the version variables of the official base images when the image has no shell.
image_runtimes() { # image
  local found
  # The image is the user's to name, and anything: it runs with no network, no capabilities and no privilege gain.
  found="$(docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges --entrypoint sh "$1" -c 'ls -d /usr/share/dotnet/shared/*/* /usr/lib/dotnet/shared/*/* 2>/dev/null; node --version 2>/dev/null' 2>/dev/null </dev/null \
    | awk '{ sub(/\r$/, ""); n = split($0, a, "/") }
      n > 2 && a[n - 2] == "shared" && a[n - 1] ~ /^Microsoft\.(NETCore|AspNetCore)\.App$/ { print a[n - 1] "\t" a[n] "\t" (a[n - 1] ~ /AspNetCore/ ? "aspnet" : "runtime"); next }
      /^v[0-9]+\.[0-9]+\.[0-9]+/ { v = substr($0, 2); sub(/[^0-9.].*/, "", v); print "Node.js\t" v "\tnode" }')"
  [ -n "$found" ] || found="$(docker image inspect "$1" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
    | awk '{ v = substr($0, index($0, "=") + 1) }
      /^ASPNET(CORE)?_VERSION=/ { print "Microsoft.AspNetCore.App\t" v "\taspnet"; next }
      /^DOTNET_VERSION=/ { print "Microsoft.NETCore.App\t" v "\truntime"; next }
      /^NODE_VERSION=/ { print "Node.js\t" v "\tnode" }')"
  printf '%s' "$found"
}

log "Scanning $REPO"
START=$(date +%s)

LOCKS="$(git ls-files '*package-lock.json' '*yarn.lock' '*pnpm-lock.yaml' 2>/dev/null || find . -name node_modules -prune -o \( -name package-lock.json -o -name yarn.lock -o -name pnpm-lock.yaml \) -print)"
PKGJSONS="$(git ls-files '*package.json' 2>/dev/null | grep -v node_modules || true)"
HAS_CS=0; [ -n "$(git ls-files '*.cs' 2>/dev/null | head -1)" ] && HAS_CS=1
HAS_REACT=0; HAS_NEXT=0
for p in $PKGJSONS; do
  grep -qE '"react"[[:space:]]*:' "$p" && HAS_REACT=1
  grep -qE '"next"[[:space:]]*:' "$p" && HAS_NEXT=1
done

section 1 "Runtime and framework versions" "Every .NET, .NET Framework, Node.js, Angular, React and Next.js version the application uses must still receive security fixes, and every .NET and Node.js runtime must be on a patch that has all of them: a runtime is vulnerable when a later patch of its line fixed a CVE. What ships (pinned versions, images) fails; this machine's runtimes only warn. Sources: Microsoft .NET release metadata, nodejs.org, endoflife.date."
if skipped runtime; then skip_step "Runtime and framework" runtime
elif ! has curl || ! has_jq; then row "Runtime and framework" SKIP "needs curl, and jq or Docker"
else
  : > "$T"; RT_FAIL=""; RT_WARN=""; RT_N=0
  rt_add() { # name version where shipped(1|0) verdict
    local st note latest res=PASS label
    IFS=$'\t' read -r st note latest <<EOF
$5
EOF
    [ -n "$st" ] || { st=unknown; note="could not be checked"; latest=-; }
    label="$1${2:+ $2}"
    if [ "$st" = unknown ]; then res=WARN; RT_WARN="$RT_WARN$label"$'\n'
    elif [ "$st" != ok ]; then
      if [ "$4" = 1 ]; then res="**FAIL**"; RT_FAIL="$RT_FAIL$label"$'\n'; else res=WARN; RT_WARN="$RT_WARN$label"$'\n'; fi
    fi
    RT_N=$((RT_N+1))
    printf '| %s | %s | %s | %s | %s | %s |\n' "$1" "$2" "$3" "$(cell "$note")" "${latest:--}" "$res" >> "$T"
    printf '    %-44s %s\n' "$label" "$note"
  }
  PROJ="$(git ls-files '*.csproj' '*.fsproj' '*.vbproj' '*.props' 2>/dev/null)"
  # target<TAB>project file, once per pair; .NET Framework's TargetFrameworkVersion v4.8 becomes fx4.8.
  TFS="$(for f in $PROJ; do
      { grep -oE '<TargetFrameworks?>[^<]+' "$f" | sed -E 's/^<[^>]+>//' | tr ';' '\n'
        grep -oE '<TargetFrameworkVersion>v[0-9.]+<' "$f" | sed -E 's/^.*>v([0-9.]+)<$/fx\1/'; } 2>/dev/null \
        | tr -d ' \t\r' | awk -v f="$f" 'NF { print $0 "\t" f }'
    done | sort -u)"
  # .NET lines the projects target; the runtimes of these lines are checked to the patch below.
  CHANS=" "
  for tf in $(printf '%s\n' "$TFS" | cut -f1 | sort -u); do
    nf="$(pl "$(printf '%s\n' "$TFS" | awk -F'\t' -v t="$tf" '$1 == t' | wc -l | tr -d ' ')" "project file")"
    if [[ "$tf" =~ ^net(coreapp)?([0-9]+\.[0-9]+) ]]; then
      ch="${BASH_REMATCH[2]}"
      case "$CHANS" in *" $ch "*) ;; *) CHANS="$CHANS$ch " ;; esac
      if ! dotnet_channel "$ch"; then rt_add "Target $tf" "" "$nf" 1 "$(verdict unknown "no .NET release data for $ch" -)"
      else
        latest="$(q "$DN_FILE" '.releases[0].runtime.version // "-"')"
        if [ "$DN_PHASE" = eol ]; then rt_add "Target $tf" "" "$nf" 1 "$(verdict eol ".NET $ch ended ${DN_EOL:0:10}" "$latest")"
        else rt_add "Target $tf" "" "$nf" 1 "$(verdict ok "line supported until ${DN_EOL:0:10}; the runtime patch is checked in the rows below" "$latest")"; fi
      fi
    elif [[ "$tf" =~ ^net4([0-9])([0-9]?)$ ]]; then
      v="4.${BASH_REMATCH[1]}${BASH_REMATCH[2]:+.${BASH_REMATCH[2]}}"
      rt_add "Target .NET Framework" "$v" "$nf" 1 "$(eol_info dotnetfx "$v")"
    elif [[ "$tf" =~ ^fx(.+)$ ]]; then
      v="${BASH_REMATCH[1]}"; rt_add "Target .NET Framework" "$v" "$nf" 1 "$(eol_info dotnetfx "$v")"
    fi
  done
  for f in $PROJ; do
    for v in $(grep -oE '<RuntimeFrameworkVersion>[^<$]+<' "$f" 2>/dev/null | sed -E 's/^<[^>]+>//; s/<$//' | tr -d ' \t\r'); do
      rt_add "RuntimeFrameworkVersion" "$v" "$f" 1 "$(dotnet_verdict runtime "$v")"
    done
  done
  if [ -f global.json ]; then
    v="$(jqx -r '.sdk.version // empty' < global.json 2>/dev/null)"
    [ -n "$v" ] && rt_add ".NET SDK pinned" "$v" "global.json" 0 "$(dotnet_verdict sdk "$v")"
  fi

  # Base images in the Dockerfiles. A pinned tag is what ships; a floating tag (10.0, latest) takes the newest
  # patch at build time, so only a local copy that a local build would reuse can be checked here.
  FLOATING=""; FOREIGN=""
  for df in $(git ls-files '*Dockerfile*' '*.dockerfile' 2>/dev/null | awk -F/ 'tolower($NF) ~ /^dockerfile|\.dockerfile$/'); do
    for ref in $(awk '{ sub(/\r$/, "") } toupper($1) == "FROM" { i = 2; while ($i ~ /^--/) i++; ref = $i
        if (toupper($(i + 1)) == "AS" && $(i + 2) != "") st[tolower($(i + 2))] = 1
        if (ref != "" && !(tolower(ref) in st) && ref !~ /\$/) print ref }' "$df"); do
      if [[ "$ref" =~ ^mcr\.microsoft\.com/dotnet/(aspnet|runtime|sdk)(:([^@[:space:]]+))? ]]; then
        kind="${BASH_REMATCH[1]}"; tag="${BASH_REMATCH[3]:-latest}"
        shipped=1; [ "$kind" = sdk ] && shipped=0
        if [[ "$tag" =~ ^([0-9]+\.[0-9]+\.[0-9]+) ]]; then
          v="${BASH_REMATCH[1]}"; rt_add "Base image $kind" "$v" "$df" "$shipped" "$(dotnet_verdict "$kind" "$v")"; continue
        fi
        local_v=""
        if [ "$HAVE_DOCKER" = 1 ]; then
          case "$kind" in aspnet) envn=ASPNET_VERSION ;; runtime) envn=DOTNET_VERSION ;; *) envn=DOTNET_SDK_VERSION ;; esac
          local_v="$(docker image inspect "$ref" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | sed -n "s/^$envn=//p" | tail -1)"
        fi
        if [ -n "$local_v" ]; then
          d="$(dotnet_verdict "$kind" "$local_v")"
          case "$d" in ok$'\t'*) ;; *) d="$(printf '%s\n' "$d" | R="$ref" awk -F'\t' -v OFS='\t' '{ $2 = "local copy of the floating tag is old, run docker pull " ENVIRON["R"] ": " $2; print }')" ;; esac
          rt_add "Base image $kind (local copy)" "$local_v" "$df, $ref" 0 "$d"
        else FLOATING="$FLOATING\`$ref\` in $df"$'\n'; fi
      elif [[ "$ref" =~ ^(docker\.io/)?(library/)?node:([0-9]+\.[0-9]+\.[0-9]+) ]]; then
        v="${BASH_REMATCH[3]}"; rt_add "Base image node" "$v" "$df" 1 "$(node_verdict "$v")"
      elif [[ "$ref" =~ ^(docker\.io/)?(library/)?node(:|$) ]]; then FLOATING="$FLOATING\`$ref\` in $df"$'\n'
      else FOREIGN="$FOREIGN\`$ref\` in $df"$'\n'; fi
    done
  done

  # This machine builds and tests; its runtimes do not ship, so they warn rather than fail.
  NOLOCAL=""
  if has dotnet && [ "$CHANS" != " " ]; then
    BEST="$(dotnet --list-runtimes 2>/dev/null | awk -v chans="$CHANS" '
      function newer(a, b,  x, y, i, n) { n = split(a, x, "."); split(b, y, "."); for (i = 1; i <= n; i++) if (x[i] + 0 != y[i] + 0) return x[i] + 0 > y[i] + 0; return 0 }
      $1 ~ /^Microsoft\.(NETCore|AspNetCore)\.App$/ && $2 !~ /-/ { split($2, p, "."); ch = p[1] "." p[2]; k = $1 " " ch
        if (index(chans, " " ch " ") && (!(k in best) || newer($2, best[k]))) best[k] = $2 }
      END { for (k in best) print k, best[k] }' | sort)"
    while read -r n ch v; do
      [ -n "$n" ] || continue
      kind=runtime; case "$n" in *AspNetCore*) kind=aspnet ;; esac
      rt_add "$n" "$v" "this machine (build and tests)" 0 "$(dotnet_verdict "$kind" "$v")"
    done <<EOF
$BEST
EOF
    for ch in $CHANS; do printf '%s\n' "$BEST" | awk -v c="$ch" '$2 == c' | grep -q . || NOLOCAL="$NOLOCAL$ch"$'\n'; done
    NOLOCAL="$(printf '%s' "$NOLOCAL" | sort | paste -sd, - | sed 's/,/, /g')"
  fi
  if has node && [ -n "$PKGJSONS" ]; then nv="$(node --version | tr -d v)"; rt_add "Node.js" "$nv" "this machine (build)" 0 "$(node_verdict "$nv")"; fi
  for p in $PKGJSONS; do
    for pair in "@angular/core:angular" "react:react" "next:nextjs"; do
      dep="${pair%%:*}"; prod="${pair##*:}"
      v="$(jqx -r --arg d "$dep" '(.dependencies // {})[$d] // (.devDependencies // {})[$d] // empty' < "$p" 2>/dev/null | grep -oE '[0-9]+(\.[0-9]+)*' | head -1)"
      [ -n "$v" ] && rt_add "$dep" "$v" "$p" 1 "$(eol_info "$prod" "${v%%.*}")"
    done
  done
  table "| Component | Version | Used in | Status | Latest patch | Result |" "$T" ""
  if [ -n "$NOLOCAL" ]; then
    log "    No .NET $NOLOCAL runtime on this machine: it cannot build or restore this code, so the NuGet audit cannot run here"
    md "" "This machine has no .NET $NOLOCAL runtime, so it cannot build or restore this code and section 2 cannot audit NuGet packages. Install the .NET $NOLOCAL SDK."
  fi
  [ -n "$FLOATING" ] && md "" "Floating base-image tags, which take the newest patch when the image is built with \`--pull\`: $(printf '%s' "$FLOATING" | few). What actually ships is only visible in the built image: scan it with \`--image\`."
  [ -n "$FOREIGN" ] && md "" "Other base images: $(printf '%s' "$FOREIGN" | few). Their runtime is only visible in the built image: scan it with \`--image\`."
  if [ "$RT_N" = 0 ]; then md "" "No .NET, Node.js, Angular, React or Next.js versions were found."
  elif [ -n "$RT_FAIL" ]; then row "Runtime and framework" FAIL "vulnerable or end-of-life: $(printf '%s' "$RT_FAIL" | few)"
  elif [ -n "$RT_WARN" ]; then row "Runtime and framework" WARN "to check: $(printf '%s' "$RT_WARN" | few)"
  else row "Runtime and framework" PASS "$(pl "$RT_N" version), all supported and patched"; fi
  latest="$(q "$REL/dotnet-index.json" '[.["releases-index"][] | select(.["support-phase"] == "active" or .["support-phase"] == "maintenance") | "\(.["channel-version"]) \(.["latest-runtime"])"] | join(", ")')"
  [ -n "$latest" ] && md "" "Latest supported .NET runtimes today: $latest. Servers and images must run these patch versions or newer."
  [ -n "$RT_FAIL$RT_WARN" ] && md "" "**How to fix:** install the patch named in the Status column (servers: the Hosting Bundle or runtime installer; images: rebuild with \`docker build --pull\`). An end-of-life version gets no more security fixes: plan the upgrade to a supported line."
fi

section 2 "Dependencies" "The NuGet and npm packages the application ships, checked against published advisories. Only production npm dependencies count, because dev tools are not shipped. Showing severities: $SEVTEXT."
if skipped deps; then skip_step "Dependencies" deps
else
  DEPS_CHECKED=0
  TARGETS="$(git ls-files '*.sln' '*.slnx' 2>/dev/null)"; VIA_SLN=1
  if [ -z "$TARGETS" ]; then
    VIA_SLN=0; TARGETS="$(git ls-files '*.csproj' '*.fsproj' '*.vbproj' 2>/dev/null | xargs grep -l 'PackageReference' 2>/dev/null)"
  fi
  if [ -n "$TARGETS" ]; then
    if ! has dotnet; then row "NuGet packages" SKIP "dotnet SDK not installed"
    elif ! has_jq; then row "NuGet packages" SKIP "needs jq or Docker to read the dotnet output"
    else
      echo "dotnet|installed|SDK $(dotnet --version 2>/dev/null)" >> "$TOOLS"
      NUGET_N=0; RESULTS=""; BAD=""
      nuget_audit() { # target: sets NA_OK, NA_WHY and NA_BROKEN, and adds a usable report to RESULTS
        local f rerr rc
        NUGET_N=$((NUGET_N+1)); f="$OUT/nuget-$NUGET_N.json"
        NA_OK=0; NA_WHY=""; NA_BROKEN=""
        with_timeout 900 dotnet restore "$1" > "$REL/restore.log" 2>&1
        # The first restore error says why a project could not be read (an SDK older than its target framework, a feed that needs credentials).
        rerr="$(grep -m1 ': error ' "$REL/restore.log")"
        with_timeout 300 dotnet list "$1" package --vulnerable --include-transitive --format json > "$f" 2> "$REL/list.err"; rc=$?
        if [ "$(q "$f" 'has("projects")')" != true ]; then
          if [ "$rc" -ge 128 ]; then NA_WHY="no answer from the NuGet advisory feed within 5 minutes"
          else NA_WHY="$(cat "$f" "$REL/list.err" 2>/dev/null | grep -m1 -i 'error' | sed -E 's/^error:[[:space:]]*//' | tr -s ' \t' '  ' | clip 160)"; fi
          return
        fi
        NA_BROKEN="$(q "$f" '[.problems[]? | select(.level == "error") | .project] | unique | .[]')"
        if [ -n "$NA_BROKEN" ]; then
          NA_WHY="${rerr:-$(q "$f" '[.problems[]? | select(.level == "error") | .text][0] // ""')}"
          NA_WHY="$(printf '%s' "${NA_WHY#*: error }" | sed -E 's/[[:space:]]*\[[^]]+\][[:space:]]*$//' | tr -s ' \t' '  ' | clip 160)"
          if [ "$(q "$f" "[$NUGET_OK] | length")" = 0 ]; then NA_BROKEN=""; return; fi
        fi
        # Every resolved package, for the SBOM in section 8.
        with_timeout 300 dotnet list "$1" package --include-transitive --format json > "$REL/nuget-all-$NUGET_N.json" 2>/dev/null
        [ "$(q "$REL/nuget-all-$NUGET_N.json" 'has("projects")')" = true ] || rm -f "$REL/nuget-all-$NUGET_N.json"
        NA_OK=1; RESULTS="$RESULTS $f"
      }
      nuget_audit_all() { # targets, one per line
        local t b
        while IFS= read -r t; do
          [ -n "$t" ] || continue
          nuget_audit "$t" < /dev/null
          [ "$NA_OK" = 1 ] || BAD="$BAD$t"$'\t'"$NA_WHY"$'\n'
          while IFS= read -r b; do [ -n "$b" ] && BAD="$BAD$(rel "$b")"$'\t'"$NA_WHY"$'\n'; done <<EOF2
$NA_BROKEN
EOF2
        done <<EOF
$1
EOF
      }
      nuget_audit_all "$TARGETS"
      # dotnet cannot load every project type in a solution (an SSDT .sqlproj, for one); then audit the projects one by one.
      if [ "$VIA_SLN" = 1 ] && [ -n "$BAD" ]; then
        md "" "dotnet could not read $(printf '%s' "$BAD" | cut -f1 | few) as a whole ($(cell "$(printf '%s' "$BAD" | head -1 | cut -f2)")), so each project file was audited on its own."
        DONE="$(for f in $RESULTS; do q "$f" "$NUGET_OK"' | .path | rel($r)'; done)"
        BAD=""
        nuget_audit_all "$(git ls-files '*.csproj' '*.fsproj' '*.vbproj' 2>/dev/null | while IFS= read -r p; do
          printf '%s\n' "$DONE" | grep -qxF "$p" || printf '%s\n' "$p"; done)"
      fi
      if [ -n "$RESULTS" ]; then
        DEPS_CHECKED=$((DEPS_CHECKED+1))
        # shellcheck disable=SC2086
        NPROJ="$(qall "[.[] | $NUGET_OK] | length" $RESULTS)"
        # shellcheck disable=SC2086
        qall "$NUGET_LIST"' | .[] | "| \(.sev) | \(.id) | \(.ver) | \(.t) | \(.p | cell) | \(link(.url | split("/") | last; .url)) |"' $RESULTS > "$T"
        n="$(grep -c . "$T")"
        if [ "$n" -gt 0 ]; then
          # shellcheck disable=SC2086
          row "NuGet packages" FAIL "$(pl "$n" advisory advisories) in $(pl "${NPROJ:-0}" project): $(qall "$NUGET_LIST"' | map("\(.id) \(.ver)") | unique | few' $RESULTS)"
          md "" "### NuGet"
          table "| Severity | Package | Installed | Used as | Projects | Advisory |" "$T" "nuget-*.json"
          md "" "**How to fix:** for a direct package, raise its version in the project file or Directory.Packages.props. For a transitive one, upgrade the package that pulls it in, or add a direct reference to a fixed version."
        else row "NuGet packages" PASS "no advisories at $SEVTEXT in $(pl "${NPROJ:-0}" project)"; fi
      fi
      # Projects fail for different reasons; name each reason once with the projects it stopped.
      if [ -n "$BAD" ]; then
        detail=""
        while IFS= read -r w; do
          detail="${detail:+$detail; }$(printf '%s' "$BAD" | W="$w" awk -F'\t' '$2 == ENVIRON["W"] { print $1 }' | few): $(cell "$w")"
        done <<EOF
$(printf '%s' "$BAD" | cut -f2 | sort | uniq -c | sort -rn | sed -E 's/^ *[0-9]+ //')
EOF
        row "NuGet, not audited" SKIP "$detail"
      fi
    fi
  fi
  if git ls-files '*packages.config' 2>/dev/null | grep -q .; then md "" "packages.config projects: dotnet cannot audit them, so the Trivy table below covers them."; fi
  for l in $LOCKS; do
    case "$l" in
      *package-lock.json)
        if ! has npm; then row "npm $l" SKIP "npm not installed; Trivy below still reads it"; continue; fi
        echo "npm|installed|$(npm --version 2>/dev/null)" >> "$TOOLS"
        d="$(dirname "$l")"; f="npm-$(echo "$d" | tr '/.' '__').json"
        (cd "$d" && with_timeout 180 npm audit --omit=dev --package-lock-only --json > "$OUT/$f" 2>/dev/null); rc=$?
        if [ "$(q "$OUT/$f" 'has("vulnerabilities")')" != true ]; then
          if [ "$rc" -ge 128 ]; then why="no answer within 3 minutes"; else why="$(q "$OUT/$f" '.error.summary // "no output"' | head -1)"; fi
          row "npm $l" SKIP "npm audit did not run: ${why:-no output}"; continue
        fi
        DEPS_CHECKED=$((DEPS_CHECKED+1))
        q "$OUT/$f" "$NPM_LIST"' | .[] | "| \(.severity | ascii_upcase) | \(.name) | \(.range | cell) | \(if .isDirect then "direct" else "transitive" end) | \(.fixAvailable | if . == true then "`npm audit fix`" elif (. == false or . == null) then "no fix yet" else "\(.name)@\(.version)\(if .isSemVerMajor then " (major upgrade)" else "" end)" end) | \(.via as $via | [$via[] | objects | link(.url | split("/") | last; .url)] | unique | if length == 0 then "via " + ([$via[] | strings] | unique | join(", ")) else (.[0:3] | join(", ")) + (if length > 3 then ", +\(length - 3) more" else "" end) end) |"' > "$T"
        n="$(grep -c . "$T")"
        if [ "$n" -gt 0 ]; then row "npm $l" FAIL "$(pl "$n" package): $(q "$OUT/$f" "$NPM_LIST"' | map(.name) | few')"
        else row "npm $l" PASS "shipped dependencies clean at $SEVTEXT"; fi
        if [ "$n" -gt 0 ]; then
          md "" "### npm: $l"
          table "| Severity | Package | Vulnerable versions | Used as | Fix | Advisory |" "$T" "$f"
          md "" "**How to fix:** run \`npm audit fix\` in \`$d\` for the safe upgrades, or upgrade the package in the Fix column. A major upgrade needs testing; a package with no fix needs an exception with a review date."
        fi ;;
      *) md "" "$l: no native audit for this lock file, so the Trivy table below covers it." ;;
    esac
  done
  if available trivy && has_jq; then
    rm -f "$OUT/trivy-deps.json"
    run_tool trivy "$TRIVY_IMG" fs --quiet --scanners vuln --severity "$SEVERITY" --skip-dirs "$SKIP_DIRS" \
      --format json --output "$(p_out trivy)/trivy-deps.json" "$(p_repo trivy)"
    if [ ! -s "$OUT/trivy-deps.json" ]; then row "Trivy dependencies" SKIP "Trivy produced no report: $(tool_error trivy)"
    elif [ "$(q "$OUT/trivy-deps.json" '[.Results[]? | select(.)] | length')" = 0 ]; then
      # Trivy reads lock files only (packages.lock.json, packages.config, package-lock.json, ...), not .NET project files.
      md "" "Trivy found no lock file it can read, so it adds nothing here. .NET projects without packages.lock.json are covered by the NuGet check above."
    else
      DEPS_CHECKED=$((DEPS_CHECKED+1))
      q "$OUT/trivy-deps.json" "$TRIVY_VULNS | $TRIVY_VULN_ROW" > "$T"
      n="$(grep -c . "$T")"
      if [ "$n" -gt 0 ]; then
        row "Trivy dependencies" FAIL "$(pl "$n" finding): $(q "$OUT/trivy-deps.json" "$TRIVY_VULNS"' | map(.pkg) | unique | few')"
        md "" "### All lock files and packages.config (Trivy)" "" "Trivy reads the same lock files as the audits above plus packages.config and other ecosystems, so expect overlap."
        table "$TRIVY_VULN_HEAD" "$T" "trivy-deps.json"
      else row "Trivy dependencies" PASS "$(pl "$(q "$OUT/trivy-deps.json" '[.Results[]? | select(.)] | length')" "lock file"), no findings at $SEVTEXT"; fi
    fi
  fi
  if [ "$DEPS_CHECKED" = 0 ] && { [ -n "$TARGETS" ] || [ -n "$LOCKS" ]; }; then
    row "Dependencies" SKIP "no dependency audit ran; install the dotnet SDK, npm, Trivy or Docker"
  fi
fi

section 3 "Secrets" "Passwords, keys and tokens in the files and in git history. Values are redacted in this report."
if skipped secrets; then skip_step "Secrets" secrets
else
  if available gitleaks && has_jq; then
    # The repository's own .gitleaks.toml, if any, is extended rather than replaced, so the ignored-files rule below still applies.
    EXT="useDefault = true"; [ -f .gitleaks.toml ] && EXT="path = '$(p_repo gitleaks)/.gitleaks.toml'"
    # Files git ignores (local appsettings, IDE state) are not in the repository and never shipped from it; gitleaks reads
    # every file in the folder, so name them here. Untracked files that are not ignored are still scanned: they could be committed.
    IGNORED="$(git -c core.quotepath=off ls-files --others --ignored --exclude-standard --directory 2>/dev/null)"
    { printf '[extend]\n%s\n' "$EXT"
      cat <<'TOML'
[[allowlists]]
description = "build output, installed packages and caches"
paths = [
  '''(^|/)node_modules/''', '''(^|/)bin/''', '''(^|/)obj/''', '''(^|/)dist/''', '''(^|/)build/''',
  '''(^|/)\.next/''', '''(^|/)\.angular/''', '''(^|/)packages/''', '''(^|/)TestResults/''', '''(^|/)security-reports/''',
  '''(^|/)\.dgf-factory/security/''', '''(^|/)\.dgf-factory/runtime/\.venv/''',
  '''(^|/)package-lock\.json$''', '''(^|/)yarn\.lock$''', '''(^|/)pnpm-lock\.yaml$''',
]
[[allowlists]]
description = "Power BI publish-to-web links: the token in them is a public report id, not a key"
regexTarget = "line"
regexes = ['''app\.powerbi\.com/view\?r=''']
[[allowlists]]
description = "documentation placeholders: AI Factory's security checklist teaches with this literal fake key"
regexTarget = "match"
regexes = ['''sk_live_abc123''']
TOML
    } > "$OUT/gitleaks.toml"
    # History keeps its findings in files ignored today (an appsettings.json committed before it was ignored), so only the tree scan skips them.
    cp "$OUT/gitleaks.toml" "$OUT/gitleaks-tree.toml"
    if [ -n "$IGNORED" ]; then
      { printf '\n[[allowlists]]\ndescription = "files git ignores"\npaths = [\n'
        printf '%s\n' "$IGNORED" | sed -E 's/([][\\.+*?(){}|^$])/\\\1/g' \
          | awk -v q="'''" '{ if (/\/$/) print "  " q "(^|/)" $0 q ","; else print "  " q "(^|/)" $0 "$" q "," }'
        printf ']\n'; } >> "$OUT/gitleaks-tree.toml"
    fi
    run_tool gitleaks "$GITLEAKS_IMG" dir "$(p_repo gitleaks)" --config "$(p_out gitleaks)/gitleaks-tree.toml" --redact --no-banner --exit-code 0 \
      --report-format json --report-path "$(p_out gitleaks)/gitleaks-tree.json"
    if [ ! -s "$OUT/gitleaks-tree.json" ]; then row "Secrets, working tree" SKIP "gitleaks produced no report"
    else
      q "$OUT/gitleaks-tree.json" "$LEAKS"' | .[] | "| \(.file | cell) | \(.line) | \(.rule) |"' > "$T"
      n="$(grep -c . "$T")"
      if [ "$n" -gt 0 ]; then
        row "Secrets, working tree" FAIL "$(pl "$n" finding): $(q "$OUT/gitleaks-tree.json" "$LEAK_RULES")"
        md "" "### In the current files"
        table "| File | Line | Type |" "$T" "gitleaks-tree.json"
      else row "Secrets, working tree" PASS "none found"; fi
      [ -n "$IGNORED" ] && md "" "Not scanned: $(pl "$(printf '%s\n' "$IGNORED" | grep -c .)" path) that git ignores, such as $(printf '%s\n' "$IGNORED" | head -3 | few). They are local files, not part of the repository."
    fi
    if git rev-parse --git-dir >/dev/null 2>&1; then
      # In a worktree or submodule .git is a file pointing outside the folder, so gitleaks in Docker sees no history and reports nothing.
      if ! has gitleaks && [ -f "$REPO/.git" ]; then
        row "Secrets, git history" SKIP "this folder is a git worktree or submodule, which gitleaks in Docker cannot read; scan a normal clone or install gitleaks"
      else
        TOTAL="$(git rev-list --count HEAD 2>/dev/null)"; TOTAL="${TOTAL:-0}"
        SPAN="all $TOTAL commits"
        [ "$HISTORY" -gt 0 ] && [ "$HISTORY" -lt "$TOTAL" ] && SPAN="the last $HISTORY of $TOTAL commits (older ones not checked, run with --history 0)"
        LOGOPTS=""; [ "$HISTORY" -gt 0 ] && LOGOPTS="--log-opts=-n $HISTORY"
        run_tool gitleaks "$GITLEAKS_IMG" git "$(p_repo gitleaks)" --config "$(p_out gitleaks)/gitleaks.toml" --redact --no-banner --exit-code 0 \
          ${LOGOPTS:+"$LOGOPTS"} --report-format json --report-path "$(p_out gitleaks)/gitleaks-history.json"
        if [ ! -s "$OUT/gitleaks-history.json" ]; then row "Secrets, git history" SKIP "gitleaks produced no report"
        else
          q "$OUT/gitleaks-history.json" "$LEAKS"' | .[] | "| \(.file | cell) | \(.line) | \(.rule) | \(.commit) | \(.date) |"' > "$T"
          n="$(grep -c . "$T")"
          if [ "$n" -gt 0 ]; then
            row "Secrets, git history" FAIL "$(pl "$n" finding) in $SPAN"
            md "" "### In git history ($SPAN)" "" "Each row is the commit that added the value. A secret still in the current files shows here too: removing it from the files does not remove it from history."
            table "| File | Line | Type | Commit | Date |" "$T" "gitleaks-history.json"
          else row "Secrets, git history" PASS "none in $SPAN"; fi
        fi
      fi
    fi
  else row "Secrets" SKIP "install gitleaks, and jq or Docker"; fi
  # An empty value (Password= at the end of a connection string, "") or a __Token__ the pipeline replaces is a placeholder, not a secret.
  KEY_RE='(Password|Pwd|PrivateKey|ClientSecret|ApiKey|SharedAccessKey|AccountKey|machineKey)'
  PLACEHOLDER_RE="$KEY_RE"'[^:=]{0,3}[:=][[:space:]]*(""|'"''"'|"?__[A-Za-z0-9_.:-]+__"?|\$\{|"?[[:space:]]*,?[[:space:]]*$|;)'
  git grep -nE "$KEY_RE"'[^:=]{0,3}[:=]' -- '*.json' '*.config' '*.yaml' '*.yml' '*.env*' ':!**/node_modules/**' 2>/dev/null \
    | grep -viE "$PLACEHOLDER_RE" | cut -d: -f1,2 > "$OUT/secret-candidates.txt"
  # .NET Framework appSettings use key="..." value="..." attributes, which the pattern above cannot see.
  git grep -niE 'key="[^"]*(password|secret|apikey|api_key|token|accountkey|privatekey)[^"]*"[[:space:]]+value="[^"_$][^"]+"' \
    -- '*.config' ':!**/node_modules/**' 2>/dev/null | cut -d: -f1,2 >> "$OUT/secret-candidates.txt"
  n="$(grep -c . "$OUT/secret-candidates.txt")"
  if [ "$n" -gt 0 ]; then
    row "Secret key names" WARN "$(pl "$n" line) to check by hand"
    awk -F: '{printf "| %s | %s |\n", $1, $2}' "$OUT/secret-candidates.txt" > "$T"
    md "" "### Settings named like secrets (check by hand)" "" "These lines set a key called Password, ApiKey, ClientSecret or similar to a value. Confirm each value is a placeholder, not a real secret."
    table "| File | Line |" "$T" "secret-candidates.txt"
  fi
  if step_failed 3 || [ "$n" -gt 0 ]; then
    md "" "**How to fix:** if a value is real, rotate it at the provider first, then move it to a secret store or pipeline variable. Deleting it from the code is not enough, because git history keeps it. If it is test data or an example, add it to the allowlist in \`.gitleaks.toml\`."
  fi
fi

section 4 "Configuration" "Dockerfiles, Kubernetes manifests, Helm charts, Terraform and web.config, checked for unsafe settings."
if skipped config; then skip_step "Configuration files" config
else
  if available trivy && has_jq; then
    rm -f "$OUT/trivy-config.json"
    run_tool trivy "$TRIVY_IMG" config --quiet --severity "$SEVERITY" --skip-dirs "$SKIP_DIRS" \
      --format json --output "$(p_out trivy)/trivy-config.json" "$(p_repo trivy)"
    if [ ! -s "$OUT/trivy-config.json" ]; then row "Configuration files" SKIP "Trivy produced no report: $(tool_error trivy)"
    else
      q "$OUT/trivy-config.json" "$TRIVY_CFG"' | .[] | "| \(.sev) | \(.where | cell) | \(link(.id; .url)) \(.title | cell) | \(.fix | cell | clip(160)) |"' > "$T"
      n="$(grep -c . "$T")"
      if [ "$n" -gt 0 ]; then row "Configuration files" FAIL "$(pl "$n" finding): $(q "$OUT/trivy-config.json" "$TRIVY_CFG"' | map(.title) | unique | few')"
      else row "Configuration files" PASS "no findings at $SEVTEXT"; fi
      table "| Severity | File | Issue | How to fix |" "$T" "trivy-config.json"
    fi
  else row "Configuration files" SKIP "install Trivy or Docker"; fi
  git grep -niE 'debug="true"|customErrors mode="Off"' -- ':(icase)*web.config' 2>/dev/null \
    | awk -F: '{line=$0; sub(/^[^:]*:[^:]*:[[:space:]]*/, "", line); gsub(/\|/, "\\|", line); if (length(line) > 80) line = substr(line, 1, 77) "..."; printf "| %s | %s | `%s` |\n", $1, $2, line}' > "$T"
  n="$(grep -c . "$T")"
  if [ "$n" -gt 0 ]; then
    row "web.config" WARN "debug or detailed errors switched on in $(pl "$n" place)"
    md "" "### web.config" "" "Debug compilation and detailed error pages expose stack traces and slow the site. Confirm the release transform (Web.Release.config) removes them."
    table "| File | Line | Setting |" "$T" ""
  fi
fi

section 5 "Code (SAST)" "Static analysis of the source code with Semgrep rules for the languages found: C#, TypeScript, JavaScript, React and Next.js."
if skipped code; then skip_step "Semgrep" code
elif available semgrep && has_jq; then
  PACKS="--config p/secrets"
  [ "$HAS_CS" = 1 ] && PACKS="$PACKS --config p/csharp"
  [ -n "$PKGJSONS" ] && PACKS="$PACKS --config p/typescript --config p/javascript"
  [ "$HAS_REACT" = 1 ] && PACKS="$PACKS --config p/react"
  [ "$HAS_NEXT" = 1 ] && PACKS="$PACKS --config p/nextjs"
  SG_SEV="--severity ERROR"; echo "$SEVERITY" | grep -qiE 'medium|low' && SG_SEV="--severity ERROR --severity WARNING"
  rm -f "$OUT/semgrep.json"
  # shellcheck disable=SC2086
  run_tool semgrep "$SEMGREP_IMG" scan --metrics=off --quiet $PACKS $SG_SEV \
    --exclude node_modules --exclude bin --exclude obj --exclude dist --exclude '*.min.js' --exclude .dgf-factory \
    --json --output "$(p_out semgrep)/semgrep.json" "$(p_repo semgrep)"
  if [ ! -s "$OUT/semgrep.json" ]; then row "Semgrep" SKIP "Semgrep produced no report"
  else
    q "$OUT/semgrep.json" "$SEMGREP_LIST"' | .[] | "| \(.sev) | \(.file | cell):\(.line) | \(.rule | cell) | \(.msg | cell | clip(200)) |"' > "$T"
    n="$(grep -c . "$T")"
    if [ "$n" -gt 0 ]; then row "Semgrep" FAIL "$(pl "$n" finding): $(q "$OUT/semgrep.json" "$SEMGREP_LIST"' | map(.rule) | unique | few')"
    else row "Semgrep" PASS "no findings"; fi
    md "" "Rule packs: \`$(echo "$PACKS" | sed 's/--config //g')\`."
    table "| Severity | Where | Rule | What is wrong |" "$T" "semgrep.json"
    errs="$(q "$OUT/semgrep.json" '.errors | length')"
    [ "${errs:-0}" -gt 0 ] && md "" "Semgrep could not fully read $(pl "$errs" file); those parts were not checked. Details are in \`$RAWREL/semgrep.json\` under \"errors\"."
    [ "$n" -gt 0 ] && md "" "**How to fix:** fix each real issue. For a false positive, add \`// nosemgrep: <rule>\` on the line with a short reason, so the next reviewer sees why."
  fi
else row "Semgrep" SKIP "install Semgrep, or Docker"; fi

section 6 "Container image" "Operating-system and application packages inside the image that is deployed, and the patch level of its .NET and Node.js runtimes. Only package findings with a released fix count."
if skipped image; then skip_step "Container image" image
elif [ -z "${IMAGES// /}" ] && [ "$BUILD" = 0 ]; then not_run "pass --build, or --image NAME[,NAME...], to scan the images you ship"
elif [ "$HAVE_DOCKER" = 0 ]; then row "Container image" SKIP "needs Docker"
else
  if [ "$BUILD" = 1 ]; then
    tag="$(basename "$REPO" | tr 'A-Z' 'a-z'):scan"
    if docker build --pull -f "$DOCKERFILE" -t "$tag" . > "$OUT/docker-build.log" 2>&1; then
      log "  built $tag"; md "" "Built \`$tag\` from \`$DOCKERFILE\`."; IMAGES="$IMAGES $tag"
    else row "Image build" FAIL "docker build of $DOCKERFILE failed, see $RAWREL/docker-build.log"; fi
  fi
  for img in $IMAGES; do
    safe="$(printf '%s' "$img" | sed 's/[^A-Za-z0-9._-]/_/g')"
    md "" "### $img"
    if ! docker image inspect "$img" >/dev/null 2>&1 && ! docker pull "$img" > "$OUT/pull-$safe.log" 2>&1; then
      row "Image $img" SKIP "could not pull it (docker login to the registry?), see $RAWREL/pull-$safe.log"; continue
    fi
    file="trivy-image-$safe.json"
    rm -f "$OUT/$file"
    run_tool --socket trivy "$TRIVY_IMG" image --quiet --severity "$SEVERITY" --ignore-unfixed \
      --format json --output "$(p_out trivy)/$file" "$img"
    # Trivy cannot read some locally built images through the Docker socket (a layer missing from the image store export).
    # Then scan the image's files: export a container of it and let Trivy unpack and scan that as a root filesystem.
    if [ ! -s "$OUT/$file" ]; then
      cid="$(docker create "$img" 2>/dev/null | tail -1)"
      if [ -n "$cid" ]; then
        tmp="$(mktemp -d)"
        docker export -o "$tmp/fs.tar" "$cid" >/dev/null 2>&1; docker rm "$cid" >/dev/null 2>&1
        echo "trivy|Docker|$TRIVY_IMG" >> "$TOOLS"
        docker run --rm -v "$tmp":/in:ro -v "$OUT":/out -v security-scan-cache:/root/.cache --entrypoint sh "$TRIVY_IMG" -c \
          "mkdir /fs && tar -xf /in/fs.tar -C /fs 2>/dev/null; trivy rootfs --timeout 30m --quiet --severity $SEVERITY --ignore-unfixed --format json --output /out/$file /fs" >/dev/null 2>&1
        rm -rf "$tmp"
        [ -s "$OUT/$file" ] && md "" "Trivy could not read this image through Docker, so its exported file system was scanned instead."
      fi
    fi
    if [ ! -s "$OUT/$file" ]; then row "Image $img" SKIP "Trivy produced no report: $(tool_error trivy)"
    else
      q "$OUT/$file" "$TRIVY_VULNS | $TRIVY_VULN_ROW" > "$T"
      n="$(grep -c . "$T")"
      if [ "$n" -gt 0 ]; then row "Image $img" FAIL "$(pl "$n" "fixable finding"): $(q "$OUT/$file" "$TRIVY_VULNS"' | map(.pkg) | unique | few')"
      else row "Image $img" PASS "no fixable findings at $SEVTEXT"; fi
      os="$(q "$OUT/$file" '"\(.Metadata.OS.Family // "") \(.Metadata.OS.Name // "")"')"
      [ -n "${os// /}" ] && md "" "Base operating system: $os."
      table "$TRIVY_VULN_HEAD" "$T" "$file"
      [ "$n" -gt 0 ] && md "" "**How to fix:** rebuild on the newest tag of the base image (\`docker build --pull\`), and upgrade the application packages listed. Then rescan."
    fi
    RTS="$(image_runtimes "$img")"
    if [ -z "$RTS" ]; then md "" "No .NET or Node.js runtime found in the image (a self-contained app carries its own: check the SDK that published it)."
    else
      : > "$T"; bad=""; unk=0; names=""
      while IFS=$'\t' read -r rn rv kind; do
        [ -n "$rn" ] || continue
        if [ "$kind" = node ]; then d="$(node_verdict "$rv")"; else d="$(dotnet_verdict "$kind" "$rv")"; fi
        IFS=$'\t' read -r st note latest <<EOF2
$d
EOF2
        res=PASS
        if [ -z "$st" ] || [ "$st" = unknown ]; then res=WARN; unk=$((unk+1))
        elif [ "$st" != ok ]; then res="**FAIL**"; bad="$bad$rn $rv"$'\n'; fi
        printf '| %s | %s | %s | %s | %s |\n' "$rn" "$rv" "$(cell "$note")" "${latest:--}" "$res" >> "$T"
        printf '    %-44s %s\n' "$rn $rv" "$note"
        names="$names$rn $rv"$'\n'
      done <<EOF
$RTS
EOF
      table "| Runtime in the image | Version | Status | Latest patch | Result |" "$T" ""
      if [ -n "$bad" ]; then row "Runtime in $img" FAIL "vulnerable: $(printf '%s' "$bad" | few)"
      elif [ "$unk" -gt 0 ]; then row "Runtime in $img" WARN "$(pl "$unk" runtime) could not be checked"
      else row "Runtime in $img" PASS "$(printf '%s' "$names" | few), all patched"; fi
    fi
  done
fi

section 7 "Running application (DAST)" "OWASP ZAP visits the running test site and checks its responses: security headers, cookie flags, error pages and known vulnerable JavaScript libraries. It does not attack the site."
if skipped dast; then skip_step "ZAP baseline" dast
elif [ -z "$URL" ]; then not_run "pass --url with a test environment address to scan the running site"
elif [ "$HAVE_DOCKER" = 0 ] || ! has_jq; then row "ZAP baseline" SKIP "needs Docker"
else
  TARGET="$(echo "$URL" | sed -E 's#://(localhost|127\.0\.0\.1)#://host.docker.internal#')"
  # ZAP runs as its own unprivileged user (zap, uid 1000), which must write its reports into the mounted folder.
  # The folder is closed again to the owner alone when the run ends.
  chmod 777 "$OUT" 2>/dev/null
  echo "zap|Docker|$ZAP_IMG" >> "$TOOLS"
  docker run --rm --add-host host.docker.internal:host-gateway -v "$OUT":/zap/wrk:rw -t "$ZAP_IMG" \
    zap-baseline.py -t "$TARGET" -m 1 -r zap-baseline.html -J zap-baseline.json -I > "$OUT/zap.log" 2>&1
  if [ ! -s "$OUT/zap-baseline.json" ]; then row "ZAP baseline $URL" FAIL "scan did not complete, see $RAWREL/zap.log"
  else
    q "$OUT/zap-baseline.json" "$ZAP_LIST"' | .[] | "| \(.risk) | \(.name | cell) | \(.n) | \(.uri | cell | clip(80)) | \(.fix | cell | clip(160)) |"' > "$T"
    block="$(q "$OUT/zap-baseline.json" "$ZAP_LIST"' | map(select(.risk | blocking($s))) | length')"
    medium="$(q "$OUT/zap-baseline.json" "$ZAP_LIST"' | map(select(.risk == "Medium")) | length')"
    total="$(grep -c . "$T")"
    if [ "${block:-0}" -gt 0 ]; then row "ZAP baseline $URL" FAIL "$(pl "$block" alert) at $SEVTEXT, $total in total"
    elif [ "${medium:-0}" -gt 0 ]; then row "ZAP baseline $URL" WARN "$(pl "$medium" "medium-risk alert"), $total in total"
    else row "ZAP baseline $URL" PASS "no high or medium alerts ($total low or informational)"; fi
    table "| Risk | Alert | Places | Example URL | How to fix |" "$T" "zap-baseline.json"
    md "" "The full ZAP report, with every request and response, is \`$RAWREL/zap-baseline.html\`. Open it in a browser."
  fi
fi

section 8 "SBOM" "A list of every component in this release. Keep it with the release: when the next CVE is published, search it to see whether this version is affected."
if skipped sbom; then skip_step "SBOM" sbom
elif ! has_jq; then row "SBOM" SKIP "needs jq or Docker"
else
  # Trivy reads lock files only, so the NuGet packages that dotnet resolved in section 2 are added to the source SBOM.
  SRC="$OUT/sbom-source.cdx.json"
  available trivy && run_tool trivy "$TRIVY_IMG" fs --quiet --format cyclonedx --skip-dirs "$SKIP_DIRS" \
    --output "$(p_out trivy)/sbom-source.cdx.json" "$(p_repo trivy)"
  from="$(q "$SRC" '[.components[]? | select(.)] | length')"; from="${from:-0}"
  { if [ -s "$SRC" ]; then cat "$SRC"; else echo '{"bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1}'; fi
    cat "$REL"/nuget-all-*.json 2>/dev/null; } | jqx -s "$SBOM_MERGE" > "$REL/sbom.json" 2>/dev/null
  total="$(q "$REL/sbom.json" '.components | length')"; total="${total:-0}"
  FILES=""
  if [ "$total" -gt 0 ]; then
    mv "$REL/sbom.json" "$SRC"
    row "SBOM, source" PASS "$(pl "$total" component) ($((total - from)) NuGet from dotnet, $from from lock files)"
    FILES="\`$RAWREL/sbom-source.cdx.json\`"
  else row "SBOM, source" SKIP "no packages found: no lock files and no NuGet data from section 2"; fi
  if available trivy && [ "$HAVE_DOCKER" = 1 ]; then
    for img in $IMAGES; do
      safe="$(printf '%s' "$img" | sed 's/[^A-Za-z0-9._-]/_/g')"
      docker image inspect "$img" >/dev/null 2>&1 || continue
      file="sbom-image-$safe.cdx.json"
      run_tool --socket trivy "$TRIVY_IMG" image --quiet --format cyclonedx --output "$(p_out trivy)/$file" "$img"
      n="$(q "$OUT/$file" '[.components[]? | select(.)] | length')"
      if [ "${n:-0}" -gt 0 ]; then row "SBOM, $img" PASS "$(pl "$n" component)"; FILES="${FILES:+$FILES, }\`$RAWREL/$file\`"
      else row "SBOM, $img" SKIP "Trivy produced no SBOM"; fi
    done
  fi
  [ -n "$FILES" ] && md "" "Files: $FILES (CycloneDX). To check one later: \`trivy sbom <file>\`."
fi

# The verdict and summary go first: most readers stop there.
ELAPSED=$(( $(date +%s) - START ))
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
COMMIT="$(git rev-parse --short HEAD 2>/dev/null)"
DIRTY=""; [ -n "$(git status --porcelain --untracked-files=no 2>/dev/null | head -1)" ] && DIRTY=" (with uncommitted changes)"
next_step() {
  case "$1" in
    3) echo "Rotate every real secret in section 3, then remove it from the code. Do this first: a leaked secret is usable today." ;;
    2) echo "Upgrade the packages in section 2 to the fixed version. Where no fix exists, record an exception with a review date." ;;
    6) echo "Rebuild the images on the newest base image and rescan (section 6)." ;;
    1) echo "Move the vulnerable or end-of-life versions in section 1 to the patch named there." ;;
    7) echo "Fix the alerts from the running site in section 7, then rescan the test environment." ;;
    4) echo "Fix the configuration findings in section 4; the How to fix column says what to change." ;;
    5) echo "Review the code findings in section 5. Fix the real ones and mark false positives with a reason." ;;
  esac
}
{
  echo "# Security scan report: $(basename "$REPO")"
  echo
  echo "- **Scanned:** $(date '+%Y-%m-%d %H:%M %Z'), took $((ELAPSED / 60)) min $((ELAPSED % 60)) s"
  [ -n "$COMMIT" ] && echo "- **Code:** branch $BRANCH, commit $COMMIT$DIRTY"
  echo "- **Folder:** \`$REPO\`"
  echo "- **Run by:** $(git config user.name 2>/dev/null || whoami) on $(hostname)"
  echo "- **Blocking severities:** $SEVTEXT"
  for img in $IMAGES; do echo "- **Image:** \`$img\`"; done
  [ -n "$URL" ] && echo "- **Test site:** $URL"
  echo
  if [ "$FAILED" = 1 ]; then echo "## Result: FAIL"; elif [ "$SKIPPED" -gt 0 ]; then echo "## Result: INCOMPLETE"; else echo "## Result: PASS"; fi
  echo
  echo "$(pl "$FAILS" check) failed, $WARNS to review by hand, $PASSES passed, $SKIPPED skipped."
  if [ "$FAILED" = 1 ]; then echo "Do not release until every FAIL is fixed or has an approved exception."
  else echo "No blocking findings at $SEVTEXT."; fi
  [ "$SKIPPED" -gt 0 ] && echo && echo "**This result is incomplete:** $(pl "$SKIPPED" check) did not run. Install the missing tools or Docker and rerun."
  echo
  echo "FAIL blocks the release. WARN needs a person to look. SKIP means the check did not run."
  echo
  echo "## Summary"
  echo
  echo "| Check | Result | Finding |"
  echo "| --- | --- | --- |"
  cat "$ROWS"
  if [ "$FAILED" = 1 ] || [ "$WARNS" -gt 0 ] || [ "$SKIPPED" -gt 0 ]; then
    echo
    echo "## What to do next"
    echo
    i=0
    for s in 3 2 6 1 7 4 5; do
      step_failed "$s" && { i=$((i+1)); echo "$i. $(next_step "$s")"; }
    done
    [ "$WARNS" -gt 0 ] && { i=$((i+1)); echo "$i. Check the WARN rows by hand; each section says what to look for."; }
    [ "$SKIPPED" -gt 0 ] && { i=$((i+1)); echo "$i. Install what the SKIP rows ask for and rerun, so the result is complete."; }
  fi
  cat "$DETAILS"
  echo
  echo "## Files"
  echo
  echo "Raw scanner output is in \`$RAWREL/\`, next to this report:"
  echo
  for f in $(ls "$OUT"); do
    case "$f" in
      nuget-*.json) w="dotnet list package --vulnerable output" ;;
      npm-*.json) w="npm audit output" ;;
      trivy-deps.json) w="Trivy dependency findings" ;;
      trivy-config.json) w="Trivy configuration findings" ;;
      trivy-image-*.json) w="Trivy image findings" ;;
      gitleaks-*.json) w="gitleaks findings, secrets redacted" ;;
      gitleaks.toml) w="gitleaks settings used for git history" ;;
      gitleaks-tree.toml) w="gitleaks settings used for the current files (also skips files git ignores)" ;;
      secret-candidates.txt) w="settings named like secrets" ;;
      semgrep.json) w="Semgrep findings and parse errors" ;;
      sbom-*.cdx.json) w="SBOM, CycloneDX" ;;
      zap-baseline.html) w="ZAP report, open in a browser" ;;
      zap-baseline.json|zap.yaml) w="ZAP findings" ;;
      *.log) w="tool log" ;;
      *) w="" ;;
    esac
    echo "- \`$f\`${w:+: $w}"
  done
  echo
  echo "Scanners used:"
  echo
  sort -u "$TOOLS" | awk -F'|' '{ if ($2 == "Docker") printf "- %s: Docker image `%s`\n", $1, $3; else printf "- %s: installed, %s\n", $1, $3 }'
} > "$REPORT"
rm -rf "$ROWS" "$DETAILS" "$TOOLS" "$T" "$REL"
# The raw output and the report can quote secrets and findings: readable by the owner alone.
chmod -R go-rwx "$OUT" "$REPORT" 2>/dev/null

# A report folder the scan created ignores itself; one that already existed inside the repository may not.
if case "$REPORTS/" in "$REPO"/*) true ;; *) false ;; esac && ! git check-ignore -q "$REPORTS/x" 2>/dev/null && git rev-parse --git-dir >/dev/null 2>&1; then
  log ""; log "Tip: add $(rel "$REPORTS")/ to .gitignore so reports are never committed."
fi
printf '\n'
if [ "$FAILED" = 1 ]; then echo "RESULT: FAIL"
elif [ "$SKIPPED" -gt 0 ]; then echo "RESULT: INCOMPLETE (no failures in the checks that ran)"
else echo "RESULT: PASS"; fi
[ "$SKIPPED" -gt 0 ] && printf 'INCOMPLETE: %s check(s) skipped; see the SKIP rows above.\n' "$SKIPPED"
printf 'Report: %s\n' "$REPORT"
# The house verdict, last: a skipped check is a check that did not run, so it warns and never passes.
if [ "$FAILED" = 1 ]; then echo "BLOCKED"; exit 1; fi
if [ "$WARNS" -gt 0 ] || [ "$SKIPPED" -gt 0 ]; then echo "WARNINGS"; exit 2; fi
echo "CLEAN"
exit 0

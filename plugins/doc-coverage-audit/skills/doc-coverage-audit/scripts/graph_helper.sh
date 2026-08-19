#!/bin/zsh
# Microsoft Graph auth + request helper for doc-coverage-audit.
#
#   export DCA_DIR=/path/to/scratch          # where tokens are cached (default: cwd)
#   ./graph_helper.sh probe                  # what access does the current az login have?
#   ./graph_helper.sh consent <tenantId>     # is Graph CLI Tools pre-consented org-wide?
#   ./graph_helper.sh devicecode <tenantId>  # start device-code sign-in
#   ./graph_helper.sh poll <tenantId>        # complete it (prints OK on success)
#   ./graph_helper.sh refresh <tenantId>     # refresh the access token
#   ./graph_helper.sh get <url>              # authenticated GET
#
# Read references/graph-auth.md before using this.

set -u
DIR=${DCA_DIR:-$PWD}
CID=14d82eec-204b-4c2f-b7e8-296a70dab67e   # Microsoft Graph Command Line Tools
SCOPE="https://graph.microsoft.com/Sites.Read.All https://graph.microsoft.com/Files.Read.All offline_access"
TOK=$DIR/gtok.txt; REF=$DIR/grefresh.txt; DC=$DIR/dc.json

case "${1:-}" in

probe)
  echo "=== az account ==="
  az account show -o json 2>&1 | jq -r '{user:.user.name,tenant:.tenantId,domain:.tenantDefaultDomain}' 2>/dev/null \
    || { echo "az not logged in"; exit 1; }
  echo "=== graph token scopes ==="
  az account get-access-token --resource https://graph.microsoft.com -o tsv --query accessToken > "$DIR/aztok.txt" 2>/dev/null \
    || { echo "could not get graph token"; exit 1; }
  python3 -c "
import base64,json,sys
t=open('$DIR/aztok.txt').read().strip().split('.')[1]; t+='='*(-len(t)%4)
d=json.loads(base64.urlsafe_b64decode(t))
scp=d.get('scp','')
print('appid :',d.get('appid'),d.get('app_displayname'))
print('scopes:',scp)
ok=any(s.startswith(('Sites.','Files.')) for s in scp.split())
print()
print('VERDICT:', 'az token can read SharePoint' if ok else 'az token CANNOT read SharePoint -> go to rung 3 (consent)')
"
  ;;

consent)
  T=$(cat "$DIR/aztok.txt" 2>/dev/null) || { echo "run probe first"; exit 1; }
  SPID=$(curl -s -H "Authorization: Bearer $T" \
    "https://graph.microsoft.com/v1.0/servicePrincipals?\$filter=appId%20eq%20'$CID'&\$select=id" \
    | jq -r '.value[0].id // empty')
  [ -z "$SPID" ] && { echo "Graph CLI Tools SP not present in tenant"; exit 1; }
  echo "Graph CLI Tools SP: $SPID"
  curl -s -H "Authorization: Bearer $T" \
    "https://graph.microsoft.com/v1.0/oauth2PermissionGrants?\$filter=clientId%20eq%20'$SPID'" \
    | jq -c '.value[] | {consentType, scope}'
  echo
  echo "AllPrincipals + Sites.Read.All  =>  device code needs no tenant change."
  ;;

devicecode)
  curl -s -X POST "https://login.microsoftonline.com/$2/oauth2/v2.0/devicecode" \
    -d "client_id=$CID" --data-urlencode "scope=$SCOPE" -o "$DC"
  jq -r 'if .user_code then "CODE: \(.user_code)\nURL:  \(.verification_uri)\nexpires_in: \(.expires_in)s" else . end' "$DC"
  ;;

poll)
  D=$(jq -r .device_code "$DC")
  for i in $(seq 1 90); do
    R=$(curl -s -X POST "https://login.microsoftonline.com/$2/oauth2/v2.0/token" \
      -d "grant_type=urn:ietf:params:oauth:grant-type:device_code" -d "client_id=$CID" -d "device_code=$D")
    E=$(echo "$R" | jq -r '.error // "none"')
    if [ "$E" = "none" ]; then
      echo "$R" | jq -r .access_token > "$TOK"; echo "$R" | jq -r .refresh_token > "$REF"
      echo "OK authenticated"; exit 0
    fi
    [ "$E" != "authorization_pending" ] && { echo "ERR: $E"; echo "$R" | jq -r '.error_description' | head -2; exit 1; }
    perl -e 'select(undef,undef,undef,5)'
  done
  echo "timed out"; exit 1
  ;;

refresh)
  R=$(curl -s -X POST "https://login.microsoftonline.com/$2/oauth2/v2.0/token" \
    -d "grant_type=refresh_token" -d "client_id=$CID" \
    --data-urlencode "scope=$SCOPE" --data-urlencode "refresh_token=$(cat "$REF")")
  A=$(echo "$R" | jq -r '.access_token // empty')
  [ -z "$A" ] && { echo "$R" | head -c 300; exit 1; }
  echo "$A" > "$TOK"; echo "$R" | jq -r .refresh_token > "$REF"; echo refreshed
  ;;

get)
  curl -s -H "Authorization: Bearer $(cat "$TOK")" "$2"
  ;;

*) sed -n '2,20p' "$0" ;;
esac

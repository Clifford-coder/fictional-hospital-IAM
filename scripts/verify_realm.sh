#!/usr/bin/env bash
# Reads the live hospital realm settings back from a running Keycloak (default http://localhost:8080).
# Needs KC_BOOTSTRAP_ADMIN_USERNAME / KC_BOOTSTRAP_ADMIN_PASSWORD in the environment:
#   set -a; . ./.env; set +a; bash scripts/verify_realm.sh
set -uo pipefail
: "${KC_BOOTSTRAP_ADMIN_USERNAME:?load your .env first:  set -a; . ./.env; set +a}"
: "${KC_BOOTSTRAP_ADMIN_PASSWORD:?load your .env first:  set -a; . ./.env; set +a}"
KC="${KEYCLOAK_URL:-http://localhost:8080}"
NL=$'\n'

resp=$(curl -sS -w "${NL}%{http_code}" -d client_id=admin-cli -d grant_type=password \
  --data-urlencode "username=${KC_BOOTSTRAP_ADMIN_USERNAME}" \
  --data-urlencode "password=${KC_BOOTSTRAP_ADMIN_PASSWORD}" \
  "$KC/realms/master/protocol/openid-connect/token") || {
  echo "Could not reach Keycloak at $KC. Is the container running and is port 8080 published?"; exit 1; }
code=${resp##*$NL}; body=${resp%$NL*}

if [ "$code" != "200" ]; then
  msg=$(printf '%s' "$body" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("error_description") or d.get("error"))' 2>/dev/null)
  echo "Keycloak refused the admin sign-in (HTTP $code): ${msg:-$body}"
  case "$msg" in
    "Invalid user credentials") echo "  The username/password in .env do not match the running container's admin."
                                echo "  The admin is created from the variables the container was STARTED with; restart it with --env-file .env."
                                echo "  Also check .env has no quotes or trailing spaces around the values." ;;
    "Account is not fully set up") echo "  The admin has a pending required action (password change, OTP...). Sign in to the admin console once and finish it," 
                                   echo "  or use a throwaway container started from the image." ;;
    "Account disabled") echo "  The admin account is disabled." ;;
  esac
  exit 1
fi

TOKEN=$(printf '%s' "$body" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
curl -fsS -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/hospital" |
python3 -c '
import sys, json
r = json.load(sys.stdin)
for k in ("ssoSessionIdleTimeout", "ssoSessionMaxLifespan", "accessTokenLifespan", "passwordPolicy", "browserFlow"):
    print(f"{k:24} {r[k]}")'

#!/usr/bin/env bash
# Part 2, Phase 0: check the workstation and repository before any manifest is written.
# Run from the repository root:  bash scripts/preflight.sh
# Read-only. Changes nothing. Exit status 1 if any check FAILs (WARNs do not fail it).
# Written for bash 3.2 (macOS) and later.

cd "$(dirname "$0")/.." || exit 1
FAILS=0; WARNS=0
ok()   { printf '[ OK ] %s\n' "$1"; }
warn() { printf '[WARN] %s\n' "$1"; WARNS=$((WARNS+1)); }
fail() { printf '[FAIL] %s\n' "$1"; FAILS=$((FAILS+1)); }

if [ ! -f versions.env ]; then echo "versions.env not found; run from the repository root."; exit 1; fi
# shellcheck disable=SC1091
. ./versions.env
for v in KEYCLOAK_VERSION KIND_VERSION K8S_NODE_IMAGE PUBLIC_HOSTS HOST_HTTPS_PORT HOST_HTTP_PORT MIN_DOCKER_MEMORY_GB REALM_SSO_IDLE_SECONDS REALM_SSO_MAX_SECONDS REALM_PASSWORD_HISTORY; do
  eval "val=\${$v:-}"
  if [ -z "$val" ]; then echo "versions.env: $v is missing or empty."; exit 1; fi
done

echo "== Repository"
if git rev-parse --git-dir >/dev/null 2>&1; then
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  if [ "$branch" = "part2" ]; then ok "on branch part2"; else warn "on branch '$branch' (Phase 0 expects part2)"; fi
  if git rev-parse -q --verify refs/tags/part1-complete >/dev/null; then ok "tag part1-complete exists"; else fail "tag part1-complete is missing (tag Part 1 before changing anything)"; fi
  if [ -z "$(git status --porcelain)" ]; then ok "working tree clean"; else warn "uncommitted changes present"; fi
  if git check-ignore -q .env; then ok ".env is git-ignored"; else fail ".env is NOT git-ignored"; fi
else
  fail "not a git repository"
fi
if python3 - "$REALM_SSO_IDLE_SECONDS" "$REALM_SSO_MAX_SECONDS" "$REALM_PASSWORD_HISTORY" <<'PY'
import json, sys
idle, mx, hist = (int(a) for a in sys.argv[1:4])
r = json.load(open("keycloak/realm/hospital-realm.json"))
bad = []
if r.get("ssoSessionIdleTimeout") != idle: bad.append("ssoSessionIdleTimeout")
if r.get("ssoSessionMaxLifespan") != mx: bad.append("ssoSessionMaxLifespan")
if "passwordHistory(%d)" % hist not in r.get("passwordPolicy", ""): bad.append("passwordPolicy")
sys.exit(1 if bad else 0)
PY
then ok "realm file: idle $((REALM_SSO_IDLE_SECONDS / 60)) min, max $((REALM_SSO_MAX_SECONDS / 3600)) h, password history $REALM_PASSWORD_HISTORY (as versions.env states)"; else fail "realm file differs from the session/password values in versions.env (see scripts/reconcile_realm.py)"; fi
placeholders=$(grep -v '^[[:space:]]*#' versions.env | grep -c 'FILL_IN')
if [ "$placeholders" -eq 0 ]; then ok "versions.env: no placeholders left"; else warn "versions.env still has $placeholders placeholder line(s) to fill in"; fi

echo "== Tools"
if command -v python3 >/dev/null 2>&1; then
  if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then ok "python3 $(python3 -c 'import platform; print(platform.python_version())')"; else fail "python3 is older than 3.9"; fi
else fail "python3 not found"; fi
if command -v openssl >/dev/null 2>&1; then ok "openssl present (used to generate secrets)"; else fail "openssl not found"; fi

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    ok "docker daemon reachable (server $(docker version --format '{{.Server.Version}}' 2>/dev/null))"
    mem=$(docker info --format '{{.MemTotal}}' 2>/dev/null); cpus=$(docker info --format '{{.NCPU}}' 2>/dev/null)
    gb=$(python3 -c "print(round(${mem:-0}/1024**3, 1))")
    if python3 -c "import sys; sys.exit(0 if ${mem:-0} >= ${MIN_DOCKER_MEMORY_GB}*1024**3*0.95 else 1)"; then ok "docker has ${gb} GB RAM, ${cpus} CPUs"; else warn "docker has only ${gb} GB RAM (want ${MIN_DOCKER_MEMORY_GB}+): raise it in Docker Desktop > Settings > Resources"; fi
  else fail "docker is installed but the daemon is not running"; fi
else fail "docker not found"; fi

K8S_MINOR=$(printf '%s' "$K8S_NODE_IMAGE" | sed -E 's#.*:v[0-9]+\.([0-9]+)\.[0-9]+.*#\1#')
if command -v kubectl >/dev/null 2>&1; then
  kminor=$(kubectl version --client -o json 2>/dev/null | python3 -c 'import sys,json,re; print(re.sub(r"\D","",json.load(sys.stdin)["clientVersion"]["minor"]))' 2>/dev/null)
  if [ -z "$kminor" ]; then warn "kubectl found but its version could not be read"
  else
    diff=$((kminor - K8S_MINOR)); [ "$diff" -lt 0 ] && diff=$((0 - diff))
    if [ "$diff" -le 1 ]; then ok "kubectl 1.$kminor is within one minor version of the cluster (1.$K8S_MINOR)"; else fail "kubectl 1.$kminor is more than one minor away from the cluster (1.$K8S_MINOR)"; fi
  fi
else fail "kubectl not found"; fi
if command -v kind >/dev/null 2>&1; then
  kv=$(kind version 2>/dev/null | awk '{print $2}')
  if [ "$kv" = "$KIND_VERSION" ]; then ok "kind $kv (pinned)"; else warn "kind is $kv but versions.env pins $KIND_VERSION; the pinned node image was built for $KIND_VERSION"; fi
else fail "kind not found"; fi

echo "== Hostnames and ports (HTTPS port ${HOST_HTTPS_PORT}, HTTP port ${HOST_HTTP_PORT})"
for h in $PUBLIC_HOSTS; do
  ip=$(python3 -c 'import socket,sys; print(socket.gethostbyname(sys.argv[1]))' "$h" 2>/dev/null)
  if [ "$ip" = "127.0.0.1" ]; then ok "$h -> 127.0.0.1"; elif [ -z "$ip" ]; then fail "$h does not resolve (add it to /etc/hosts)"; else fail "$h resolves to $ip, expected 127.0.0.1"; fi
done
port_state() {
  python3 -c 'import socket,sys
s = socket.socket(); s.settimeout(1)
try:
    s.connect(("127.0.0.1", int(sys.argv[1]))); print("busy")
except OSError:
    print("free")' "$1"
}
for p in "$HOST_HTTPS_PORT" "$HOST_HTTP_PORT"; do
  if [ "$(port_state "$p")" = "free" ]; then ok "nothing is listening on port $p"; else fail "something is already listening on port $p"; fi
done

echo
echo "$FAILS failure(s), $WARNS warning(s)."
[ "$FAILS" -eq 0 ]

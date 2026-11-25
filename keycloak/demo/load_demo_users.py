#!/usr/bin/env python3
"""Create (or remove) the fictional demo users in a running Keycloak.

Uses only the Python standard library, so it runs on the Mac, in a plain
python:slim container, or in a Kubernetes Job without installing anything.

Every user gets the password in DEMO_USER_PASSWORD, marked temporary: the first
sign-in forces a password change and then authenticator (TOTP) enrollment. The
password is read from the environment, never printed, and never written to disk.
Users that already exist are skipped and are never modified.

Usage (from the repository root, with Keycloak running):
    set -a; . ./.env; set +a
    python3 keycloak/demo/load_demo_users.py            # create the users
    python3 keycloak/demo/load_demo_users.py --remove   # delete the same users

Environment:
    KC_BOOTSTRAP_ADMIN_USERNAME, KC_BOOTSTRAP_ADMIN_PASSWORD   admin sign-in
    DEMO_USER_PASSWORD     required to create users; at least 14 characters
    KEYCLOAK_URL           default http://localhost:8080
    REALM                  default hospital
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(HERE, "demo_users.json")
KC = os.environ.get("KEYCLOAK_URL", "http://localhost:8080").rstrip("/")
REALM = os.environ.get("REALM", "hospital")
MIN_LEN = 14   # the realm's password policy; checked here for a clearer message


class KeycloakError(Exception):
    pass


def call(method, url, token=None, data=None, form=None):
    headers = {}
    body = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as err:
        raw = err.read().decode(errors="replace")
        try:
            parsed = json.loads(raw)
            msg = parsed.get("error_description") or parsed.get("errorMessage") or parsed.get("error") or raw
        except ValueError:
            msg = raw
        return err.code, msg
    except urllib.error.URLError as err:
        raise KeycloakError(f"Could not reach Keycloak at {KC} ({err.reason}). Is it running and is port 8080 published?")


def admin_token():
    user = os.environ.get("KC_BOOTSTRAP_ADMIN_USERNAME")
    pw = os.environ.get("KC_BOOTSTRAP_ADMIN_PASSWORD")
    if not user or not pw:
        raise KeycloakError("Load your .env first:  set -a; . ./.env; set +a")
    status, body = call("POST", f"{KC}/realms/master/protocol/openid-connect/token",
                        form={"client_id": "admin-cli", "grant_type": "password",
                              "username": user, "password": pw})
    if status != 200:
        raise KeycloakError(f"Keycloak refused the admin sign-in (HTTP {status}): {body}. "
                            "Run scripts/verify_realm.sh for hints.")
    return body["access_token"]


def find_user(token, username):
    q = urllib.parse.urlencode({"username": username, "exact": "true"})
    status, body = call("GET", f"{KC}/admin/realms/{REALM}/users?{q}", token)
    if status != 200:
        raise KeycloakError(f"Looking up {username} failed (HTTP {status}): {body}")
    return body[0] if body else None


def create(token, users, password):
    failures = 0
    for u in users:
        if find_user(token, u["username"]):
            print(f"  exists   {u['username']} (left unchanged)")
            continue
        payload = {
            "username": u["username"], "firstName": u["firstName"], "lastName": u["lastName"],
            "email": u["email"], "enabled": u["enabled"], "emailVerified": True,
            "groups": u["groups"],
            "credentials": [{"type": "password", "value": password, "temporary": True}],
        }
        status, body = call("POST", f"{KC}/admin/realms/{REALM}/users", token, data=payload)
        if status == 201:
            print(f"  created  {u['username']}")
        else:
            failures += 1
            print(f"  FAILED   {u['username']} (HTTP {status}): {body}")
    return failures


def remove(token, users):
    failures = 0
    for u in users:
        found = find_user(token, u["username"])
        if not found:
            print(f"  absent   {u['username']}")
            continue
        status, body = call("DELETE", f"{KC}/admin/realms/{REALM}/users/{found['id']}", token)
        if status == 204:
            print(f"  removed  {u['username']}")
        else:
            failures += 1
            print(f"  FAILED   {u['username']} (HTTP {status}): {body}")
    return failures


def main():
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] != "--remove"):
        sys.exit(__doc__)
    removing = len(sys.argv) == 2
    with open(USERS_FILE, encoding="utf-8") as f:
        users = json.load(f)["users"]
    password = os.environ.get("DEMO_USER_PASSWORD", "")
    if not removing and len(password) < MIN_LEN:
        sys.exit(f"DEMO_USER_PASSWORD must be set in .env and be at least {MIN_LEN} characters long.")
    try:
        token = admin_token()
        print(f"{'Removing' if removing else 'Creating'} {len(users)} demo users in realm '{REALM}' at {KC}")
        failures = remove(token, users) if removing else create(token, users, password)
    except KeycloakError as err:
        sys.exit(str(err))
    if failures:
        sys.exit(f"{failures} user(s) failed.")
    print("Done.")


if __name__ == "__main__":
    main()

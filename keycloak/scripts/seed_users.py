#!/usr/bin/env python3
"""Add fictional seed users to a Keycloak realm export, in place.

Keycloak's partial export leaves users out, so this script writes the project's
fictional users into the exported realm file. It is safe to re-run: the "users"
list is replaced each time.

Usage:
    python3 keycloak/scripts/seed_users.py keycloak/realm/hospital-realm.json

All users are fictional. The shared password below is a demo seed value for
local development only.
"""
import json
import sys

SEED_PASSWORD = "Demo-Seed-Password-2026!"
EMAIL_DOMAIN = "example.org"

# (username, first name, last name, groups, enabled, temporary password)
USERS = [
    ("nina.nurse",      "Nina",  "Demo", ["/Nursing"],     True,  False),
    ("paul.physician",  "Paul",  "Demo", ["/Medicine"],    True,  False),
    ("sam.scheduler",   "Sam",   "Demo", ["/Front Desk"],  True,  False),
    ("rita.reports",    "Rita",  "Demo", ["/Analytics"],   True,  False),
    ("carl.compliance", "Carl",  "Demo", ["/Compliance"],  True,  False),
    ("ivy.it",          "Ivy",   "Demo", ["/IT"],          True,  False),
    # Exercises the first-login path (forced password change).
    ("new.hire",        "Noor",  "Demo", ["/Nursing"],     True,  True),
    # Authenticates but has no roles; should be denied by every application.
    ("no.group",        "Nolan", "Demo", [],               True,  False),
    # Disabled account that still has a group; models an offboarded user.
    ("former.employee", "Fred",  "Demo", ["/Nursing"],     False, False),
]


def build_user(default_role, username, first, last, groups, enabled, temporary):
    user = {
        "username": username,
        "enabled": enabled,
        "emailVerified": True,
        "firstName": first,
        "lastName": last,
        "email": f"{username}@{EMAIL_DOMAIN}",
        "credentials": [
            {"type": "password", "value": SEED_PASSWORD, "temporary": temporary}
        ],
        "groups": groups,
        # Imported users do not receive the realm's default role automatically.
        # It carries the account permissions (view-profile, manage-account).
        "realmRoles": [default_role],
    }
    if temporary:
        user["requiredActions"] = ["UPDATE_PASSWORD"]
    return user


def main(path):
    with open(path, encoding="utf-8") as f:
        realm = json.load(f)

    existing = {g.get("name") for g in realm.get("groups", [])}
    needed = {g.lstrip("/") for u in USERS for g in u[3]}
    missing = sorted(needed - existing)
    if missing:
        sys.exit(f"Error: groups missing from the realm export: {', '.join(missing)}")

    default_role = f"default-roles-{realm['realm']}"
    realm["users"] = [build_user(default_role, *u) for u in USERS]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(realm, f, indent=2)
        f.write("\n")
    print(f"Wrote {len(USERS)} users into {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
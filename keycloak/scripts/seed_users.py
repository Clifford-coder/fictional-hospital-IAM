#!/usr/bin/env python3
"""Add the group-to-role mappings and fictional seed users to a realm export, in place.

Keycloak's partial export leaves users out, and a re-export cannot be relied on to
carry the group role mappings, so this script writes both into the realm file:

  * each department group gets its realm role (the access-control design), and
  * the project's fictional users are added.

It is safe to re-run: the mappings and the "users" list are replaced each time.

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


# Access is granted through groups: each department group carries one realm role.
GROUP_ROLES = {
    "Nursing": "nurse",
    "Medicine": "physician",
    "Front Desk": "scheduler",
    "Analytics": "report-analyst",
    "Compliance": "compliance-auditor",
    "IT": "it-admin",
}


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

    groups = {g.get("name"): g for g in realm.get("groups", [])}
    needed = set(GROUP_ROLES) | {g.lstrip("/") for u in USERS for g in u[3]}
    missing = sorted(needed - set(groups))
    if missing:
        sys.exit(f"Error: groups missing from the realm export: {', '.join(missing)}")

    roles = {r.get("name") for r in realm.get("roles", {}).get("realm", [])}
    missing = sorted(set(GROUP_ROLES.values()) - roles)
    if missing:
        sys.exit(f"Error: realm roles missing from the realm export: {', '.join(missing)}")

    for group_name, role in GROUP_ROLES.items():
        groups[group_name]["realmRoles"] = [role]

    default_role = f"default-roles-{realm['realm']}"
    realm["users"] = [build_user(default_role, *u) for u in USERS]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(realm, f, indent=2)
        f.write("\n")
    print(f"Wrote {len(GROUP_ROLES)} group role mappings and {len(USERS)} users into {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
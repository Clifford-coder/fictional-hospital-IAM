#!/usr/bin/env python3
"""One-time split: move the fictional demo users out of the realm file.

Part 2, Phase 1. The realm file should hold only what an IT department defines
once (roles, groups and their role mappings, clients, the authentication flow,
policies, event settings). The nine fictional users, and the shared demo password
that came with them, move to keycloak/demo/demo_users.json, which contains no
passwords at all. keycloak/demo/load_demo_users.py creates the users in a running
Keycloak and takes the password from the environment at that moment.

Usage:
    python3 keycloak/scripts/split_demo_users.py keycloak/realm/hospital-realm.json \
        keycloak/demo/demo_users.json

Safe to re-run: if the realm file already has no users and the demo file exists,
it reports that and changes nothing. It refuses to run if the realm file does not
contain exactly the nine expected usernames, so it cannot discard users it does
not know about.
"""
import json
import sys

EXPECTED = {
    "nina.nurse", "paul.physician", "sam.scheduler", "rita.reports",
    "carl.compliance", "ivy.it", "new.hire", "no.group", "former.employee",
}

NOTES = {
    "new.hire": "A new employee: the temporary password forces a password change and authenticator enrollment at first sign-in.",
    "no.group": "Authenticates but has no group and therefore no job role; every application should deny this user.",
    "former.employee": "Disabled account that still has a group; models an offboarded user. Sign-in must fail.",
}


def main(realm_path, demo_path):
    with open(realm_path, encoding="utf-8") as f:
        realm = json.load(f)

    users = realm.get("users", [])
    if not users:
        print("The realm file already has no users; nothing to do.")
        return

    found = {u["username"] for u in users}
    if found != EXPECTED:
        sys.exit("Refusing to split: the realm file's users are not the expected nine.\n"
                 f"  unexpected: {sorted(found - EXPECTED)}\n  missing:    {sorted(EXPECTED - found)}")

    demo_users = []
    for u in users:
        entry = {
            "username": u["username"],
            "firstName": u["firstName"],
            "lastName": u["lastName"],
            "email": u["email"],
            "enabled": u["enabled"],
            "groups": u.get("groups", []),
        }
        if u["username"] in NOTES:
            entry["note"] = NOTES[u["username"]]
        demo_users.append(entry)

    demo = {
        "description": ("Fictional demo users. No passwords are stored here: "
                        "load_demo_users.py sets every password from DEMO_USER_PASSWORD "
                        "at load time and marks it temporary."),
        "users": demo_users,
    }
    with open(demo_path, "w", encoding="utf-8") as f:
        json.dump(demo, f, indent=2)
        f.write("\n")

    del realm["users"]
    with open(realm_path, "w", encoding="utf-8") as f:
        json.dump(realm, f, indent=2)
        f.write("\n")
    print(f"Moved {len(demo_users)} users to {demo_path} (without passwords) and removed them from {realm_path}.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])

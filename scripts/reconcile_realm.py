#!/usr/bin/env python3
"""Align hospital-realm.json with the values the Part 1 documents state.

Documented (README, build-process.md, testing-guide.md):
    SSO session idle 15 min, SSO session max 12 h, password history 5
Found in the realm file:
    ssoSessionIdleTimeout 1800 (30 min), ssoSessionMaxLifespan 36000 (10 h), passwordHistory(3)

Refuses to change anything unless the file holds exactly the values it expects
(or already holds the new ones), so it can never silently overwrite a value
you changed on purpose. Safe to re-run.

Usage: python3 scripts/reconcile_realm.py keycloak/realm/hospital-realm.json
"""
import json
import sys

# (key, value found, value wanted)
CHANGES = [
    ("ssoSessionIdleTimeout", 1800, 900),     # seconds: 30 min -> 15 min
    ("ssoSessionMaxLifespan", 36000, 43200),  # seconds: 10 h -> 12 h
]
POLICY_OLD, POLICY_NEW = "passwordHistory(3)", "passwordHistory(5)"


def main(path):
    with open(path, encoding="utf-8") as f:
        realm = json.load(f)

    for key, old, new in CHANGES:
        if realm.get(key) == new:
            print(f"  already {new}: {key}")
        elif realm.get(key) == old:
            realm[key] = new
            print(f"  {key}: {old} -> {new}")
        else:
            sys.exit(f"Error: {key} is {realm.get(key)!r}, expected {old} or {new}. Not changing anything.")

    policy = realm.get("passwordPolicy", "")
    if POLICY_NEW in policy:
        print(f"  already {POLICY_NEW}: passwordPolicy")
    elif POLICY_OLD in policy:
        realm["passwordPolicy"] = policy.replace(POLICY_OLD, POLICY_NEW)
        print(f"  passwordPolicy: {POLICY_OLD} -> {POLICY_NEW}")
    else:
        sys.exit(f"Error: passwordPolicy is {policy!r}; expected it to contain {POLICY_OLD} or {POLICY_NEW}.")

    with open(path, "w", encoding="utf-8") as f:   # same format the seed scripts write
        json.dump(realm, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])

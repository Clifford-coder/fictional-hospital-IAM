#!/usr/bin/env python3
"""Write the group-to-role mappings into a realm export, in place.

Keycloak's partial export cannot be relied on to carry the group role mappings,
so this script writes them into the realm file. Access is granted through groups:
each department group carries one realm role.

(Part 1 called this seed_users.py and also wrote the fictional users and a shared
password into the file. From Part 2, Phase 1 the users live in keycloak/demo/ and
are loaded separately; this script only writes the mappings and makes sure no
"users" list remains in the realm file.)

Usage:
    python3 keycloak/scripts/seed_group_roles.py keycloak/realm/hospital-realm.json

Safe to re-run.
"""
import json
import sys

GROUP_ROLES = {
    "Nursing": "nurse",
    "Medicine": "physician",
    "Front Desk": "scheduler",
    "Analytics": "report-analyst",
    "Compliance": "compliance-auditor",
    "IT": "it-admin",
}


def main(path):
    with open(path, encoding="utf-8") as f:
        realm = json.load(f)

    groups = {g.get("name"): g for g in realm.get("groups", [])}
    missing = sorted(set(GROUP_ROLES) - set(groups))
    if missing:
        sys.exit(f"Error: groups missing from the realm export: {', '.join(missing)}")

    roles = {r.get("name") for r in realm.get("roles", {}).get("realm", [])}
    missing = sorted(set(GROUP_ROLES.values()) - roles)
    if missing:
        sys.exit(f"Error: realm roles missing from the realm export: {', '.join(missing)}")

    for group_name, role in GROUP_ROLES.items():
        groups[group_name]["realmRoles"] = [role]

    removed = realm.pop("users", None)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(realm, f, indent=2)
        f.write("\n")
    print(f"Wrote {len(GROUP_ROLES)} group role mappings into {path}"
          + (f" and removed {len(removed)} users" if removed else ""))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])

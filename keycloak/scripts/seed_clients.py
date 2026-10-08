#!/usr/bin/env python3
"""Add the sample-application OIDC clients to a Keycloak realm export, in place.

Defines one confidential OpenID Connect client per sample application and writes
them into the exported realm file. Client secrets are NOT written to the file:
each is a ${PLACEHOLDER} that Keycloak resolves from an environment variable
when it imports the realm at startup. Safe to re-run: existing clients with the
same clientId are replaced.

Usage:
    python3 keycloak/scripts/seed_clients.py keycloak/realm/hospital-realm.json
    python3 keycloak/scripts/seed_clients.py keycloak/realm/hospital-realm.json \
        --base-url http://localhost:5050
"""
import argparse
import json
import sys

DEFAULT_BASE_URL = "http://localhost:5050"

# (clientId, display name, URL path prefix, secret environment variable)
CLIENTS = [
    ("ehr-demo",       "EHR (demo)",                       "ehr",       "EHR_CLIENT_SECRET"),
    ("wiki-demo",      "Internal wiki (demo)",             "wiki",      "WIKI_CLIENT_SECRET"),
    ("dashboard-demo", "Scheduling/reporting dashboard (demo)", "dashboard", "DASHBOARD_CLIENT_SECRET"),
]

DEFAULT_SCOPES = ["basic", "acr", "profile", "roles", "email", "web-origins"]
OPTIONAL_SCOPES = ["address", "phone", "offline_access", "microprofile-jwt"]


def build_client(client_id, name, prefix, secret_env, base_url):
    return {
        "clientId": client_id,
        "name": name,
        "enabled": True,
        "protocol": "openid-connect",
        "clientAuthenticatorType": "client-secret",
        "secret": "${" + secret_env + "}",
        "publicClient": False,
        "standardFlowEnabled": True,
        "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False,
        "fullScopeAllowed": True,
        "rootUrl": base_url,
        "baseUrl": f"/{prefix}/",
        "redirectUris": [f"{base_url}/{prefix}/callback"],
        "webOrigins": [],
        "attributes": {
            "pkce.code.challenge.method": "S256",
            "post.logout.redirect.uris": f"{base_url}/",
        },
        "defaultClientScopes": DEFAULT_SCOPES,
        "optionalClientScopes": OPTIONAL_SCOPES,
        # Puts the user's realm roles into a flat "roles" claim, in the ID
        # token as well as the access token, so the application can read them.
        "protocolMappers": [
            {
                "name": "hospital-roles",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-realm-role-mapper",
                "consentRequired": False,
                "config": {
                    "claim.name": "roles",
                    "multivalued": "true",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true",
                },
            }
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("realm_file")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"public base URL of the sample app (default {DEFAULT_BASE_URL})")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    with open(args.realm_file, encoding="utf-8") as f:
        realm = json.load(f)

    known = {s.get("name") for s in realm.get("clientScopes", [])}
    if known:
        missing = sorted(set(DEFAULT_SCOPES + OPTIONAL_SCOPES) - known)
        if missing:
            sys.exit(f"Error: client scopes missing from the realm export: {', '.join(missing)}")

    ids = {c[0] for c in CLIENTS}
    kept = [c for c in realm.get("clients", []) if c.get("clientId") not in ids]
    realm["clients"] = kept + [build_client(*c, base_url) for c in CLIENTS]

    with open(args.realm_file, "w", encoding="utf-8") as f:
        json.dump(realm, f, indent=2)
        f.write("\n")
    print(f"Wrote {len(CLIENTS)} clients into {args.realm_file} (base URL {base_url})")


if __name__ == "__main__":
    main()

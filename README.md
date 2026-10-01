# Hospital IAM (Keycloak)

A centralized identity and access management (IAM) system for a **fictional**
hospital, built on the official Keycloak container image. It replaces three
separate internal logins (an electronic health records system, an internal
wiki, and a scheduling/reporting dashboard) with a single identity provider, so
IT has one place to enforce password policy and multi-factor authentication
(MFA), and one step to revoke a staff member's access when they leave or change
roles.

## Project scope

- Custom Keycloak image built from the official base image
- Custom realm with hospital roles (Nurse, Physician, and others)
- TOTP-based MFA
- OpenID Connect (OIDC) single sign-on (SSO) demonstrated with sample apps
- Final deployment as separate containers: Keycloak, PostgreSQL, sample app,
  and an nginx reverse proxy handling TLS
- Documentation: image build process, role/permission matrix, onboarding and
  offboarding runbooks, backup/restore, Keycloak upgrade procedure, and a
  mapping of design decisions (MFA, audit logging, RBAC) to HIPAA-style
  access-control and audit requirements

## About the sample applications

The three "applications" (EHR, wiki, scheduling/reporting dashboard) are
**proof-of-concept stand-ins, not real software.** They exist only to show that
Keycloak's login, role enforcement, and single sign-on work end to end.

- They are deliberately thin: a handful of role-gated pages each.
- Any "records" they display are hard-coded, obviously fictional placeholders.
- They have no database of their own. PostgreSQL in this project stores
  Keycloak's identity data only.
- They are **not** an EHR, a wiki, or a scheduling system, and nothing here is
  suitable for handling real clinical workflows.

## Data policy

All users, roles, and records in this project are fictional. Names are
obviously fake, email addresses use `example.org`, and no real person or
patient data is ever used or stored here.

## Pinned versions

| Component | Version |
|---|---|
| Keycloak | 26.7.4 (`quay.io/keycloak/keycloak:26.7.4`) |
| Docker | 29.7.2 |

Images are always referenced by exact tag, never `latest`.

## Repository layout

```
hospital-iam/
  keycloak/        Dockerfile and realm/hospital-realm.json
  app/             proof-of-concept sample application(s)
  docs/            project documentation (see docs/build-process.md)
  .env.example     placeholder values only; real .env is git-ignored
  README.md
```

## Secrets

Real credentials live only in a local `.env` file, which is git-ignored. Never
commit secrets, private keys, or real client secrets.
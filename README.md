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

- One small Flask program serves all three under `/ehr`, `/wiki`, and
  `/dashboard`, and each is registered as its own OpenID Connect client.
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
| Sample app dependencies | Pinned in `app/requirements.txt` (Flask 3.1.3, Authlib 1.6.12); Python 3.9 or newer |

Images are always referenced by exact tag, never `latest`.

## Repository layout

```
hospital-iam/
  keycloak/        Dockerfile, realm/hospital-realm.json,
                   scripts/seed_users.py, scripts/seed_clients.py
  app/             app.py, requirements.txt (proof-of-concept sample apps)
  docs/            build-process.md, role-matrix.md
  .env.example     placeholder values only; real .env is git-ignored
  README.md
```

## Quick start

Prerequisites: Docker, and Python 3.9 or newer.

**1. Configure.** Copy the example file and replace every `change-me` value in
`.env`. Generate each secret with `openssl rand -hex 24`.

```bash
cp .env.example .env
```

**2. Start Keycloak.**

```bash
docker build -t hospital-iam-keycloak:0.4.1 ./keycloak
docker run --rm --name iam -p 8080:8080 -p 9000:9000 \
  --env-file .env hospital-iam-keycloak:0.4.1
```

**3. Start the sample applications** in a second terminal.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
python app/app.py
```

- Sample applications: http://localhost:5050 (use `localhost`, not `127.0.0.1`)
- Admin console: http://localhost:8080 (credentials from `.env`)
- Hospital user sign-in: http://localhost:8080/realms/hospital/account
- Health check: http://localhost:9000/health/ready

The `hospital` realm, its fictional users, and the three application clients are
imported automatically on startup. Hospital users must enroll an authenticator
app (TOTP) at first sign-in. This runs Keycloak in development mode for local
use only, and data, including authenticator enrollments, is discarded when the
container stops. See `docs/build-process.md` for how the image is built.

## Hospital realm

Access is granted through groups, and each group carries one realm role.

| Group | Role |
|---|---|
| Nursing | `nurse` |
| Medicine | `physician` |
| Front Desk | `scheduler` |
| Analytics | `report-analyst` |
| Compliance | `compliance-auditor` |
| IT | `it-admin` |

`keycloak/scripts/seed_users.py` writes the group-to-role mappings and nine
fictional users into the realm file, including one with no group and one
disabled account for testing. Their shared demo password is defined in that
script and is for local development only. The access each role has, and how the
sample applications enforce it, is in `docs/role-matrix.md`.

## Security configuration

| Control | Setting |
|---|---|
| Password policy | Minimum 14 characters; not username or email; last 5 passwords remembered |
| Multi-factor authentication | TOTP required for every hospital user; users without a device must enroll at login |
| Brute-force protection | Temporary lockout after 5 failed logins |
| Sessions | 15-minute idle timeout, 12-hour maximum; 5-minute access tokens |
| Single sign-on | OpenID Connect authorization code flow with PKCE; one confidential client per application |
| Authorization | Roles granted through groups only; enforced server-side by each application |
| Client secrets | Supplied from the environment at startup; never stored in the repository |

Details and reasoning are in `docs/build-process.md`.

## Secrets

Real credentials live only in a local `.env` file, which is git-ignored. Never
commit secrets, private keys, or real client secrets.
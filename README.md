# Hospital IAM (Keycloak)

A centralized identity and access management (IAM) system for a **fictional**
hospital, built on the official Keycloak container image. It replaces three
separate internal logins (an electronic health records system, an internal
wiki, and a scheduling/reporting dashboard) with a single identity provider, so
IT has one place to enforce password policy and multi-factor authentication
(MFA), and one step to revoke a staff member's access when they leave or change
roles.

## Project scope

**Included in this repository**

- Custom Keycloak image built from the official base image
- Custom realm with hospital roles (Nurse, Physician, and others), assigned
  through groups
- Password policy, brute-force protection, and mandatory TOTP-based MFA
- OpenID Connect (OIDC) single sign-on (SSO) across three sample applications,
  with role-based access enforced in each
- Audit logging of user and administrator events
- Documentation: image build process and the role/permission matrix

**Part 2: Kubernetes deployment (in progress, branch `part2`)**

- Final deployment as separate workloads on a local Kubernetes (kind) cluster:
  Keycloak, PostgreSQL, the sample applications, and an nginx reverse proxy
  handling TLS
- Documentation still to come: onboarding and offboarding runbooks,
  backup/restore, Keycloak upgrade procedure, and a mapping of design decisions
  (MFA, audit logging, RBAC) to HIPAA-style access-control and audit
  requirements

## Status

| Part | State |
|---|---|
| Part 1: single Keycloak container, realm, MFA, SSO, audit events | Complete (Git tag `part1-complete`) |
| Part 2, Phase 0: pinned versions, realm aligned with the documents, workstation checks | Complete |
| Part 2, Phase 1: optimized Keycloak image, containerized sample app, demo users separated from the realm | Complete |
| Part 2, later phases: cluster, database, TLS proxy, runbooks | Not started |

The Part 1 quick start below builds Part 1 as tagged (`git checkout part1-complete`).
The current images are run as described under "Running the Phase 1 images". Part 2
changes are recorded in `docs/build-process.md` under "Part 2: Kubernetes
deployment".

## About the sample applications

The three "applications" (EHR, wiki, scheduling/reporting dashboard) are
**proof-of-concept stand-ins, not real software.** They exist only to show that
Keycloak's login, role enforcement, and single sign-on work end to end.

- One small Flask program serves all three under `/ehr`, `/wiki`, and
  `/dashboard`, and each is registered as its own OpenID Connect client.
- They are deliberately thin: a handful of role-gated pages each.
- Any "records" they display are hard-coded, obviously fictional placeholders.
- They have no database of their own.
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

**Part 2 pins** are all in one file, `versions.env`, and every image there is
also pinned by digest (`name:tag@sha256:...`) so a moved tag cannot change what
runs.

| Component | Version |
|---|---|
| Keycloak | 26.7.4 (unchanged from Part 1) |
| kind / Kubernetes node image | v0.33.0 / `kindest/node` v1.36.4 |
| Calico (NetworkPolicy enforcement) | v3.33.0 |
| cert-manager | v1.21.3 |
| PostgreSQL | 17.12 |
| nginx (`nginx-unprivileged`, Alpine) | 1.30.6 |
| Python (application image) | 3.13.18 (slim) |
| gunicorn (application image) | 23.0.0 on Python below 3.10, 27.0.1 on 3.10 and above |

Local image tags: `hospital-iam-keycloak:0.6.0` and `hospital-iam-app:0.6.0`.

## Repository layout

```
hospital-iam/
  versions.env     every Part 2 pinned version and local setting
  keycloak/        Dockerfile (optimized, two-stage), .dockerignore,
                   realm/hospital-realm.json (structure only, no users),
                   demo/demo_users.json, demo/load_demo_users.py,
                   scripts/seed_group_roles.py, scripts/seed_clients.py,
                   scripts/split_demo_users.py
  app/             app.py, requirements.txt, Dockerfile, .dockerignore
                   (proof-of-concept sample apps)
  k8s/             cluster/, base/, overlays/local/ (empty until later phases)
  nginx/           reverse proxy configuration (empty until later phases)
  scripts/         preflight.sh, verify_realm.sh, reconcile_realm.py
  docs/            build-process.md, role-matrix.md, testing-guide.md,
                   runbooks/ (empty until later phases)
  .env.example     variable names only, no values; real .env is git-ignored
  README.md
```

## Quick start (Part 1, tag `part1-complete`)

These steps build and run the single-container Part 1 system. They work on the
`part1-complete` tag, not on branch `part2`, where the Keycloak image is no longer in
development mode and the realm file holds no users.

Prerequisites: Docker, and Python 3.9 or newer.

**1. Configure.** Copy the example file, then give every variable in `.env` a
value: choose an admin password, and generate each secret with
`openssl rand -hex 24`. Use no quotation marks around the values. The sample
applications refuse to start while any of their secrets is empty.

```bash
cp .env.example .env
```

**2. Start Keycloak.**

```bash
docker build -t hospital-iam-keycloak:0.5.0 ./keycloak
docker run --rm --name iam -p 8080:8080 -p 9000:9000 \
  --env-file .env hospital-iam-keycloak:0.5.0
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
- Audit events: `docker logs iam 2>&1 | grep "org.keycloak.events"`

The `hospital` realm, its fictional users, and the three application clients are
imported automatically on startup. Hospital users must enroll an authenticator
app (TOTP) at first sign-in. This runs Keycloak in development mode for local
use only, and data, including authenticator enrollments, is discarded when the
container stops. See `docs/build-process.md` for how the image is built.

## Running the Phase 1 images (branch `part2`)

Prerequisites: Docker, Python 3.9 or newer (for the loader script), and a `.env` in
which every variable has a value (see "Secrets"). Load the pinned versions and the
secrets in every new terminal:

```bash
set -a; . ./versions.env; . ./.env; set +a
```

**1. Build the images.**

```bash
docker build -t hospital-iam-keycloak:0.6.0 ./keycloak
docker build -t hospital-iam-app:0.6.0 ./app
```

**2. Start PostgreSQL and Keycloak** on a shared network.

```bash
export KC_DB_PASSWORD="$KEYCLOAK_DB_PASSWORD"
docker network create iam-net

docker run -d --name pg --network iam-net \
  -e POSTGRES_USER=keycloak -e POSTGRES_DB=keycloak -e POSTGRES_PASSWORD="$KEYCLOAK_DB_PASSWORD" \
  "$POSTGRES_IMAGE"
until [ "$(docker logs pg 2>&1 | grep -c 'ready to accept connections')" -ge 2 ]; do sleep 2; done

docker run -d --name keycloak --network iam-net -p 8080:8080 -p 9000:9000 \
  -e KC_DB_URL=jdbc:postgresql://pg:5432/keycloak -e KC_DB_USERNAME=keycloak -e KC_DB_PASSWORD \
  -e KC_HOSTNAME=http://localhost:8080 -e KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true -e KC_HTTP_ENABLED=true \
  -e KC_BOOTSTRAP_ADMIN_USERNAME -e KC_BOOTSTRAP_ADMIN_PASSWORD \
  -e EHR_CLIENT_SECRET -e WIKI_CLIENT_SECRET -e DASHBOARD_CLIENT_SECRET \
  hospital-iam-keycloak:0.6.0
until curl -fs http://localhost:9000/health/ready >/dev/null; do sleep 3; done
```

**3. Load the fictional users, then start the sample applications.**

```bash
python3 keycloak/demo/load_demo_users.py

docker run -d --name app --network iam-net -p 5050:5050 \
  -e KEYCLOAK_ISSUER=http://localhost:8080/realms/hospital \
  -e KEYCLOAK_DISCOVERY_URL=http://keycloak:8080/realms/hospital/.well-known/openid-configuration \
  -e APP_BASE_URL=http://localhost:5050 \
  -e APP_SECRET_KEY -e EHR_CLIENT_SECRET -e WIKI_CLIENT_SECRET -e DASHBOARD_CLIENT_SECRET \
  hospital-iam-app:0.6.0
```

- Sample applications: http://localhost:5050 (use `localhost`, not `127.0.0.1`)
- Admin console: http://localhost:8080 (credentials from `.env`)
- Hospital user sign-in: http://localhost:8080/realms/hospital/account
- Health check: http://localhost:9000/health/ready
- Realm settings as the server reports them: `bash scripts/verify_realm.sh`
- Audit events: `docker logs keycloak 2>&1 | grep "org.keycloak.events"`

Each demo user starts with the password from `DEMO_USER_PASSWORD`, marked temporary:
the first sign-in forces enrollment of an authenticator app (TOTP) and a new password.

**To stop and start over**, remove the containers and the network. This also discards
the database, so all enrollments and password changes are lost:

```bash
docker rm -f app keycloak pg
docker network rm iam-net
```

The `part2` images are production-shaped: Keycloak runs with `start --optimized`
against PostgreSQL, and the application runs under gunicorn as a non-root user. They
are served over plain HTTP on `localhost` until the TLS proxy is added in a later phase.

## Part 2 workstation checks

Part 2 adds two scripts. Both are run from the repository root.

```bash
bash scripts/preflight.sh
```

Read-only. Checks the Git branch and tag, that `.env` is git-ignored, the realm
values against `versions.env`, the installed tools (Python, OpenSSL, Docker,
kubectl, kind), Docker's memory, that `iam.hospital.test`, `apps.hospital.test`
and `iam-admin.hospital.test` resolve to `127.0.0.1` (add them to `/etc/hosts`),
and that host ports 443 and 80 are free. It exits with an error if a check
fails.

```bash
set -a; . ./.env; set +a
bash scripts/verify_realm.sh
```

With the Keycloak container from the quick start running, signs in as the admin
and prints the realm's session and password settings as the server reports them.
If the sign-in is refused, the script prints Keycloak's reason.

## Testing

`docs/testing-guide.md` is a step-by-step walkthrough for trying out the system as
run in "Running the Phase 1 images": the accounts to use, what to look at in the admin
console, and ten short tests with expected results.

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

`keycloak/scripts/seed_group_roles.py` writes the group-to-role mappings into the
realm file. The realm file holds no users. The nine fictional users, including one
with no group and one disabled account for testing, are listed without passwords in
`keycloak/demo/demo_users.json` and are created in a running Keycloak by
`keycloak/demo/load_demo_users.py`. That script sets every user's password from
`DEMO_USER_PASSWORD` in `.env` and marks it temporary, so no shared password is stored
in the repository or in an image. The access each role has, and how the sample
applications enforce it, is in `docs/role-matrix.md`.

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
| Audit logging | User and admin events saved and written to the server log, including successful sign-ins |
| Demo users | Not in the realm file or any image; created at load time with a temporary password taken from the environment |

Details and reasoning are in `docs/build-process.md`.

## Secrets

Real credentials live only in a local `.env` file, which is git-ignored.

Keep every password in `.env` to letters and digits, and make it long (20
characters or more). The shell command `. ./.env` and `docker --env-file` read
special characters differently, so a password containing `$`, `!`, `#`, `&`,
quotes, or similar can work in one place and be rejected in the other.
`.env.example` also lists three Part 2 variables: `DEMO_USER_PASSWORD` (the temporary
password the loader gives every demo user, at least 14 characters), `KEYCLOAK_DB_PASSWORD`
(the database password used by PostgreSQL and Keycloak), and `POSTGRES_PASSWORD`
(used once the cluster is built).

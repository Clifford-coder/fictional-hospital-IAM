# Build Process

How the Hospital IAM image and environment were built. This document is
extended as each part of the project is completed, and each phase section records
the state of the project at the end of that phase.

> **Data policy:** everything in this project is fictional. No real person or
> patient data is used anywhere.

---

## Phase 0: Workspace and guardrails

### Goal

Establish a clean, reproducible working area and a pinned Keycloak version
before writing any configuration.

### Environment

| Item | Value |
|---|---|
| Date | 2026-10-01 |
| Host OS | macOS 26.5.2 |
| Docker | 29.7.2 |
| Keycloak (pinned) | 26.7.4 |

### Decisions

**1. Base image: official Keycloak image, pinned to an exact tag.**
The image is `quay.io/keycloak/keycloak:26.7.4`. Keycloak publishes its
official container image on Quay.io. The older `jboss/keycloak` image on Docker
Hub is legacy and is not used.

- *Why pinned:* an exact tag makes builds reproducible, and it turns a future
  upgrade into a deliberate, reviewable change to a single line rather than a
  surprise from `latest`.
- *Why 26.7.4:* it was the latest stable release as of 2026-10-01. The tag was
  verified by pulling the image and confirming the version it reports.
- *Admin bootstrap:* Keycloak 26 and later use `KC_BOOTSTRAP_ADMIN_USERNAME`
  and `KC_BOOTSTRAP_ADMIN_PASSWORD` for the initial admin account.

**2. Secrets stay out of Git and out of image layers.**
Real values live in a local `.env` file that is git-ignored. The repository
holds only `.env.example` with placeholders, and admin credentials are supplied
at container run time rather than baked into an image.

**3. Fictional data only.**
Names are obviously fake, email addresses use `example.org`, and no real person
or patient data is used anywhere. The rule is stated in the README.

**4. Sample applications are proof-of-concept stand-ins.**
The EHR, wiki, and dashboard are deliberately thin applications with hard-coded
fictional records and no database of their own. They exist to demonstrate OpenID
Connect login, role enforcement, and single sign-on, not to be real clinical
software.

**5. Repository layout.**
Chosen so later phases (realm configuration, sample apps, multi-container
deployment, runbooks) fit without rearranging.

```
hospital-iam/
  keycloak/        Dockerfile, realm/hospital-realm.json, scripts/seed_users.py
  app/             proof-of-concept sample application(s)
  docs/            build-process.md, role-matrix.md
  .env.example     placeholder values only; real .env is git-ignored
  README.md
```

---

## Phase 1: Custom Keycloak image

### Goal

Build a custom image on top of the pinned official Keycloak base, run it, and
confirm it is healthy. This version runs in development mode, which allows plain
HTTP and an embedded database, and is intended for local development only.

### Dockerfile (`keycloak/Dockerfile`)

```dockerfile
FROM quay.io/keycloak/keycloak:26.7.4

ENV KC_HEALTH_ENABLED=true

CMD ["start-dev"]
```

| Instruction | Purpose |
|---|---|
| `FROM quay.io/keycloak/keycloak:26.7.4` | Starts from the official image at the exact pinned version. |
| `ENV KC_HEALTH_ENABLED=true` | Enables Keycloak's health endpoints. In current releases these are served on the management port (9000), separate from the application port (8080). |
| `CMD ["start-dev"]` | Default argument passed to the base image's Keycloak launcher. Dev mode allows plain HTTP and uses an embedded throwaway database, which suits local development only. |

The base image already defines the entrypoint (Keycloak's launcher script), so
the Dockerfile supplies only the command argument.

### Build and run

Admin credentials are not stored in the image. They are supplied at run time
from a local, git-ignored `.env` file (created from `.env.example`):

```bash
cp .env.example .env        # then set a local admin password in .env

docker build -t hospital-iam-keycloak:0.1.0 ./keycloak

docker run --rm --name iam -p 8080:8080 -p 9000:9000 \
  --env-file .env hospital-iam-keycloak:0.1.0
```

- Port 8080 serves the admin console and realm endpoints.
- Port 9000 serves the management interface (health endpoints).
- `--rm` removes the container on exit. In dev mode all data is discarded with
  it, which is intentional at this stage: configuration is meant to be
  recreated from files in the repository, not from container state.
- Passing credentials with `--env-file` at run time keeps secrets out of the
  image layers.

### Verification

| Check | Command or action | Observed result |
|---|---|---|
| Admin console reachable | Open `http://localhost:8080` | Redirects to the Keycloak admin login page |
| Admin login works | Sign in with the credentials from `.env` | Redirects to `http://localhost:8080/admin/master/console/` |
| Management interface | Open `http://localhost:9000/` | Shows the Keycloak Management Interface listing the `/health` endpoint |
| Readiness | `curl -s http://localhost:9000/health/ready` | `status: UP`, with `Graceful Shutdown` and `Keycloak Initialized` checks both UP |
| OIDC discovery | `curl -s http://localhost:8080/realms/master/.well-known/openid-configuration` | JSON document with issuer `http://localhost:8080/realms/master` and the authorization, token, and introspection endpoints |

The discovery document is the same mechanism the sample applications use later
to learn Keycloak's endpoints, so a valid response here confirms the OpenID
Connect layer is working.

### Limitations of this build

- Dev mode only: plain HTTP, embedded database, not suitable for production.
- No realm configuration is included. The image starts with Keycloak's default
  `master` realm only.

---

## Phase 2: Hospital realm

### Goal

Model the hospital's access structure in a dedicated realm and capture it in
files, so the same realm is recreated identically every time the image starts.

### Design

**Realm.** A realm named `hospital` (display name "Hospital IAM (Fictional)")
holds all staff identities. The built-in `master` realm is used only to
administer Keycloak.

**Roles are granted through groups only.** No role is assigned directly to a
user. Each department group carries one realm role, so a single group change
grants or removes a person's access, and access can be reviewed by reading group
membership.

| Group | Realm role | Description |
|---|---|---|
| Nursing | `nurse` | Clinical nursing staff |
| Medicine | `physician` | Physicians |
| Front Desk | `scheduler` | Scheduling and front-desk staff |
| Analytics | `report-analyst` | Reporting and analytics staff |
| Compliance | `compliance-auditor` | Compliance and audit staff |
| IT | `it-admin` | IT administrators |

All roles are realm roles. No client roles are defined at this stage. The
intended access for each role is recorded in `role-matrix.md`.

**Fictional seed users.** Nine users, all with `example.org` addresses:

| Username | Group | Purpose |
|---|---|---|
| `nina.nurse` | Nursing | Nurse role |
| `paul.physician` | Medicine | Physician role |
| `sam.scheduler` | Front Desk | Scheduler role |
| `rita.reports` | Analytics | Report analyst role |
| `carl.compliance` | Compliance | Compliance auditor role |
| `ivy.it` | IT | IT administrator role |
| `new.hire` | Nursing | Temporary password; exercises the forced password change at first login |
| `no.group` | none | Can authenticate but holds no job role; applications should deny this user |
| `former.employee` | Nursing | Disabled account; models an offboarded user who still has a group |

All seeded users share a demo password defined in the seed script. It is
fictional and for local development only.

### Process

**1. Build the structure in the admin console.** Create the `hospital` realm,
then the six realm roles, then the six groups, mapping one role to each group on
the group's Role mapping tab.

**2. Export the realm.** Realm settings > Action > Partial export, with
"Include groups and roles" and "Include clients" enabled. The download is saved
as `keycloak/realm/hospital-realm.json`.

**3. Add the users.** Keycloak's partial export does not include users, so
`keycloak/scripts/seed_users.py` writes them into the exported file:

```bash
python3 keycloak/scripts/seed_users.py keycloak/realm/hospital-realm.json
```

The script replaces the realm's `users` list each run (so it is safe to repeat),
stops with an error if an expected group is missing from the export, and assigns
every user the realm's default role (see "Issue encountered" below). The script
was later extended to write the group role mappings as well (see Phase 4).

**4. Import the realm on startup.** The Dockerfile copies the realm file into
Keycloak's import directory and starts the server with `--import-realm`:

```dockerfile
FROM quay.io/keycloak/keycloak:26.7.4

ENV KC_HEALTH_ENABLED=true

# Realm definition (roles, groups, seeded users), placed where Keycloak looks for imports
COPY realm/hospital-realm.json /opt/keycloak/data/import/hospital-realm.json

# --import-realm imports it on first start (skipped if the realm already exists)
CMD ["start-dev", "--import-realm"]
```

Keycloak imports the file only when the realm does not already exist. Because
the container runs with `--rm` and a throwaway database, every new container
starts from the file.

**5. Build and run.**

```bash
docker build -t hospital-iam-keycloak:0.2.0 ./keycloak

docker run --rm --name iam -p 8080:8080 -p 9000:9000 \
  --env-file .env hospital-iam-keycloak:0.2.0
```

### Issue encountered

The first version of the seed script did not give users the realm's default
role (`default-roles-hospital`). Signing in to the hospital realm's account
console then failed: the token request succeeded, but the account API calls
returned HTTP 401 and the page showed "Something went wrong".

- **Cause:** users created through a realm import do not receive the default
  role automatically. That role carries the `view-profile` and `manage-account`
  permissions the account API requires.
- **Fix:** the seed script now sets `realmRoles` to the realm's default role for
  every user.
- **Note:** administrator sign-in uses the `master` realm, so hospital users
  cannot sign in to the admin console. Hospital users sign in at
  `http://localhost:8080/realms/hospital/account`.

### Verification

| Check | Result |
|---|---|
| A brand-new container starts with the realm, six roles, six groups, and nine users already present | Confirmed |
| Group membership grants the matching role (for example `nina.nurse` inherits `nurse` from Nursing) | Confirmed |
| `no.group` holds no job role | Confirmed |
| `former.employee` (disabled) cannot sign in | Confirmed |
| Enabled users can sign in at the hospital realm's account page | Confirmed |
| `new.hire` is required to change the password at first login | Confirmed |

---

## Phase 3: Password policy and multi-factor authentication

### Goal

Enforce one password policy and mandatory TOTP multi-factor authentication for
every hospital user from a single place, and capture the configuration in the
realm file so it is reproduced on every start.

### Configuration

All settings are in the `hospital` realm.

**Password policy** (Authentication > Policies > Password policy)

| Policy | Value |
|---|---|
| Minimum length | 14 |
| Not username | On |
| Not email | On |
| Password history | 5 |

Length is the strongest lever, so it is set high. Forced periodic expiry and
character-composition rules are deliberately omitted, following NIST SP 800-63B,
which favors length and breached-password screening over composition rules and
scheduled rotation. A breached-password blocklist was not configured because it
requires a file supplied to the container. The seed password (24 characters)
satisfies this policy.

**Brute-force protection** (Realm settings > Security defenses)

| Setting | Value |
|---|---|
| Mode | Lockout temporarily |
| Maximum login failures | 5 |
| Wait increment | 1 minute |
| Maximum wait | 15 minutes |

Temporary lockout was chosen over permanent lockout because permanent lockout
would let anyone who knows a username lock that staff member out of the system.

**OTP policy** (Authentication > Policies > OTP Policy)

| Setting | Value | Reason |
|---|---|---|
| Type | Time-based (TOTP) | Standard authenticator-app mechanism |
| Algorithm | SHA-1 | Supported by the widest range of authenticator apps |
| Digits | 6 | Standard |
| Period | 30 seconds | Standard |
| Look-around window | 1 | Tolerates small clock drift |
| Reusable code | Off | A code is accepted once only |

**Sessions and tokens** (Realm settings > Sessions, Tokens)

| Setting | Value | Reason |
|---|---|---|
| SSO session idle | 15 minutes | Clinical workstations are shared |
| SSO session max | 12 hours | Covers a long shift |
| Access token lifespan | 5 minutes | Shorter lifetime means a revocation takes effect sooner |

### Mandatory OTP authentication flow

Keycloak's built-in browser flow only asks for a one-time code from users who
have already enrolled one, so a user without a device can sign in with a
password alone. To close that gap the built-in flow was duplicated as
`browser-mandatory-otp` and bound as the realm's browser flow. The built-in flow
is left untouched.

In the copy, the **Browser - Conditional 2FA** subflow (inside the `forms`
subflow, after `Username Password Form`) is changed from Conditional to
**Required**, and its `OTP Form` step is **Required**. Result:

- A user who has not enrolled a device is sent to the TOTP setup screen at
  login rather than being let through.
- A user who has enrolled is asked for a code at every login.
- If an administrator deletes a user's OTP credential, that user is sent to
  enroll again at the next login. This is also the recovery path for a lost or
  replaced phone.

The `forms` subflow itself must remain **Alternative**, not Required, or the
`Cookie` step above it is skipped and single sign-on stops working (see
Phase 4, "Issues encountered").

The WebAuthn step in the subflow remains Disabled. Admin-console labels for
flows differ slightly between Keycloak releases, so the structure above is the
reliable description.

An initial attempt used a different structure: disabling the conditional subflow
and adding a separate required `OTP Form` step under the `forms` subflow. In
testing it did not present the OTP prompt, and the cause was not investigated.
The structure above was adopted because it enforced OTP as intended in every
test.

### Process

1. Start the Phase 2 image (`0.2.0`), sign in to the admin console, and
   configure the password policy, brute-force protection, OTP policy, flow, and
   session limits in the `hospital` realm.
2. Test each behavior before exporting (see Verification).
3. Export the realm (Realm settings > Action > Partial export, with groups and
   roles and clients included) over `keycloak/realm/hospital-realm.json`.
4. Re-run the seed script, because the export omits users:

   ```bash
   python3 keycloak/scripts/seed_users.py keycloak/realm/hospital-realm.json
   ```

5. Rebuild and run a fresh container:

   ```bash
   docker build -t hospital-iam-keycloak:0.3.0 ./keycloak

   docker run --rm --name iam -p 8080:8080 -p 9000:9000 \
     --env-file .env hospital-iam-keycloak:0.3.0
   ```

### Verification

Performed first in the running container, then repeated on a fresh container
built from the committed realm file.

| Check | Result |
|---|---|
| First login of a user with no enrolled device (`nina.nurse`) is sent to TOTP setup after the password | Confirmed |
| After enrollment, every login asks for a code | Confirmed |
| A wrong code is rejected | Confirmed |
| A different never-enrolled user (`paul.physician`) is also forced to enroll | Confirmed |
| After an administrator deletes a user's OTP credential, that user is forced to enroll again rather than signing in with a password alone | Confirmed |
| A password that violates the policy is rejected when `new.hire` changes the temporary password | Confirmed |
| Repeated failed logins trigger a temporary lockout | Confirmed |
| Flow binding, policy values, and session settings survive the export and rebuild | Confirmed |

### Notes

- Dev mode discards data when the container stops, including TOTP enrollments.
  Each fresh container requires users to enroll again.
- Enrollment testing used a personal authenticator app with fictional users.

---

## Phase 4: Sample applications with OpenID Connect single sign-on

### Goal

Connect proof-of-concept applications to Keycloak through OpenID Connect, enforce
the role matrix inside them, and show that one sign-in reaches every application.

### Design

**One program, three clients.** A single small Flask program (`app/app.py`) plays
the three hospital systems under separate path prefixes. Each is registered in
Keycloak as its own OpenID Connect client, so signing in to one and opening
another exercises single sign-on exactly as three separate systems would.

| System | Client ID | Path | Redirect URI |
|---|---|---|---|
| EHR (demo) | `ehr-demo` | `/ehr/` | `http://localhost:5050/ehr/callback` |
| Internal wiki (demo) | `wiki-demo` | `/wiki/` | `http://localhost:5050/wiki/callback` |
| Scheduling and reporting dashboard (demo) | `dashboard-demo` | `/dashboard/` | `http://localhost:5050/dashboard/callback` |

The program listens on port 5050 because macOS uses port 5000 for AirPlay
Receiver. It runs directly on the host, not in a container: inside a container
`localhost` refers to the container itself, so the browser-facing and
server-facing Keycloak addresses would not match.

**Client configuration.** `keycloak/scripts/seed_clients.py` writes the clients
into the realm file. Every client is configured identically:

| Setting | Value | Reason |
|---|---|---|
| Client authentication | On (confidential) | The program is a server-side application that can keep a secret |
| Standard flow (authorization code) | On | The login flow in use |
| Proof Key for Code Exchange | Required, S256 | Binds the authorization code to the request that asked for it |
| Direct access grants | Off | Applications must never handle user passwords |
| Implicit flow | Off | Superseded by the code flow |
| Redirect URIs | Exact match, one per client | Prevents redirection to other addresses |
| Post-logout redirect URI | The application's base URL | Allows the end-session redirect |
| Role mapper `hospital-roles` | Realm roles into a flat `roles` claim | Lets the application read roles from the ID token |

**Secrets are not stored in the repository.** The realm file contains
placeholders such as `${EHR_CLIENT_SECRET}`. Keycloak resolves each placeholder
from an environment variable when it imports the realm at startup. The values
live in the local, git-ignored `.env` file, which supplies Keycloak (through
`docker run --env-file`) and the application. `.env.example` lists the variable
names with placeholder values: `EHR_CLIENT_SECRET`, `WIKI_CLIENT_SECRET`,
`DASHBOARD_CLIENT_SECRET`, and `APP_SECRET_KEY`.

**Application behavior.**

- *Authorization is enforced on the server*, from the `roles` claim of the
  validated ID token, never from anything the browser sends. Each page lists the
  roles allowed to open it; others receive HTTP 403. The pages and their roles
  are listed in `role-matrix.md`.
- *Each application keeps its own login session.* Signing in at one application
  does not sign the browser in at another locally. Single sign-on happens at
  Keycloak, which recognizes its own session and returns the browser to the
  second application without asking for credentials.
- *Sessions are held server-side.* The browser cookie holds only a session
  identifier, because three ID tokens would exceed the 4 KB cookie limit. The
  store is in memory, so restarting the program signs everyone out.
- *An application session ends when the ID token expires* (five minutes, the
  realm's token lifespan). Re-authentication is then silent while the Keycloak
  session is valid and refused once it is not. A disabled user or ended Keycloak
  session therefore stops working in each application within about five minutes,
  without any back-channel notification.
- *Sign-out uses OpenID Connect RP-initiated logout.* It ends the Keycloak
  session, so other applications ask for a sign-in once their own sessions
  expire.

All page content is hard-coded and fictional.

### Process

1. **Create the secrets.** Set the four variables listed above in `.env`, each
   generated with `openssl rand -hex 24`. No quotation marks around the values.
2. **Write the clients into the realm file:**

   ```bash
   python3 keycloak/scripts/seed_clients.py keycloak/realm/hospital-realm.json
   ```

   The script replaces any existing copies of the three clients, so it is safe to
   repeat.
3. **Rebuild and run Keycloak:**

   ```bash
   docker build -t hospital-iam-keycloak:0.4.1 ./keycloak

   docker run --rm --name iam -p 8080:8080 -p 9000:9000 \
     --env-file .env hospital-iam-keycloak:0.4.1
   ```

4. **Run the applications** in a second terminal, from the repository root:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r app/requirements.txt
   python app/app.py
   ```

   The dependencies are pinned in `app/requirements.txt` to versions that install
   on Python 3.9 and later (Flask 3.1.3, Authlib 1.6.12).

5. Browse to `http://localhost:5050`. Use `localhost`, not `127.0.0.1`, because
   the application's session cookie is bound to the host name used to start the
   sign-in.

**After any re-export of the realm**, run both seed scripts, in this order,
before rebuilding, because the export omits users and the client definitions are
generated:

```bash
python3 keycloak/scripts/seed_users.py keycloak/realm/hospital-realm.json
python3 keycloak/scripts/seed_clients.py keycloak/realm/hospital-realm.json
```

### Issues encountered

**Dependency versions and Python 3.9.** The first set of pinned versions
included Authlib 1.8.0, which does not install on Python 3.9, the interpreter
on the development machine. The pins were changed to the newest versions that
resolve on Python 3.9 and the application was re-tested against them.

**Every application asked for a sign-in; no single sign-on.** Keycloak held a
valid session (the identity cookies existed and the account console listed the
EHR as in use), but the wiki, the dashboard, the account console, and the EHR's
own renewal all showed the login form.

- *Cause:* in the `browser-mandatory-otp` flow, the top-level `forms` subflow had
  been set to Required. A Required step at that level causes the Alternative
  steps beside it, including `Cookie`, to be skipped, so existing sessions were
  never honored.
- *Fix:* `forms` set to **Alternative**, with its contents unchanged
  (`Username Password Form` Required, `Conditional 2FA` Required, `OTP Form`
  Required). The change is persisted in the realm file.
- *Check:* mandatory TOTP was re-tested afterwards. A user who has never
  enrolled is still forced to enroll, because the OTP step still runs whenever a
  password sign-in actually takes place; the `Cookie` step only lets an existing
  session skip it.

**Roles missing from tokens.** After signing in, the applications showed no job
role. Inspection of `hospital-realm.json` showed every group with an empty role
list, although users and their group memberships were intact, so no role was
inherited from any group.

- *Cause:* the group-to-role mappings were absent from the realm file. Why they
  were lost between the earlier verification and this point was not determined.
- *Fix:* the group-to-role mapping is now defined in `seed_users.py`, which
  writes it into the realm file on every run and stops with an error if a
  required group or role is missing from the export. Access control no longer
  depends on what a console export happens to contain.

### Verification

| Check | Result |
|---|---|
| The three clients are created from the realm file, with secrets supplied from the environment | Confirmed |
| One sign-in (password and authenticator code) reaches all three applications without a further prompt | Confirmed |
| Mandatory TOTP still enforced after the flow correction | Confirmed |
| Roles arrive in the token through group membership alone, with no role assigned directly to a user, on a fresh container | Confirmed |
| For each hospital role, the pages shown as allowed or denied match `role-matrix.md` | Confirmed |
| `no.group` is denied every page | Confirmed |
| `former.employee` (disabled) cannot sign in | Confirmed |

### Limitations

- Keycloak runs in development mode over plain HTTP, and the applications run
  on the host rather than in containers.
- Application sessions are in memory and are lost when the program restarts.
- Authorization is page-level. Row-level limits named in the matrix, such as
  "own unit" or "own patients", are not modeled.
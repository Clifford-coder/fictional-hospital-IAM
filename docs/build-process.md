# Build Process

How the Hospital IAM image and environment were built. This document is
extended as each part of the project is completed, and each phase section records
the state of the project at the end of that phase.

> **Data policy:** everything in this project is fictional. No real person or
> patient data is used anywhere.

> **Structure:** Phases 0 to 5 describe Part 1, a single Keycloak container (Git
> tag `part1-complete`). Part 2, the Kubernetes deployment, starts at the heading
> "Part 2: Kubernetes deployment" near the end of this file, and its phases are
> labelled "Part 2, Phase N".
>
> Part 1 text describes the files as they were at that tag. In particular,
> `seed_users.py` was replaced in Part 2, Phase 1 by `seed_group_roles.py` and the
> demo-user loader.

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
holds only `.env.example`, which lists the variable names without values, and admin credentials are supplied
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
Chosen to keep the image definition, the sample applications, and the
documentation in separate, clearly named places.

```
hospital-iam/
  keycloak/        Dockerfile, realm/hospital-realm.json, scripts/seed_users.py
  app/             proof-of-concept sample application(s)
  docs/            build-process.md, role-matrix.md, testing-guide.md
  .env.example     variable names only, no values; real .env is git-ignored
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
cp .env.example .env        # then give every variable in .env a value

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
names without values: `EHR_CLIENT_SECRET`, `WIKI_CLIENT_SECRET`,
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

---

## Phase 5: Audit logging

### Goal

Record who did what and when, for both ordinary users and administrators, in a
form that can be read in the server log and stored by Keycloak.

### Configuration

| Setting | Value | Reason |
|---|---|---|
| Event listener | `jboss-logging` (enabled by default for the realm) | Writes every event to the server log under the `org.keycloak.events` category, which is what log collection would read |
| Success-event log level | `info` | The listener logs successful events at `debug` by default, which the server's default level hides, so successful sign-ins would be missing from the log |
| User events | Saved, with a short development retention | Keeps sign-ins, failures, and credential changes where an administrator can search them |
| Admin events | Saved, with representation included | Records administrator actions together with the changed object |

Including the representation stores the content of changed objects, which can be
sensitive. That is acceptable here because every record is fictional, and it
would be weighed again for real data.

The log level is set in the Dockerfile. This is the final version:

```dockerfile
FROM quay.io/keycloak/keycloak:26.7.4

ENV KC_HEALTH_ENABLED=true

# Realm definition (roles, groups, seeded users, clients), placed where Keycloak looks for imports
COPY realm/hospital-realm.json /opt/keycloak/data/import/hospital-realm.json

# Dev mode with two additions:
#   --import-realm: import the realm on first start (skipped if it already exists)
#   --spi-events-listener--jboss-logging--success-level=info: also log successful
#     events (logins, logouts), which are hidden at the default debug level
CMD ["start-dev", "--import-realm", "--spi-events-listener--jboss-logging--success-level=info"]
```

### Process

1. In the `hospital` realm, under Realm settings > Events, confirm the
   `jboss-logging` listener, then turn on saving for user events and for admin
   events (with representation).
2. Export the realm over `keycloak/realm/hospital-realm.json` and re-run both seed
   scripts, because the export omits users and the client definitions are
   generated:

   ```bash
   python3 keycloak/scripts/seed_users.py keycloak/realm/hospital-realm.json
   python3 keycloak/scripts/seed_clients.py keycloak/realm/hospital-realm.json
   ```

3. Rebuild and run:

   ```bash
   docker build -t hospital-iam-keycloak:0.5.0 ./keycloak

   docker run --rm --name iam -p 8080:8080 -p 9000:9000 \
     --env-file .env hospital-iam-keycloak:0.5.0
   ```

4. Read the events from the container log:

   ```bash
   docker logs iam 2>&1 | grep "org.keycloak.events"
   ```

### What is recorded

Each action below was performed and found in the log.

| Action | Log entry | Fields that identify it |
|---|---|---|
| Successful sign-in | `LOGIN`, followed by `CODE_TO_TOKEN` | `username`, `clientId`, `sessionId`, `ipAddress`, `redirect_uri` |
| First authenticator enrollment | `UPDATE_TOTP` and `UPDATE_CREDENTIAL`, then `LOGIN` | `credential_type="otp"`, `custom_required_action="CONFIGURE_TOTP"` |
| Wrong password | `LOGIN_ERROR` | `error="invalid_user_credentials"`, `username` |
| Wrong authenticator code | `LOGIN_ERROR` | `error="invalid_user_credentials"` plus `selected_credential_id` |
| Sign-in to a disabled account | `LOGIN_ERROR` | `error="user_disabled"`, `username` |
| Sign-out | `LOGOUT` | `clientId`, `sessionId` |
| Administrator changes a user's group membership | Admin event, `operationType` `CREATE` or `DELETE` | `resourceType="GROUP_MEMBERSHIP"`, `resourcePath`, `username` |
| Administrator disables or enables a user | Admin event, `operationType="UPDATE"` | `resourceType="USER"`, `resourcePath` |
| Session expiry | `USER_SESSION_DELETED` | `reason="user_session_expired"` |

Two entries, trimmed to the fields discussed (identifiers shown as placeholders):

```
WARN  [org.keycloak.events] type="LOGIN_ERROR", realmName="hospital", clientId="wiki-demo", ipAddress="192.168.65.1", error="user_disabled", username="former.employee"

INFO  [org.keycloak.events] operationType="DELETE", realmName="master", resourceType="GROUP_MEMBERSHIP", resourcePath="users/<user-id>/groups/<group-id>", username="nina.nurse"
```

### Observations

- **Password and code failures share an error name.** Both are logged as
  `invalid_user_credentials`. A wrong authenticator code additionally carries a
  `selected_credential_id`, which distinguishes it from a wrong password.
- **Administrator actions show the administrator's realm.** Admin entries report
  `realmName="master"`, because administrators sign in there, and identify the
  affected hospital object by `resourcePath`.
- **The log records that something changed, not what.** The disable and enable
  entries show an `UPDATE` on a user without naming the attribute. The detail is
  held in the stored admin event, which includes the representation.
- **Signing out of one application ends the Keycloak session.** A later sign-out
  from another application in the same browser session was logged as
  `LOGOUT_ERROR` with `error="session_expired"`, consistent with the sign-out
  behavior described in Phase 4.
- **The log covers every realm.** Sign-ins to the admin console (`master`),
  token refreshes, and token exchanges appear alongside hospital events.
- **Source addresses are the Docker network gateway** (`192.168.65.1`), not the
  address of an individual client. Recording real client addresses behind a
  reverse proxy depends on forwarded headers.

### Verification

| Check | Result |
|---|---|
| A successful sign-in is logged at `info` level | Confirmed |
| A wrong password is logged as `LOGIN_ERROR` | Confirmed |
| A wrong authenticator code is logged as `LOGIN_ERROR` | Confirmed |
| An administrator's group-membership changes (add and remove) are logged as admin events | Confirmed |
| An administrator disabling and re-enabling a user is logged, and a sign-in to the disabled account is logged as `user_disabled` | Confirmed |

### Limitations

- In development mode, saved events are discarded when the container stops, and
  the log lasts only as long as the container.
- The log is verbose: token exchanges and token refreshes are recorded for every
  application and for the admin console.
- Admin entries in the log do not carry the detail of what was changed.

---

# Part 2: Kubernetes deployment

Part 1 (Phases 0 to 5 above) is a single Keycloak container in development
mode, tagged `part1-complete` in Git. Part 2 moves the system onto a local
Kubernetes cluster as separate workloads: Keycloak, PostgreSQL, the sample
applications, and an nginx reverse proxy that terminates TLS. Part 2 phases are
numbered from 0 again and are written "Part 2, Phase N" to keep them apart from
the Part 1 phases above.

---

## Part 2, Phase 0: Preparation and guardrails

### Goal

Freeze Part 1, pin every version Part 2 depends on, remove a known mismatch
between the realm file and these documents, and check the workstation, all
before any Kubernetes manifest is written. No cluster is created in this phase.

### Environment

| Item | Value |
|---|---|
| Date | 2026-11-25 |
| Host | macOS on Apple silicon (arm64) |
| Docker | 29.7.2, with 7.7 GB RAM and 11 CPUs available to it |
| kubectl (client) | 1.36 |
| kind | v0.33.0 |
| Python (system) | 3.9.6 |
| Git branch | `part2` |

### Decisions

**1. Freeze Part 1, then work on a branch.**
The last Part 1 commit carries the annotated tag `part1-complete`, and all
Part 2 work happens on the branch `part2`.

- *Why:* Part 1 stays a working, complete single-container system that can be
  checked out at any time, and any Part 2 change can be compared against it.

**2. Every version is pinned in one file, `versions.env`.**
The file is plain `KEY=VALUE`, one setting per line, with comments on their own
lines. Scripts read it, and a script (`scripts/preflight.sh`) compares it with
what is installed.

| Component | Pin | Reason |
|---|---|---|
| Keycloak | 26.7.4 | Unchanged from Part 1, so that differences in Part 2 come from moving to Kubernetes and not from a Keycloak upgrade. The upgrade is exercised on purpose in a later phase. |
| kind | v0.33.0 | Runs the local cluster inside Docker. |
| Kubernetes node image | `kindest/node` v1.36.4 | Kubernetes 1.36, not the newest 1.37, because cert-manager 1.21 documents support for Kubernetes 1.33 to 1.36. |
| Calico (network plugin) | v3.33.0 | Part 2 relies on default-deny NetworkPolicies, so enforcement has to be certain. Calico is installed explicitly in place of kind's built-in plugin, so enforcement does not depend on which version of the built-in plugin ships, and Calico's policy behavior is widely documented. |
| cert-manager | v1.21.3 | Issues TLS certificates from a local certificate authority, so certificate handling matches a real deployment. |
| PostgreSQL | 17.12 | Keycloak 26.7 supports PostgreSQL 14 to 18; 17 is a mature choice inside that range. |
| nginx | 1.30.6 (`nginx-unprivileged`, Alpine) | Runs as a non-root user, which the Kubernetes "restricted" Pod Security Standard requires. The ingress-nginx project was retired in March 2026, so nginx is deployed as an ordinary Deployment with its own configuration and not as an ingress controller. |
| Python (application image) | 3.13.18 (slim) | Base for the sample application container. |

**3. Container images are pinned by digest, not only by tag.**
Each image is written `name:tag@sha256:...`.

- *Why:* a tag can be re-pushed to point at different contents, while a digest
  identifies exactly one image. With both present, Docker resolves by digest and
  the tag is there for the human reader.
- *How recorded:* each image was pulled on 2026-11-25 and its digest read back
  with `docker inspect` (the `RepoDigests` field). The versions inside the
  images were confirmed by running them: PostgreSQL 17.12, nginx 1.30.6,
  Python 3.13.18. The Keycloak digest is the one for the 26.7.4 tag.
- *Consequence:* updating an image is now a deliberate edit to `versions.env`,
  never something that happens because an upstream tag moved.

**4. The realm file is aligned with the documented values.**
The README, Part 1 Phase 3, and the testing guide state an SSO session idle
timeout of 15 minutes, a maximum session of 12 hours, and a password history of
5. The realm file actually held 30 minutes, 10 hours, and a history of 3.

- *Decision:* change the realm file, not the documents. The documented values
  are the stated policy, and a 15-minute idle timeout suits the shared clinical
  workstations the policy is written for.
- *How:* `scripts/reconcile_realm.py` makes exactly three edits
  (`ssoSessionIdleTimeout` 1800 to 900, `ssoSessionMaxLifespan` 36000 to 43200,
  `passwordHistory(3)` to `passwordHistory(5)`). It refuses to run if it does
  not find the exact old values, so it cannot overwrite a value that was
  changed on purpose, and running it again changes nothing. The rest of the file
  is byte for byte unchanged.
- *Guard:* `versions.env` records the three target values and `preflight.sh`
  fails if the realm file disagrees.
- *Note on Part 1:* the `part1-complete` tag still holds the old values, so Part
  1 as tagged did not fully match its own documents. Part 2 corrects this.

**5. Hostnames and ports.**
Three names are mapped to `127.0.0.1` in `/etc/hosts`: `iam.hospital.test`
(Keycloak, user-facing), `apps.hospital.test` (sample applications), and
`iam-admin.hospital.test` (Keycloak admin console).

- *Why `.test`:* the name is reserved for testing (RFC 6761) and never resolves
  on the internet, so it cannot collide with a real domain.
- *Why a separate admin hostname:* the admin console can later be given stricter
  rules at the proxy than the hostname ordinary users reach.
- *Ports:* the cluster is meant to publish HTTPS on host port 443 and HTTP on
  80, so URLs need no port number. Preflight confirms nothing else is listening
  on them. If 443 or 80 cannot be bound, the fallback is to set 8443 and 8080 in
  `versions.env`.

**6. Secrets: generated from a git-ignored `.env`, one Secret per consumer.**
Kubernetes Secrets will be created from the local `.env` file, which is never
committed. Each workload gets its own Secret, holding only what it needs.

- Three variable names were added to `.env.example`: `DEMO_USER_PASSWORD`,
  `POSTGRES_PASSWORD`, and `KEYCLOAK_DB_PASSWORD`. The Keycloak database
  password is deliberately not called `KC_DB_PASSWORD`, so that Keycloak cannot
  pick it up automatically as one of its own settings.
- Passwords are limited to letters and digits and made long (see the second
  issue below).
- `.gitignore` gained `.DS_Store`, `.env.*` (with `.env.example` kept),
  `*.dump`, `backups/`, `kubeconfig`, and `*.kubeconfig`, because database dumps
  and cluster credentials files contain secrets and are easy to commit by
  accident.

**7. Two scripts check the work.**

- `scripts/preflight.sh` is read-only and changes nothing. It checks the branch
  and tag, a clean working tree, that `.env` is ignored, the realm values against
  `versions.env`, the tool versions (Python, OpenSSL, Docker, kubectl, kind),
  Docker's memory, that the three hostnames resolve to `127.0.0.1`, and that
  ports 443 and 80 are free. It exits with an error if any check fails.
- `scripts/verify_realm.sh` signs in as the admin of a running Keycloak and reads
  the realm settings back from the server, so the claim about session and
  password values is checked against the running system and not only the file.

**8. Directory scaffold.**
Empty folders for later phases were created with a `.gitkeep` file in each,
because Git does not track empty folders.

```
hospital-iam/
  versions.env     every pinned version and local setting
  keycloak/        Dockerfile, realm/hospital-realm.json, scripts/, demo/ (later)
  app/             proof-of-concept sample applications
  k8s/             cluster/, base/, overlays/local/ (manifests, later phases)
  nginx/           reverse proxy configuration (later)
  scripts/         preflight.sh, verify_realm.sh, reconcile_realm.py
  docs/            build-process.md, role-matrix.md, testing-guide.md, runbooks/
  .env.example     variable names only, no values; real .env is git-ignored
  README.md
```

### Issues encountered

**Admin sign-in check failed with HTTP 400 and no readable error.** The first
version of `verify_realm.sh` printed `curl: (22) ... 400` followed by a Python
JSON error.

- *Cause:* Keycloak's token endpoint answers HTTP 400, not 401, when the
  username or password is wrong, when the account has an unfinished required
  action, and when the account is disabled. The script used `curl -f`, which
  discards the response body, so Keycloak's explanation never appeared and the
  JSON parser received nothing.
- *Fix:* the script now prints the HTTP status and Keycloak's own
  `error_description`, with a hint for each of the three cases. It was tested
  against a live Keycloak 26.7.4 with correct and wrong credentials.

**Correct-looking admin password rejected.** The server log showed
`LOGIN_ERROR ... error="invalid_user_credentials"` and included a `userId`, which
meant the account was found and the password was wrong.

- *Cause:* the password contained characters that bash treats as syntax (such as
  `$`, `!`, `#`, `&`, `;`, quotes, or a backslash). The shell command
  `. ./.env` interprets them, while `docker --env-file` reads the file literally,
  so the container and the script were using two different strings.
- *Fix:* the password was changed to letters and digits only. The same
  difference applies to `kubectl create secret --from-env-file`, which is also
  literal, so the rule is part of the Secrets decision above. Strength comes from
  length, not symbols.

**Trailing comments became part of the values.** In one copy of `versions.env`,
comments written after a value on the same line ended up inside quotes
(`KIND_VERSION="v0.33.0   # check ..."`), so the value was the whole string.
That would have broken the kind version comparison, the realm arithmetic, and
the port checks.

- *Fix:* every comment now sits on its own line above the setting, and the file
  header states that no setting may have a trailing comment.

### Verification

| Check | Result |
|---|---|
| `scripts/preflight.sh` | 0 failures. The only warning was uncommitted changes, reported before the Phase 0 work was committed |
| Realm file values | Idle 15 minutes, maximum 12 hours, history 5, matching `versions.env` |
| Realm values on a running Keycloak 26.7.4 (`verify_realm.sh`) | `ssoSessionIdleTimeout` 900, `ssoSessionMaxLifespan` 43200, password policy includes `passwordHistory(5)`, browser flow `browser-mandatory-otp` |
| Image versions inside the pinned images | PostgreSQL 17.12, nginx 1.30.6, Python 3.13.18 |
| `versions.env` | No placeholders left; every image has a digest |
| Hostnames | All three resolve to `127.0.0.1` |
| Ports 443 and 80 | Nothing listening on either |
| Docker resources | 7.7 GB RAM against a 6 GB minimum |
| kubectl and kind | kubectl 1.36 against node image 1.36; kind v0.33.0 as pinned |

### State at the end of Part 2, Phase 0

- Commits on `part2`: the realm alignment, then the pins, scripts, scaffold, and
  ignore rules. This documentation update follows as its own commit.
- No cluster exists, no manifest is written, and no application behavior has
  changed. The only functional change is the three realm values above.
- `docs/role-matrix.md` and `docs/testing-guide.md` needed no change: they
  already described the corrected values.

### Limitations

- Whether Docker can bind host ports 443 and 80 is proven only when the cluster
  is created. Preflight shows that nothing is using them, not that binding will
  succeed. The 8443 and 8080 fallback is in place.
- The nginx digest was recorded from the `stable-alpine` tag, and the
  `1.30.6-alpine` label in `versions.env` is the version that image reports. The
  digest is what is enforced.
- Digests freeze what was tested on 2026-11-25. They are not updated
  automatically, which is intended, but they also mean security patches to the
  base images arrive only when someone updates them.
- Kubernetes Secrets are base64-encoded, not encrypted. That is acceptable for a
  local lab with fictional data. A real deployment would encrypt Secrets at rest
  or use an external secrets manager.

---

## Part 2, Phase 1: Production-shaped images

### Goal

Replace the development-mode Keycloak image with an optimized one that starts
against PostgreSQL, put the sample applications in a container, and separate what
an IT department defines once (the realm's structure) from the fictional demo
users.

### Environment

| Item | Value |
|---|---|
| Date | 2026-11-25 |
| Docker | 29.7.2 |
| Keycloak image | `hospital-iam-keycloak:0.6.0` (built on Keycloak 26.7.4) |
| Sample application image | `hospital-iam-app:0.6.0` (Python 3.13.18, gunicorn 27.0.1) |
| Database for testing | PostgreSQL 17.12 in a container |

Both image tags are local only. They are not pushed to a registry; Phase 2 loads
them into the cluster.

### Decisions

**1. The Keycloak image separates build-time options from runtime options.**
Keycloak fixes some settings when `kc.sh build` runs and bakes them into the
server. Everything else is supplied when the container starts.

| Setting | Where it is set | Reason |
|---|---|---|
| `KC_DB=postgres` | Build (Dockerfile) | The database vendor is fixed by the build step |
| `KC_HEALTH_ENABLED`, `KC_METRICS_ENABLED` | Build (Dockerfile) | The health and metrics endpoints are build-time features |
| Database URL, user, password | Runtime (environment) | They differ per environment, and the password is a secret |
| `KC_HOSTNAME`, `KC_HTTP_ENABLED`, `KC_HOSTNAME_BACKCHANNEL_DYNAMIC` | Runtime (environment) | The public address and where TLS ends are facts about a deployment, not about the image |
| Admin bootstrap credentials, client secrets | Runtime (environment) | Secrets |
| `--import-realm`, the success-event option | Start arguments in `CMD` | Runtime options |

The container starts with `start --optimized`, which skips the build at boot, so
every start behaves the same way and the server starts faster. The startup log
does not contain Keycloak's "Updating the configuration" message, which is how an
implicit rebuild would show itself.

- *Two stages:* the image follows Keycloak's documented pattern, a builder stage
  that runs `kc.sh build` and a final stage that copies the result. With nothing
  to discard yet, the benefit is small today; it matters once providers or themes
  are added.
- *Pinned by digest:* both `FROM` lines carry the same digest as `KEYCLOAK_IMAGE`
  in `versions.env`.
- *Ownership:* files are copied with `--chown=1000:0`. User 1000 is Keycloak's own
  non-root user, and group 0 keeps the files usable if a platform assigns a
  different user ID.
- *Build context:* `keycloak/.dockerignore` excludes `scripts/` and `demo/`, so
  the demo users cannot enter an image even by accident.

**2. The success-event option stays a runtime argument.**
Part 1 turned on logging of successful sign-ins with
`--spi-events-listener--jboss-logging--success-level=info`. It was tested whether
`--optimized` accepts that option at start or whether it has to move into the
build stage. It is accepted at start: with it in `CMD`, an administrator sign-in
is logged as a `LOGIN` event at INFO level. It therefore stays in `CMD`, next to
`--import-realm`.

**3. Realm structure and demo users are separate.**
`hospital-realm.json` now holds what an IT department defines once: roles,
groups and their role mappings, clients, the mandatory-OTP flow, policies, and
event settings. The nine fictional users, and the shared demo password that was
stored with them, are no longer in the realm file or in any image.

- `keycloak/demo/demo_users.json` lists the nine users with no passwords.
- `keycloak/scripts/split_demo_users.py` did the one-time move. It refuses to run
  unless the realm file holds exactly the nine expected users, and it changes
  nothing on a second run. Apart from the removed `users` list, the realm file is
  unchanged.
- `keycloak/scripts/seed_group_roles.py` replaces `seed_users.py`. It keeps the
  group-to-role mapping, which is the structural part, and removes any `users`
  list from the realm file. The group-to-role mapping is still written into the
  realm file, for the reason given under Part 1, Phase 4.

**4. A loader creates the demo users in a running Keycloak.**
`keycloak/demo/load_demo_users.py` uses only the Python standard library, so it
runs on a workstation, in a plain Python container, or later in a Kubernetes Job
without installing anything.

- Every user receives the password in `DEMO_USER_PASSWORD`, read from the
  environment, never printed, and never stored. It is marked temporary, so each
  first sign-in forces enrollment of an authenticator and a new password. That is
  the real onboarding path, and no shared password ships anywhere.
- It creates users through the admin REST API. Unlike a realm import, this gives
  each user the realm's default role automatically, and groups are assigned by
  path.
- It is safe to repeat: a user that already exists is skipped and never modified.
  `--remove` deletes exactly the users in `demo_users.json` and nobody else.
- The password is checked against the realm's 14-character minimum before any
  request is made, so a short value fails with a clear message.

**5. The sample application runs under gunicorn, as a non-root user.**
`app/Dockerfile` creates a fixed numeric user (10001) and runs
`gunicorn --workers 1 --threads 4`.

- *One worker:* login sessions are kept in a dictionary in the memory of the
  process. Two worker processes would each hold different sessions and sign people
  out at random, so concurrency comes from threads, and the deployment will run a
  single replica.
- *Numeric user:* Kubernetes can verify `runAsNonRoot` only for a numeric ID.
- *`--worker-tmp-dir /dev/shm`:* gunicorn's heartbeat files go to memory, so the
  container's filesystem can later be made read-only.
- *`--no-control-socket`:* gunicorn 27 opens a management socket under the user's
  home directory by default. This user has no home directory, and an admin socket
  is not needed.
- *`--access-logfile -`:* requests are logged to standard output, where
  `docker logs` and `kubectl logs` read them.
- The base image is pinned by digest, as `PYTHON_IMAGE` in `versions.env`, and
  `app/.dockerignore` keeps `.env`, `.venv` and `.git` out of the image.

**6. Two optional settings were added to the application.**
`app/app.py` gained two environment variables, and both have defaults that keep
the previous behavior.

- `KEYCLOAK_DISCOVERY_URL`: the address from which the application fetches
  Keycloak's discovery document. It defaults to the public issuer address. In a
  cluster it can point to Keycloak's internal address while `KEYCLOAK_ISSUER`
  stays public. With `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true`, a discovery document
  fetched through the internal name reported the issuer, the authorization
  endpoint and the end-session endpoint on the public address (for the browser),
  and the token and key endpoints on the internal address (for the application).
  The ID token's issuer therefore matches the issuer the application expects, and
  the application never needs to reach the public address from inside the
  network.
- `PROXY_HOPS` (default 0): how many reverse proxies stand in front of the
  application. Only when it is above zero is Werkzeug's `ProxyFix` applied, so the
  forwarded scheme and host are trusted. Trusting `X-Forwarded-*` headers
  unconditionally would let anyone who can reach the application directly forge
  them. The application builds its URLs from `APP_BASE_URL` and not from the
  request, so this setting is a safeguard.

**7. gunicorn is pinned per Python version.**
`app/requirements.txt` pins gunicorn 23.0.0 for Python below 3.10 and 27.0.1 for
3.10 and above. The development machine runs Python 3.9, on which gunicorn 24 and
later cannot be installed, while the container uses Python 3.13 and should not be
held back by that. The other pins are unchanged.

**8. Secrets stay out of the images.**
Neither image contains a credential, a client secret, an `.env` file, or the demo
password. The Keycloak realm file carries the three client secrets as
`${EHR_CLIENT_SECRET}`-style placeholders that Keycloak fills from its
environment when it imports the realm. Three variables were added to `.env` in
Part 2, Phase 0 and are used from this phase: `KEYCLOAK_DB_PASSWORD` for the
database, `DEMO_USER_PASSWORD` for the loader, and `POSTGRES_PASSWORD` (not
needed until the cluster phase).

### Process

Both `versions.env` and `.env` must be loaded in every new terminal, because the
commands use the pinned image references and the secrets:

```bash
set -a; . ./versions.env; . ./.env; set +a
```

1. Split the demo users out of the realm file (one time):

   ```bash
   python3 keycloak/scripts/split_demo_users.py keycloak/realm/hospital-realm.json keycloak/demo/demo_users.json
   ```

2. Build both images:

   ```bash
   docker build -t hospital-iam-keycloak:0.6.0 ./keycloak
   docker build -t hospital-iam-app:0.6.0 ./app
   ```

3. Start PostgreSQL and Keycloak on a shared network. Keycloak receives the
   database password and the other runtime settings from the environment:

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

4. Load the demo users, then start the sample applications:

   ```bash
   python3 keycloak/demo/load_demo_users.py
   docker run -d --name app --network iam-net -p 5050:5050 \
     -e KEYCLOAK_ISSUER=http://localhost:8080/realms/hospital \
     -e KEYCLOAK_DISCOVERY_URL=http://keycloak:8080/realms/hospital/.well-known/openid-configuration \
     -e APP_BASE_URL=http://localhost:5050 \
     -e APP_SECRET_KEY -e EHR_CLIENT_SECRET -e WIKI_CLIENT_SECRET -e DASHBOARD_CLIENT_SECRET \
     hospital-iam-app:0.6.0
   ```

The `-e NAME` form without a value passes the exported variable, so no secret
appears on a command line. The Postgres wait loop looks for the "ready" message
twice because the official image starts a temporary server during initialization
and then restarts.

### Issues encountered

**gunicorn 24 and later cannot be installed on Python 3.9.** The first choice,
the newest gunicorn, failed to resolve on the development machine's interpreter.
The pin was split by Python version (decision 7), and both lines were checked.

**gunicorn's default control socket needs a home directory.** gunicorn 27 tries to
create a socket under the running user's home directory. The application's user
has none, and a read-only filesystem would not allow it either. The socket is
disabled with `--no-control-socket`.

**PostgreSQL reports ready before it is.** The official image starts a temporary
server to initialize the database and then restarts. Checking readiness once can
succeed during the first start, and Keycloak would then fail to connect. The start
script waits for the ready message to appear twice.

**An empty image reference.** In a terminal where `versions.env` had not been
loaded, `docker run ... "$POSTGRES_IMAGE"` received an empty value and failed with
"invalid reference format". Every command sequence in this project therefore
begins by loading `versions.env` and `.env`.

### Observations

- A new user's required actions run in a fixed order: authenticator enrollment
  first, then the password change.
- The demo users all carry a temporary password, so the first sign-in of every
  user exercises the onboarding path. The testing guide has a section for this.
- Removing the `pg` container discards the identity data, including every
  authenticator enrollment, and the next start imports the realm again into an
  empty database. While the container exists, restarting Keycloak does not
  re-import the realm: import runs only when the realm does not exist.

### Verification

| Check | Result |
|---|---|
| Keycloak starts with `start --optimized` against PostgreSQL | Confirmed: the log shows `Profile prod activated` and `Realm 'hospital' imported`, and no "Updating the configuration" message |
| Realm values on the running server (`scripts/verify_realm.sh`) | `ssoSessionIdleTimeout` 900, `ssoSessionMaxLifespan` 43200, password policy `length(14)`, not username, not email, `passwordHistory(5)`, browser flow `browser-mandatory-otp` |
| The password policy is enforced | A password equal to the username and a password equal to the email were each rejected; a different strong password was accepted |
| Successful sign-ins are logged with the option as a start argument | Confirmed: an administrator sign-in appears as `type="LOGIN"` |
| Realm file and demo file | The realm file has no `users` list. `demo_users.json` has nine users and no credentials. The old demo password appears in neither |
| `load_demo_users.py` | Creates nine users; a second run leaves all nine unchanged; a short `DEMO_USER_PASSWORD` and a wrong admin password each fail with a clear message |
| Demo users after loading | Group membership, the group's role, and the default role are present; every user has a temporary password; `former.employee` is disabled |
| First sign-in through a browser | Forced authenticator enrollment and password change, then arrival at the EHR page with the role `nurse` |
| Application discovery through the internal address | Issuer and browser endpoints on the public address; token and key endpoints on the internal address |
| Application container | Runs as `10001:10001`, with exactly one gunicorn worker; `/srv` holds only `app.py` and `requirements.txt` |
| Keycloak container | Runs as user 1000 |
| No secrets in the images | None of the eight secret values appears in either image's build history or environment; the image's realm file holds only `${...}` placeholders |

### State at the end of Part 2, Phase 1

```
hospital-iam/
  versions.env
  keycloak/
    Dockerfile           optimized, two-stage, pinned by digest
    .dockerignore
    realm/hospital-realm.json    structure only, no users
    demo/demo_users.json         nine fictional users, no passwords
    demo/load_demo_users.py      creates or removes them in a running Keycloak
    scripts/seed_group_roles.py  group-to-role mappings
    scripts/seed_clients.py
    scripts/split_demo_users.py  one-time split (kept for the record)
  app/
    Dockerfile  .dockerignore  app.py  requirements.txt
```

### Limitations

- Keycloak and the application are reached over plain HTTP on `localhost`. TLS,
  the public hostnames, and the proxy arrive in later phases, and the client
  redirect addresses in the realm still point to `http://localhost:5050`.
- The images exist only on the local Docker daemon. Loading them into the cluster
  is done when the cluster exists.
- The PostgreSQL container used here is a test database with a throwaway
  credential. It is not the cluster's database, which has persistent storage and
  its own configuration.
- The sample application keeps login sessions in memory, so it must stay at one
  replica and a restart signs everyone out.
- The Part 1 quick start no longer works on this branch, because the Keycloak
  image is no longer in development mode and the realm has no users. Part 1 can
  still be built from the `part1-complete` tag.

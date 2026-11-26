# Testing Guide

A step-by-step walkthrough for trying out the project without reading the build
process. Everything here uses fictional users and data. It describes the system as
run on branch `part2` (README, "Running the Phase 1 images"). The single-container
Part 1 system is on the `part1-complete` tag.

## Before you begin

Complete the three steps in the README section "Running the Phase 1 images", so
that all of these are running (`docker ps` lists the containers `pg`, `keycloak`
and `app`):

- Keycloak at http://localhost:8080, with the demo users loaded
- The sample applications at http://localhost:5050

Always use `localhost` in the browser, not `127.0.0.1`. Use a private (incognito)
window for the sign-in tests so earlier sessions do not interfere.

An authenticator app is needed for multi-factor authentication. Any app that
supports time-based codes works (for example Google Authenticator, Microsoft
Authenticator, or Apple Passwords). One app can hold a separate entry for each
user.

## Accounts

**Administrator.** Sign in at http://localhost:8080 with the
`KC_BOOTSTRAP_ADMIN_USERNAME` and `KC_BOOTSTRAP_ADMIN_PASSWORD` values from your
`.env` file. This account belongs to Keycloak's `master` realm. A banner saying
it is a temporary admin user is expected.

After signing in, switch to the hospital realm: open **Manage realms** at the top
of the left sidebar and choose **hospital**. The sidebar then shows
"Hospital IAM (Fictional)" as the current realm.

**Hospital users.** Every user is created with the same temporary password, the
value of `DEMO_USER_PASSWORD` in your `.env` file. It is not stored anywhere else.
Each user must replace it at first sign-in (see "First sign-in" below).

| Username | Role | Notes |
|---|---|---|
| `nina.nurse` | nurse | |
| `paul.physician` | physician | |
| `sam.scheduler` | scheduler | |
| `rita.reports` | report-analyst | |
| `carl.compliance` | compliance-auditor | |
| `ivy.it` | it-admin | |
| `new.hire` | nurse | Keep unused until test 5 |
| `no.group` | none | Can sign in but has no role |
| `former.employee` | nurse (disabled) | Account is disabled |

Hospital users sign in through the applications, or at
http://localhost:8080/realms/hospital/account. They cannot sign in to the admin
console, which only accepts the administrator.

## First sign-in

All demo users are created with a temporary password, so each user's first
sign-in has two extra steps:

1. Enroll an authenticator: scan the QR code and enter the 6-digit code.
2. Choose a new password of at least 14 characters that is not the username or the
   email address.

Do this once for each user used in the tests below: `nina.nurse`, `paul.physician`,
`sam.scheduler`, `rita.reports`, `carl.compliance`, `ivy.it`, and `no.group`. Leave
`new.hire` for test 5. Afterwards, every sign-in takes the new password and the
current authenticator code. Any fictional password will do; the tests that follow
call it "the user's password".

## What to look at in the admin console

With the **hospital** realm selected:

| Where | What to see |
|---|---|
| Realm roles | Six job roles |
| Groups | Six department groups; open one and its **Role mapping** tab shows its role |
| Users | Nine users; open one and its **Groups** and **Role mapping** tabs show how access is granted |
| Clients | `ehr-demo`, `wiki-demo`, and `dashboard-demo` |
| Authentication > Flows | `browser-mandatory-otp`, used as the browser flow |
| Authentication > Policies | Password policy (minimum 14 characters) and OTP policy |
| Realm settings > Security defenses | Brute-force detection |
| Realm settings > Sessions, Tokens | 15-minute idle timeout, 12-hour maximum, 5-minute access tokens |
| Realm settings > Events | User and admin event saving, with the `jboss-logging` listener |

## Tests

Each test lists what to do and what you should see.

### 1. Single sign-on with mandatory multi-factor authentication

1. Open http://localhost:5050 and choose **EHR**.
2. Sign in as `nina.nurse`. At her first sign-in, use the temporary password and
   complete the two first-sign-in steps; afterwards use her password and the
   current authenticator code.

**Expect:** you arrive at the EHR page. Then, in the same window, open the
**Internal wiki** and the **Scheduling and reporting dashboard** from the top bar:
neither asks for a password or code. That is single sign-on.

### 2. Role-based access

Each application's home page lists its pages as Allowed or Denied for the
signed-in user. Sign in as each user below and check the three home pages.

| User | EHR | Wiki | Dashboard |
|---|---|---|---|
| `nina.nurse` | Patient demographics, Chart notes and vitals | Read pages, Edit nursing pages | View schedule |
| `paul.physician` | Patient demographics, Chart notes and vitals, Sign orders | Read pages, Edit clinical pages | View schedule, Reports |
| `sam.scheduler` | Patient demographics | Read pages | View schedule, Edit schedule |
| `rita.reports` | none | Read pages | Reports |
| `carl.compliance` | Audit views | Read pages | Reports |
| `ivy.it` | Platform administration | Read pages, Wiki administration | View schedule, Edit schedule, Reports, Dashboard administration |

**Expect:** exactly the pages listed are Allowed; everything else is Denied.
The full matrix is in `role-matrix.md`.

To test enforcement directly, signed in as `nina.nurse` open
http://localhost:5050/ehr/p/orders. **Expect:** an "Access denied" page (HTTP 403).

### 3. A user with no role

Sign in as `no.group` (after its first sign-in). **Expect:** sign-in succeeds, but
every page in every application is Denied.

### 4. A disabled account

Try to sign in as `former.employee`. **Expect:** sign-in is refused because the
account is disabled.

### 5. First sign-in and password policy

1. Sign in as `new.hire` with the temporary password.
2. Enroll an authenticator. You are then asked to choose a new password. Try a
   short one (for example `short123`). **Expect:** it is rejected by the password
   policy.
3. Choose a new password of at least 14 characters. **Expect:** you arrive at the
   application.

### 6. Lockout after repeated failures

Enter a wrong password five times for one user (for example `sam.scheduler`).
**Expect:** the user's correct password is then also refused for about a minute.

### 7. MFA cannot be bypassed

1. In the admin console (hospital realm), open **Users > nina.nurse >
   Credentials** and delete her one-time-password credential.
2. Sign in as `nina.nurse` again.

**Expect:** you are sent back to the authenticator setup page; a password alone
does not get you in.

### 8. Revoking access

1. Sign in as `paul.physician` and open the dashboard. Note the line "Session
   ends in about N seconds".
2. In the admin console, open **Users > paul.physician** and turn **Enabled** off.
3. Keep refreshing the dashboard.

**Expect:** the dashboard keeps working until that countdown reaches zero (at
most about five minutes), then redirects to Keycloak, which refuses the sign-in.
Turn the account back on afterwards.

### 9. Sign-out

Sign out of one application. **Expect:** Keycloak's session ends, so opening
another application leads to the sign-in page, either immediately or once that
application's own session expires (within about five minutes).

### 10. Audit log

In a terminal:

```bash
docker logs keycloak 2>&1 | grep "org.keycloak.events"
```

**Expect:** entries for the actions above, including successful sign-ins
(`LOGIN`), failures (`LOGIN_ERROR`), sign-outs (`LOGOUT`), and your administrator
changes. The same events are also visible under **Events** in the admin console.

## Starting over

Remove the containers and the network, then repeat the README steps:

```bash
docker rm -f app keycloak pg
docker network rm iam-net
```

The database is discarded with the `pg` container, so everything returns to the
state in the repository: the realm is imported again, the demo users are created
again with the temporary password, and no authenticator is enrolled. Restarting
only Keycloak (`docker restart keycloak`) keeps the database, so users, enrollments
and password changes survive; the realm is not imported a second time.

To recreate only the demo users, run `python3 keycloak/demo/load_demo_users.py
--remove` and then `python3 keycloak/demo/load_demo_users.py` (with `.env` loaded).

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| The admin console shows only the `master` realm | Switch realm with **Manage realms** and choose **hospital** |
| A hospital user cannot sign in to the admin console | Expected; only the administrator from `.env` can |
| The `app` container exits at startup with "... is not set" | A value in `.env` is empty, or `.env` was not loaded in that terminal. Load it with `set -a; . ./.env; set +a`, fix the value, and recreate the container |
| Sign-in fails with `invalid_client` | The secrets in `.env` changed after the realm was first imported. The realm is imported once per database, so remove the containers (see "Starting over") and start again |
| A demo user's temporary password is refused | `DEMO_USER_PASSWORD` in `.env` changed after the users were loaded. Remove and reload the users (see "Starting over") |
| `load_demo_users.py` reports that Keycloak refused the admin sign-in | The admin values in `.env` must match those the Keycloak container was started with. `bash scripts/verify_realm.sh` prints Keycloak's reason |
| Redirect or cookie errors | Use `http://localhost:5050`, not `127.0.0.1` |
| Authenticator codes are rejected | Make sure the phone's clock is set automatically |
| An authenticator entry stops working after removing the containers | Expected; the database, and with it every enrollment, is discarded |
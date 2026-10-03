# Build Process

How the Hospital IAM image and environment were built. This document is
extended as each part of the project is completed.

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
  keycloak/        Dockerfile and realm/hospital-realm.json
  app/             proof-of-concept sample application(s)
  docs/            project documentation
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
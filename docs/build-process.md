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
| Host OS | macOS 26.5.2(local) |
| Docker | 29.7.2(local) |
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
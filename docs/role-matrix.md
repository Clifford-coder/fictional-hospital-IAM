# Role and Permission Matrix

Defines the access each hospital role has in each of the three systems. All users and records are fictional.

## How access is granted

Access is assigned to **roles**, roles are carried by **groups**, and people
receive access only by **group membership**. No role is assigned directly to a
user. Each application reads the user's roles from the token Keycloak issues and
maps them to its own page-level permissions.

| Group | Realm role |
|---|---|
| Nursing | `nurse` |
| Medicine | `physician` |
| Front Desk | `scheduler` |
| Analytics | `report-analyst` |
| Compliance | `compliance-auditor` |
| IT | `it-admin` |

## Access by role

| Role | EHR | Internal wiki | Scheduling / reporting dashboard |
|---|---|---|---|
| `nurse` | Read and write chart notes and vitals; cannot sign orders | Read; edit nursing pages | Read own unit's schedule |
| `physician` | Read and write chart; sign orders | Read; edit clinical pages | Read schedule; reports on own patients |
| `scheduler` | No chart access (demographics only) | Read | Write schedules |
| `report-analyst` | None (de-identified extracts only) | Read | Read all reports; no schedule writes |
| `compliance-auditor` | Read-only audit views | Read | Read reports and audit summaries |
| `it-admin` | None to clinical data; platform administration | Admin | Admin |

## Enforcement in the sample applications

Each application enforces access on the server from the `roles` claim in the
validated ID token. Roles map to pages as follows; any other role receives
HTTP 403. Access was verified by signing in as each user and comparing the
allowed and denied pages with this matrix.

| System | Page | Roles allowed |
|---|---|---|
| EHR | Patient demographics | `nurse`, `physician`, `scheduler` |
| EHR | Chart notes and vitals | `nurse`, `physician` |
| EHR | Sign orders | `physician` |
| EHR | Audit views (read-only) | `compliance-auditor` |
| EHR | Platform administration | `it-admin` |
| Wiki | Read pages | all six roles |
| Wiki | Edit nursing pages | `nurse` |
| Wiki | Edit clinical pages | `physician` |
| Wiki | Wiki administration | `it-admin` |
| Dashboard | View schedule | `nurse`, `physician`, `scheduler`, `it-admin` |
| Dashboard | Edit schedule | `scheduler`, `it-admin` |
| Dashboard | Reports | `physician`, `report-analyst`, `compliance-auditor`, `it-admin` |
| Dashboard | Dashboard administration | `it-admin` |

Enforcement is at page level. Narrower limits named in the matrix, such as
"own unit" and "own patients", are not modeled in the proof-of-concept
applications.

## Rationale

| Role | Reasoning |
|---|---|
| `nurse` | Needs to document care but orders are a physician responsibility, so order signing is withheld. |
| `physician` | Needs full chart access and authority to sign orders. |
| `scheduler` | Manages appointments and needs only demographic details, not clinical records. |
| `report-analyst` | Works from aggregate or de-identified data, so has no direct chart access and cannot alter schedules. |
| `compliance-auditor` | Reviews activity without being able to change records, so access is read-only. |
| `it-admin` | Administers platforms without needing clinical data, keeping administrative and clinical access separate. |

## Principle

Each role receives only the access its job requires (least privilege), and
clinical access is kept separate from administrative access.
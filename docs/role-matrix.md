# Role and Permission Matrix

Defines which access each hospital role is intended to have in each of the three
systems. All users and records are fictional.

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

## Intended access by role

| Role | EHR | Internal wiki | Scheduling / reporting dashboard |
|---|---|---|---|
| `nurse` | Read and write chart notes and vitals; cannot sign orders | Read; edit nursing pages | Read own unit's schedule |
| `physician` | Read and write chart; sign orders | Read; edit clinical pages | Read schedule; reports on own patients |
| `scheduler` | No chart access (demographics only) | Read | Write schedules |
| `report-analyst` | None (de-identified extracts only) | Read | Read all reports; no schedule writes |
| `compliance-auditor` | Read-only audit views | Read | Read reports and audit summaries |
| `it-admin` | None to clinical data; platform administration | Admin | Admin |

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
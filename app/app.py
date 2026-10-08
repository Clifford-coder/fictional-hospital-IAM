"""Proof-of-concept sample applications for the Hospital IAM project.

One small Flask program plays three hospital systems (EHR, internal wiki,
scheduling/reporting dashboard) under /ehr, /wiki and /dashboard. Each is a
separate OpenID Connect client of Keycloak, so signing in to one and then
opening another demonstrates single sign-on. All data is fictional and hard-coded.

Authorization is enforced here, on the server, from the "roles" claim in the
validated ID token. Each application keeps its own login session and expires it
when the ID token expires, which ties how quickly a revocation takes effect to
the realm's token lifespan.
"""
import os
import secrets
import time
from urllib.parse import urlencode

from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, abort, redirect, render_template_string, request, session

load_dotenv(find_dotenv())

ISSUER = os.environ.get("KEYCLOAK_ISSUER", "http://localhost:8080/realms/hospital")
BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5050").rstrip("/")

NURSE, PHYSICIAN, SCHEDULER = "nurse", "physician", "scheduler"
ANALYST, AUDITOR, IT_ADMIN = "report-analyst", "compliance-auditor", "it-admin"
JOB_ROLES = {NURSE, PHYSICIAN, SCHEDULER, ANALYST, AUDITOR, IT_ADMIN}

# slug -> (page title, roles allowed, fictional content lines). Mirrors docs/role-matrix.md.
APPS = {
    "ehr": {
        "title": "EHR (demo)", "client_id": "ehr-demo", "secret_env": "EHR_CLIENT_SECRET",
        "pages": {
            "demographics": ("Patient demographics", {NURSE, PHYSICIAN, SCHEDULER},
                             ["Patient 0001: Test Patient (fictional).",
                              "Placeholder demographics only; no real data."]),
            "chart": ("Chart notes and vitals", {NURSE, PHYSICIAN},
                      ["Patient 0001: Test Patient (fictional).",
                       "Sample vitals entry and sample nursing note for demonstration."]),
            "orders": ("Sign orders", {PHYSICIAN},
                       ["Order 0001 (demo): sample order awaiting signature."]),
            "audit": ("Audit views (read-only)", {AUDITOR},
                      ["Sample event: nina.nurse viewed chart for Patient 0001.",
                       "Sample event: paul.physician signed Order 0001."]),
            "admin": ("Platform administration", {IT_ADMIN},
                      ["Service status: OK (sample). No clinical data is shown here."]),
        },
    },
    "wiki": {
        "title": "Internal wiki (demo)", "client_id": "wiki-demo", "secret_env": "WIKI_CLIENT_SECRET",
        "pages": {
            "read": ("Read pages", JOB_ROLES, ["Welcome page (sample).", "Hospital policies index (sample)."]),
            "edit-nursing": ("Edit nursing pages", {NURSE}, ["Nursing procedures page (sample, editable)."]),
            "edit-clinical": ("Edit clinical pages", {PHYSICIAN}, ["Clinical guidelines page (sample, editable)."]),
            "admin": ("Wiki administration", {IT_ADMIN}, ["Spaces and permissions (sample)."]),
        },
    },
    "dashboard": {
        "title": "Scheduling and reporting dashboard (demo)", "client_id": "dashboard-demo",
        "secret_env": "DASHBOARD_CLIENT_SECRET",
        "pages": {
            "schedule": ("View schedule", {NURSE, PHYSICIAN, SCHEDULER, IT_ADMIN},
                         ["Sample unit schedule: Shift A, Shift B (fictional)."]),
            "schedule-edit": ("Edit schedule", {SCHEDULER, IT_ADMIN},
                              ["Sample schedule editor (fictional)."]),
            "reports": ("Reports", {PHYSICIAN, ANALYST, AUDITOR, IT_ADMIN},
                        ["Sample report: monthly visit counts (fictional numbers)."]),
            "admin": ("Dashboard administration", {IT_ADMIN}, ["Data sources and refresh jobs (sample)."]),
        },
    },
}


def require_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and set it.")
    return value


app = Flask(__name__)
app.secret_key = require_env("APP_SECRET_KEY")
app.config.update(
    SESSION_COOKIE_NAME="hospital_demo_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",   # sent on the redirect back from Keycloak
    SESSION_COOKIE_SECURE=BASE_URL.startswith("https://"),
)

oauth = OAuth(app)
for _key, _cfg in APPS.items():
    oauth.register(
        name=_key,
        client_id=_cfg["client_id"],
        client_secret=require_env(_cfg["secret_env"]),
        server_metadata_url=f"{ISSUER}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256"},
    )

# Server-side login sessions: sid -> {app_key: {...}}. The browser cookie holds only
# the sid (an ID token per app would overflow the 4 KB cookie limit). In-memory:
# restarting the program signs everyone out.
SESSIONS = {}

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;color:#22303c;background:#f6f8fa}
 .banner{background:#fff3cd;color:#664d03;padding:.45rem 1rem;font-size:.85rem;text-align:center}
 nav{background:#12355b;color:#fff;padding:.7rem 1rem;display:flex;gap:1rem;align-items:center}
 nav a{color:#bfe3e8;text-decoration:none} nav .sp{flex:1}
 main{max-width:46rem;margin:1.5rem auto;padding:0 1rem}
 table{border-collapse:collapse;width:100%;background:#fff}
 td,th{border:1px solid #c9d6dc;padding:.4rem .6rem;text-align:left}
 th{background:#eaf3f5} .ok{color:#146c2e;font-weight:600} .no{color:#9b1c1c}
 .card{background:#fff;border:1px solid #c9d6dc;padding:1rem;margin:1rem 0}
</style></head><body>
<div class="banner">Proof of concept: all data is fictional.</div>
<nav>
 <strong>Hospital IAM demo</strong>
 {% for k, a in apps.items() %}<a href="/{{ k }}/">{{ a.title.split(' (')[0] }}</a>{% endfor %}
 <span class="sp"></span>
 {% if login %}<span>{{ login.username }}</span> <a href="/{{ app_key }}/logout">Sign out</a>{% endif %}
</nav>
<main>
<h1>{{ title }}</h1>
{% if view == 'landing' %}
 <p>Three stand-in hospital systems share one Keycloak sign-in. Open one, sign in
 (password and authenticator code), then open another: it should not ask again.</p>
 <ul>{% for k, a in apps.items() %}<li><a href="/{{ k }}/">{{ a.title }}</a></li>{% endfor %}</ul>
{% elif view == 'home' %}
 <div class="card">
  <p><strong>{{ login.name or login.username }}</strong> ({{ login.username }})</p>
  <p>Roles: {% if login.job_roles %}{{ login.job_roles|join(', ') }}{% else %}
   <span class="no">none (no job role in token)</span>{% endif %}</p>
  <p>Session ends in about {{ remaining }} seconds; signing in again is silent while the Keycloak session lasts.</p>
 </div>
 <table><tr><th>Page</th><th>Access</th></tr>
 {% for p in pages %}<tr>
  <td>{% if p.allowed %}<a href="/{{ app_key }}/p/{{ p.slug }}">{{ p.title }}</a>{% else %}{{ p.title }}{% endif %}</td>
  <td class="{{ 'ok' if p.allowed else 'no' }}">{{ 'Allowed' if p.allowed else 'Denied' }}</td></tr>{% endfor %}
 </table>
{% elif view == 'page' %}
 <div class="card">{% for line in lines %}<p>{{ line }}</p>{% endfor %}</div>
 <p><a href="/{{ app_key }}/">Back</a></p>
{% else %}
 <p>{{ message }}</p><p><a href="/">Home</a></p>
{% endif %}
</main></body></html>"""


def render(view, status=200, **ctx):
    ctx.setdefault("title", "Hospital IAM demo")
    ctx.setdefault("login", None)
    ctx.setdefault("app_key", "")
    return render_template_string(TEMPLATE, view=view, apps=APPS, **ctx), status


def sid(create=False):
    if "sid" not in session and create:
        session["sid"] = secrets.token_urlsafe(24)
    return session.get("sid")


def current_login(app_key):
    """This app's login for the browser, or None if absent or expired."""
    entry = SESSIONS.get(sid(), {}).get(app_key)
    if entry and entry["expires_at"] <= time.time():
        SESSIONS[sid()].pop(app_key, None)
        return None
    return entry


def cfg_or_404(app_key):
    if app_key not in APPS:
        abort(404)
    return APPS[app_key]


def start_login(app_key):
    return redirect(f"/{app_key}/login?" + urlencode({"next": request.path}))


@app.route("/")
def landing():
    return render("landing", title="Hospital IAM demo")


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.route("/<app_key>/")
def home(app_key):
    cfg = cfg_or_404(app_key)
    login = current_login(app_key)
    if not login:
        return start_login(app_key)
    roles = set(login["roles"])
    pages = [{"slug": s, "title": p[0], "allowed": bool(p[1] & roles)} for s, p in cfg["pages"].items()]
    return render("home", title=cfg["title"], login=login, app_key=app_key, pages=pages,
                  remaining=int(login["expires_at"] - time.time()))


@app.route("/<app_key>/p/<slug>")
def page(app_key, slug):
    cfg = cfg_or_404(app_key)
    if slug not in cfg["pages"]:
        abort(404)
    login = current_login(app_key)
    if not login:
        return start_login(app_key)
    title, allowed, lines = cfg["pages"][slug]
    if not (allowed & set(login["roles"])):
        return render("message", 403, title="Access denied", login=login, app_key=app_key,
                      message=f"Your roles do not permit access to '{title}'.")
    return render("page", title=title, login=login, app_key=app_key, lines=lines)


@app.route("/<app_key>/login")
def login(app_key):
    cfg_or_404(app_key)
    nxt = request.args.get("next", "")
    session["next_" + app_key] = nxt if nxt.startswith(f"/{app_key}/") else f"/{app_key}/"
    return getattr(oauth, app_key).authorize_redirect(f"{BASE_URL}/{app_key}/callback")


@app.route("/<app_key>/callback")
def callback(app_key):
    cfg_or_404(app_key)
    try:
        token = getattr(oauth, app_key).authorize_access_token()
    except OAuthError as err:
        detail = f"{err.error}: {err.description}" if err.description else str(err.error)
        app.logger.warning("Sign-in failed for %s (%s)", app_key, detail)
        return render("message", 400, title="Sign-in failed", message=f"Sign-in failed ({detail}).")
    claims = token["userinfo"]
    roles = sorted(set(claims.get("roles", [])))
    old = SESSIONS.pop(session.get("sid"), {})       # new session id on every login
    session["sid"] = secrets.token_urlsafe(24)
    SESSIONS[session["sid"]] = old
    SESSIONS[session["sid"]][app_key] = {
        "username": claims.get("preferred_username", "unknown"),
        "name": claims.get("name"),
        "roles": roles,
        "job_roles": [r for r in roles if r in JOB_ROLES],
        "id_token": token["id_token"],
        "expires_at": claims["exp"],
    }
    return redirect(session.pop("next_" + app_key, f"/{app_key}/"))


@app.route("/<app_key>/logout")
def logout(app_key):
    cfg = cfg_or_404(app_key)
    login = current_login(app_key)
    SESSIONS.get(sid(), {}).pop(app_key, None)
    meta = getattr(oauth, app_key).load_server_metadata()
    params = {"client_id": cfg["client_id"], "post_logout_redirect_uri": f"{BASE_URL}/"}
    if login:
        params["id_token_hint"] = login["id_token"]
    return redirect(meta["end_session_endpoint"] + "?" + urlencode(params))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("APP_PORT", "5050")))
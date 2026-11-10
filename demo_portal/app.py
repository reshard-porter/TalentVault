"""A small, login-protected recruiting portal used to demonstrate and test the exporter.

It imitates the shape of a typical applicant-tracking / candidate-database site:
login form -> search filters -> paginated results -> candidate profile -> resume download.
All people and documents are fictional and generated deterministically.

Run it with:  python -m demo_portal.app      (http://127.0.0.1:5055, login demo / demo123)
"""
from __future__ import annotations

import io
import os
import random
from functools import wraps

from docx import Document
from flask import (Flask, abort, redirect, render_template_string, request,
                   send_file, session, url_for)
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

DEMO_USER = "demo"
DEMO_PASSWORD = "demo123"
PAGE_SIZE = 10

FIRST = ["Ava", "Liam", "Maya", "Noah", "Zara", "Ethan", "Chloe", "Marcus", "Priya", "Jordan",
         "Sofia", "Andre", "Keisha", "Daniel", "Lena", "Omar", "Grace", "Tyrone", "Mei", "Lucas"]
LAST = ["Campbell", "Reid", "Thompson", "Patel", "Brown", "Clarke", "Nguyen", "Williams",
        "Garcia", "Henry", "O'Neil", "Lindo", "Foster", "Kim", "Morgan", "Bailey", "Silva"]
TITLES = ["Software Engineer", "Data Analyst", "Registered Nurse", "Project Manager",
          "Accountant", "Senior Software Engineer", "Marketing Coordinator", "DevOps Engineer"]
LOCATIONS = ["Kingston", "Montego Bay", "Toronto", "Miami", "London", "Remote"]


def build_candidates(n: int = 45, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    people = []
    for i in range(1, n + 1):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        cid = 1000 + i
        if i % 11 == 0:
            resume = None            # some profiles have no resume uploaded
        elif i % 4 == 0:
            resume = "docx"          # some resumes are uploaded as Word files
        else:
            resume = "pdf"
        people.append({
            "id": cid,
            "first_name": first,
            "last_name": last,
            "email": f"{first}.{last}{i}@example.com".lower().replace("'", ""),
            "phone": f"+1 (876) {rng.randint(200, 999)}-{rng.randint(1000, 9999)}",
            "job_title": rng.choice(TITLES),
            "location": rng.choice(LOCATIONS),
            "resume": resume,
        })
    # one deliberately messy record: spreadsheet-formula-looking title and stray whitespace
    people[2]["job_title"] = "=Senior Software Engineer"
    people[5]["first_name"] = "  " + people[5]["first_name"] + " "
    return people


CANDIDATES = build_candidates()
BY_ID = {c["id"]: c for c in CANDIDATES}

LAYOUT = """<!doctype html><html><head><title>TalentVault Demo</title>
<style>body{font-family:system-ui;margin:2rem;max-width:900px}table{border-collapse:collapse;width:100%}
td,th{border-bottom:1px solid #ddd;padding:.4rem;text-align:left}.err{color:#b00}</style></head>
<body><header><strong>TalentVault</strong> (demo data)
{% if session.get('user') %} · <a href="{{ url_for('logout') }}" id="logout">Log out</a>{% endif %}</header>
{{ body|safe }}</body></html>"""


def page(body: str, **ctx) -> str:
    return render_template_string(LAYOUT, body=render_template_string(body, **ctx))


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("DEMO_PORTAL_SECRET", "demo-only-secret")

    @app.route("/")
    def home():
        return redirect(url_for("candidates"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            if (request.form.get("username") == DEMO_USER
                    and request.form.get("password") == DEMO_PASSWORD):
                session["user"] = DEMO_USER
                return redirect(request.args.get("next") or url_for("candidates"))
            error = "Invalid username or password."
        return page("""<h1>Sign in</h1>{% if error %}<p class="err" id="login-error">{{ error }}</p>{% endif %}
<form method="post"><label>Username <input id="username" name="username"></label>
<label>Password <input id="password" name="password" type="password"></label>
<button type="submit" id="login-btn">Sign in</button></form>""", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/candidates")
    @login_required
    def candidates():
        title = request.args.get("title", "").strip().lower()
        location = request.args.get("location", "")
        results = [c for c in CANDIDATES
                   if title in c["job_title"].lower() and (not location or c["location"] == location)]
        page_no = max(1, request.args.get("page", 1, type=int))
        pages = max(1, -(-len(results) // PAGE_SIZE))
        rows = results[(page_no - 1) * PAGE_SIZE: page_no * PAGE_SIZE]
        return page("""<h1>Candidates</h1>
<form method="get" id="filters"><input id="filter-title" name="title" placeholder="Job title" value="{{ request.args.get('title','') }}">
<select id="filter-location" name="location"><option value="">Any location</option>
{% for loc in locations %}<option {% if loc==request.args.get('location') %}selected{% endif %}>{{ loc }}</option>{% endfor %}</select>
<button type="submit" id="apply-filters">Search</button></form>
<p id="result-count">{{ total }} candidates</p>
<table><tr><th>Name</th><th>Job title</th><th>Location</th></tr>
{% for c in rows %}<tr class="candidate-row" data-id="{{ c.id }}"><td><a class="profile-link" href="{{ url_for('profile', cid=c.id) }}">{{ c.first_name }} {{ c.last_name }}</a></td>
<td>{{ c.job_title }}</td><td>{{ c.location }}</td></tr>{% endfor %}</table>
<p>Page {{ page_no }} of {{ pages }}
{% if page_no < pages %}<a class="next" href="{{ url_for('candidates', title=request.args.get('title',''), location=request.args.get('location',''), page=page_no+1) }}">Next &rsaquo;</a>{% endif %}</p>""",
                    rows=rows, total=len(results), page_no=page_no, pages=pages, locations=LOCATIONS)

    @app.route("/candidates/<int:cid>")
    @login_required
    def profile(cid: int):
        c = BY_ID.get(cid) or abort(404)
        return page("""<h1>Candidate profile</h1><dl id="profile" data-id="{{ c.id }}">
<dt>First name</dt><dd data-field="first_name">{{ c.first_name }}</dd>
<dt>Last name</dt><dd data-field="last_name">{{ c.last_name }}</dd>
<dt>Email</dt><dd data-field="email">{{ c.email }}</dd>
<dt>Phone</dt><dd data-field="phone">{{ c.phone }}</dd>
<dt>Job title</dt><dd data-field="job_title">{{ c.job_title }}</dd>
<dt>Location</dt><dd data-field="location">{{ c.location }}</dd></dl>
{% if c.resume %}<a id="resume-link" href="{{ url_for('resume', cid=c.id) }}">Download resume</a>
{% else %}<p id="no-resume">No resume on file.</p>{% endif %}""", c=c)

    @app.route("/candidates/<int:cid>/resume")
    @login_required
    def resume(cid: int):
        c = BY_ID.get(cid) or abort(404)
        if not c["resume"]:
            abort(404)
        stem = f"resume_{c['id']}"
        if c["resume"] == "pdf":
            return send_file(io.BytesIO(make_pdf(c)), mimetype="application/pdf",
                             as_attachment=True, download_name=f"{stem}.pdf")
        return send_file(io.BytesIO(make_docx(c)), as_attachment=True, download_name=f"{stem}.docx",
                         mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    return app


def resume_lines(c: dict) -> list[str]:
    name = f"{c['first_name'].strip()} {c['last_name']}"
    return [name, c["job_title"].lstrip("="), f"{c['email']}  |  {c['phone']}  |  {c['location']}", "",
            "Summary", f"Fictional demo candidate #{c['id']} generated for testing the exporter.", "",
            "Experience", "- Delivered projects on time across cross-functional teams",
            "- Improved processes and reporting accuracy"]


def make_pdf(c: dict) -> bytes:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=LETTER)
    y = 740
    for i, line in enumerate(resume_lines(c)):
        pdf.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 16 if i == 0 else 11)
        pdf.drawString(72, y, line)
        y -= 22 if i == 0 else 16
    pdf.save()
    return buf.getvalue()


def make_docx(c: dict) -> bytes:
    doc = Document()
    lines = resume_lines(c)
    doc.add_heading(lines[0], level=1)
    for line in lines[1:]:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


if __name__ == "__main__":
    print(f"Demo portal on http://127.0.0.1:5055  (login: {DEMO_USER} / {DEMO_PASSWORD})")
    create_app().run(host="127.0.0.1", port=5055)

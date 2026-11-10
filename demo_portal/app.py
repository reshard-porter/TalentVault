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

from flask import Flask, abort, redirect, render_template, request, send_file, session, url_for

from .content import avatar_png, resume_details
from .resumes import make_docx, make_pdf

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
        return render_template("login.html", error=error, faces=[1001, 1004, 1007, 1012, 1016])

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
        with_resume = sum(1 for c in CANDIDATES if c["resume"])
        stats = {"total": len(CANDIDATES), "resumes": with_resume,
                 "resume_pct": round(100 * with_resume / len(CANDIDATES)),
                 "locations": len({c["location"] for c in CANDIDATES})}
        return render_template("candidates.html", rows=rows, total=len(results), page_no=page_no,
                               pages=pages, locations=LOCATIONS, stats=stats, active="candidates")

    @app.route("/candidates/<int:cid>")
    @login_required
    def profile(cid: int):
        c = BY_ID.get(cid) or abort(404)
        return render_template("profile.html", c=c, info=resume_details(c["id"], c["job_title"]),
                               active="candidates")

    @app.route("/avatars/<int:cid>.png")
    def avatar(cid: int):
        c = BY_ID.get(cid) or abort(404)
        resp = send_file(io.BytesIO(avatar_png(cid, 240, c["first_name"])), mimetype="image/png")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

    @app.route("/candidates/<int:cid>/resume")
    @login_required
    def resume(cid: int):
        c = BY_ID.get(cid) or abort(404)
        if not c["resume"]:
            abort(404)
        stem = f"resume_{c['id']}"
        if c["resume"] == "pdf":
            inline = request.args.get("inline") == "1"
            return send_file(io.BytesIO(make_pdf(c)), mimetype="application/pdf",
                             as_attachment=not inline, download_name=f"{stem}.pdf")
        return send_file(io.BytesIO(make_docx(c)), as_attachment=True, download_name=f"{stem}.docx",
                         mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    return app


if __name__ == "__main__":
    print(f"Demo portal on http://127.0.0.1:5055  (login: {DEMO_USER} / {DEMO_PASSWORD})")
    create_app().run(host="127.0.0.1", port=5055)

"""A small, login-protected recruiting portal used to demonstrate and test the exporter.

It imitates the shape of a typical applicant-tracking / candidate-database site:
login form -> search filters -> paginated results -> candidate profile -> resume download.
All people and documents are fictional and generated deterministically.

Run it with:  python -m demo_portal.app      (http://127.0.0.1:5055, login demo / demo123)
"""
from __future__ import annotations

import csv
import io
import os
import random
import re
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, Response, abort, flash, redirect, render_template, request, send_file,
                   session, url_for)

from .content import ROLE_DATA, avatar_png, clean_title, resume_details
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

STATUSES = ["Open", "Interviewing", "On hold"]
JOB_TYPES = ["Full-time", "Part-time", "Contract", "Internship"]
DEPARTMENTS = {"Software Engineer": "Engineering", "Senior Software Engineer": "Engineering",
               "DevOps Engineer": "Engineering", "Data Analyst": "Analytics", "Registered Nurse": "Healthcare",
               "Project Manager": "Operations", "Accountant": "Finance", "Marketing Coordinator": "Marketing"}
SALARIES = {"Software Engineer": "$70k – $95k", "Senior Software Engineer": "$110k – $140k",
            "DevOps Engineer": "$90k – $120k", "Data Analyst": "$55k – $75k", "Registered Nurse": "$60k – $82k",
            "Project Manager": "$75k – $100k", "Accountant": "$50k – $70k", "Marketing Coordinator": "$42k – $55k"}
TIMEZONES = ["America/Jamaica", "America/New_York", "America/Toronto", "America/Chicago",
             "America/Los_Angeles", "Europe/London", "UTC"]
NOTIFICATION_OPTIONS = [
    ("notify_new_candidate", "New candidates", "Email me when a candidate matches an open job"),
    ("notify_resume", "Resume uploads", "Email me when a candidate uploads a new resume"),
    ("notify_weekly", "Weekly report", "Send a summary every Monday morning"),
]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "job"


def build_jobs() -> list[dict]:
    jobs = []
    for i, title in enumerate(TITLES):
        role = ROLE_DATA[title]
        jobs.append({
            "slug": slugify(title), "title": title, "department": DEPARTMENTS[title],
            "location": LOCATIONS[i % len(LOCATIONS)], "type": "Contract" if i == 6 else "Full-time",
            "status": STATUSES[[0, 0, 1, 0, 2, 1, 0, 0][i]], "salary": SALARIES[title],
            "posted": (date(2026, 11, 9) - timedelta(days=3 + i * 4)).strftime("%b %d, %Y"),
            "description": f"We are hiring {'an' if title[0] in 'AEIOU' else 'a'} {title} to join our "
                           f"{DEPARTMENTS[title]} team. The ideal candidate: {role['summary'][0].lower()}{role['summary'][1:]}",
            "skills": role["skills"],
        })
    return jobs


JOBS = build_jobs()
SETTINGS = {"full_name": "Demo Recruiter", "email": "recruiter@talentvault.example", "role": "Talent Acquisition Lead",
            "company": "TalentVault Demo", "page_size": PAGE_SIZE, "timezone": "America/Jamaica",
            "notify_new_candidate": True, "notify_resume": True, "notify_weekly": False}


def applicants_for(title: str) -> list[dict]:
    return [c for c in CANDIDATES if clean_title(c["job_title"]).lower() == title.lower()]

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

    @app.context_processor
    def inject_settings():
        initials = "".join(w[0] for w in SETTINGS["full_name"].split()[:2]).upper() or "?"
        return {"settings": {**SETTINGS, "initials": initials}}

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
        size = SETTINGS["page_size"]
        pages = max(1, -(-len(results) // size))
        rows = results[(page_no - 1) * size: page_no * size]
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

    @app.route("/jobs")
    @login_required
    def jobs():
        status = request.args.get("status", "all")
        listed = [j for j in JOBS if status == "all" or j["status"] == status]
        counts = {"all": len(JOBS), **{s: sum(1 for j in JOBS if j["status"] == s) for s in STATUSES}}
        return render_template("jobs.html", jobs=[{**j, "applicants": applicants_for(j["title"])} for j in listed],
                               status=status, counts=counts, active="jobs")

    @app.route("/jobs/new", methods=["GET", "POST"])
    @login_required
    def new_job():
        form = {"title": "", "department": "", "location": LOCATIONS[0], "type": JOB_TYPES[0],
                "salary": "", "status": "Open", "description": ""}
        if request.method == "POST":
            form.update({k: request.form.get(k, "").strip() for k in form})
            if not form["title"] or not form["department"]:
                flash("Job title and department are required.", "error")
            else:
                slug, n = slugify(form["title"]), 2
                while any(j["slug"] == slug for j in JOBS):
                    slug, n = f"{slugify(form['title'])}-{n}", n + 1
                known = ROLE_DATA.get(form["title"], {})
                JOBS.insert(0, {**form, "slug": slug, "salary": form["salary"] or "Not specified",
                                "description": form["description"] or "No description yet.",
                                "skills": known.get("skills", []), "posted": date.today().strftime("%b %d, %Y")})
                flash(f"“{form['title']}” was posted.")
                return redirect(url_for("job_detail", slug=slug))
        return render_template("job_form.html", form=form, locations=LOCATIONS, types=JOB_TYPES,
                               statuses=STATUSES, active="jobs")

    @app.route("/jobs/<slug>")
    @login_required
    def job_detail(slug: str):
        job = next((j for j in JOBS if j["slug"] == slug), None) or abort(404)
        return render_template("job_detail.html", job={**job, "applicants": applicants_for(job["title"])},
                               statuses=STATUSES, active="jobs")

    @app.route("/jobs/<slug>/status", methods=["POST"])
    @login_required
    def job_status(slug: str):
        job = next((j for j in JOBS if j["slug"] == slug), None) or abort(404)
        new = request.form.get("status")
        if new in STATUSES:
            job["status"] = new
            flash(f"Status changed to {new}.")
        return redirect(url_for("job_detail", slug=slug))

    @app.route("/reports")
    @login_required
    def reports():
        def tally(key):
            counts = {}
            for c in CANDIDATES:
                k = clean_title(c[key]) if key == "job_title" else c[key]
                counts[k] = counts.get(k, 0) + 1
            return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        by_title, by_location = tally("job_title"), tally("location")
        formats = {"pdf": sum(c["resume"] == "pdf" for c in CANDIDATES),
                   "docx": sum(c["resume"] == "docx" for c in CANDIDATES),
                   "none": sum(not c["resume"] for c in CANDIDATES)}
        return render_template("reports.html", total=len(CANDIDATES), by_title=by_title, by_location=by_location,
                               max_title=by_title[0][1], max_location=by_location[0][1], formats=formats,
                               resume_pct=round(100 * (formats["pdf"] + formats["docx"]) / len(CANDIDATES)),
                               open_jobs=sum(j["status"] == "Open" for j in JOBS),
                               generated=datetime.now().strftime("%b %d, %Y at %I:%M %p"), active="reports")

    @app.route("/reports/candidates.csv")
    @login_required
    def reports_csv():
        def safe(v):
            v = str(v).strip()
            return "'" + v if v[:1] in ("=", "+", "-", "@") else v
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Candidate ID", "First Name", "Last Name", "Email", "Phone", "Job Title", "Location", "Resume"])
        for c in CANDIDATES:
            writer.writerow([c["id"], safe(c["first_name"]), safe(c["last_name"]), safe(c["email"]), c["phone"],
                             safe(clean_title(c["job_title"])), c["location"], c["resume"] or "missing"])
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=talentvault_candidates.csv"})

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        if request.method == "POST":
            name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip()
            if not name or "@" not in email:
                flash("Please enter your name and a valid email.", "error")
            else:
                SETTINGS.update({"full_name": name, "email": email,
                                 "role": request.form.get("role", "").strip(),
                                 "company": request.form.get("company", "").strip()})
                size = request.form.get("page_size", type=int)
                if size in (10, 20, 50):
                    SETTINGS["page_size"] = size
                if request.form.get("timezone") in TIMEZONES:
                    SETTINGS["timezone"] = request.form["timezone"]
                for key, _, _ in NOTIFICATION_OPTIONS:
                    SETTINGS[key] = key in request.form
                flash("Settings saved.")
            return redirect(url_for("settings"))
        return render_template("settings.html", notification_options=NOTIFICATION_OPTIONS,
                               timezones=TIMEZONES, active="settings")

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

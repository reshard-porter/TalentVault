"""Deterministic, fictional resume content and illustrated portraits for demo candidates."""
from __future__ import annotations

import io
import random
from functools import lru_cache

from PIL import Image, ImageDraw

ROLE_DATA = {
    "Software Engineer": {
        "skills": ["Python", "JavaScript", "REST APIs", "PostgreSQL", "Docker", "Git", "Unit Testing", "Agile"],
        "summary": "Software engineer who builds reliable web services and internal tools, with a focus on clean code, automated testing and steady delivery.",
        "bullets": ["Built and maintained REST APIs serving {n}k+ daily requests",
                    "Cut page load times by {p}% by profiling queries and adding caching",
                    "Introduced automated tests that raised coverage to {c}%",
                    "Mentored junior developers through code reviews and pairing"],
        "degree": "B.Sc. Computer Science",
    },
    "Senior Software Engineer": {
        "skills": ["System Design", "Python", "Go", "AWS", "Kubernetes", "CI/CD", "Technical Leadership", "Microservices"],
        "summary": "Senior engineer who leads the design of scalable systems and helps teams ship dependable software faster.",
        "bullets": ["Led a team of {t} engineers through a migration to microservices",
                    "Designed an event pipeline processing {n}M records per day",
                    "Reduced cloud costs by {p}% through right-sizing and autoscaling",
                    "Defined engineering standards adopted across {t} product teams"],
        "degree": "M.Sc. Software Engineering",
    },
    "DevOps Engineer": {
        "skills": ["AWS", "Terraform", "Kubernetes", "Linux", "GitHub Actions", "Monitoring", "Bash", "Security"],
        "summary": "DevOps engineer who automates infrastructure and deployments so teams can release safely several times a day.",
        "bullets": ["Automated deployments, taking release time from hours to {m} minutes",
                    "Managed infrastructure as code for {t} production environments",
                    "Raised service uptime to 99.{u}% with proactive alerting",
                    "Hardened cloud accounts and passed {t} external security audits"],
        "degree": "B.Sc. Information Technology",
    },
    "Data Analyst": {
        "skills": ["SQL", "Excel", "Power BI", "Python", "Pandas", "Data Visualization", "Statistics", "Reporting"],
        "summary": "Data analyst who turns raw business data into clear dashboards and recommendations that leaders act on.",
        "bullets": ["Built {t} executive dashboards used in weekly leadership meetings",
                    "Automated monthly reporting, saving {h} staff hours per month",
                    "Identified pricing insights that lifted margin by {p}%",
                    "Cleaned and merged {n}k customer records from three systems"],
        "degree": "B.Sc. Statistics",
    },
    "Registered Nurse": {
        "skills": ["Patient Assessment", "Critical Care", "Medication Administration", "EHR Systems", "Triage", "Patient Education", "BLS / ACLS", "Teamwork"],
        "summary": "Compassionate registered nurse experienced in fast-paced hospital units, known for calm triage and clear patient communication.",
        "bullets": ["Cared for up to {t} patients per shift on a busy medical-surgical unit",
                    "Trained {t} new nurses on charting and safety protocols",
                    "Helped lower medication errors by {p}% through double-check routines",
                    "Recognized by patients and peers for outstanding bedside care"],
        "degree": "B.Sc. Nursing",
    },
    "Project Manager": {
        "skills": ["Project Planning", "Stakeholder Management", "Budgeting", "Risk Management", "Jira", "Scrum", "Reporting", "Vendor Management"],
        "summary": "Project manager who keeps complex, multi-team projects on schedule and on budget through clear plans and communication.",
        "bullets": ["Delivered {t} projects worth ${n}M on time and under budget",
                    "Coordinated {t} cross-functional teams across three time zones",
                    "Introduced a risk register that cut late-stage surprises by {p}%",
                    "Ran weekly stakeholder updates for senior leadership"],
        "degree": "B.B.A. Management, PMP",
    },
    "Accountant": {
        "skills": ["Financial Reporting", "Reconciliations", "QuickBooks", "Excel", "Tax Preparation", "Auditing", "IFRS", "Budgeting"],
        "summary": "Detail-oriented accountant who produces accurate, timely financial statements and keeps books audit-ready.",
        "bullets": ["Closed monthly books {m} days faster through process improvements",
                    "Prepared financial statements for {t} business units",
                    "Supported external audits with zero material findings",
                    "Reconciled {n}k transactions per quarter across multiple accounts"],
        "degree": "B.Sc. Accounting, ACCA",
    },
    "Marketing Coordinator": {
        "skills": ["Social Media", "Email Marketing", "Content Writing", "Canva", "Google Analytics", "SEO", "Event Planning", "HubSpot"],
        "summary": "Marketing coordinator who plans campaigns, creates engaging content and measures what works.",
        "bullets": ["Grew social media following by {p}% in twelve months",
                    "Ran email campaigns with a {c}% average open rate",
                    "Coordinated {t} launch events with partners and vendors",
                    "Produced weekly content calendars for three brands"],
        "degree": "B.A. Marketing & Communications",
    },
}
GENERIC_BULLETS = ["Partnered with managers to set quarterly goals and track progress",
                   "Documented processes so new team members could ramp up faster",
                   "Consistently rated 'exceeds expectations' in annual reviews",
                   "Represented the team in cross-department planning meetings"]
FEMININE = {"Ava", "Maya", "Zara", "Chloe", "Priya", "Sofia", "Keisha", "Lena", "Grace", "Mei"}
COMPANIES = ["Northwind Labs", "Bluepeak Systems", "Caribbean Data Co.", "Harbor Health", "Summit Partners",
             "Lumen Digital", "Coral Bay Group", "Atlas Logistics", "Brightline Media", "Island Tech Hub"]
SCHOOLS = ["University of the West Indies", "University of Technology, Jamaica", "University of Toronto",
           "Florida International University", "Northern Caribbean University"]
LANGUAGES = [["English (native)"], ["English (native)", "Spanish (conversational)"],
             ["English (native)", "French (basic)"]]

# Accent colours used for each candidate's resume sidebar and avatar backdrop
PALETTES = [("#1F3A5F", "#DCE7F3"), ("#234E52", "#D7EEEA"), ("#3C2A5D", "#E6DFF3"),
            ("#5B2C2C", "#F3E1DC"), ("#2D3A2E", "#E1ECDD"), ("#1E3D59", "#F5E9D7")]
SKIN = ["#F1C9A5", "#E0AC84", "#C68863", "#A0673F", "#7C4A2D", "#5A3420"]
HAIR = ["#1B1B1B", "#3B2A20", "#5E3B22", "#8A5A2B", "#B5884D", "#2A1E16"]
SHIRTS = ["#2F4858", "#33658A", "#86BBD8", "#758E4F", "#F6AE2D", "#55505C", "#9E2B25"]


def clean_title(title: str) -> str:
    return title.lstrip("=").strip()


@lru_cache(maxsize=None)
def resume_details(cid: int, title: str) -> dict:
    title = clean_title(title)
    role = ROLE_DATA.get(title, ROLE_DATA["Software Engineer"])
    rng = random.Random(cid)
    fill = dict(n=rng.randint(2, 40), p=rng.randint(12, 45), c=rng.randint(70, 92), t=rng.randint(3, 12),
                m=rng.randint(8, 30), u=rng.randint(5, 9), h=rng.randint(20, 80))
    end = 2026
    jobs = []
    companies = rng.sample(COMPANIES, 3)
    pool = rng.sample(role["bullets"], len(role["bullets"]))
    generic = rng.sample(GENERIC_BULLETS, len(GENERIC_BULLETS))
    bullet_sets = [pool[:3], [pool[3], generic[0]], generic[1:3]]   # no bullet repeats across jobs
    for i, company in enumerate(companies):
        span = rng.randint(2, 4) if i < 2 else rng.randint(1, 2)
        start = end - span
        bullets = bullet_sets[i]
        jobs.append({
            "title": title if i == 0 else ("Junior " + title.replace("Senior ", "") if i == 2 and "Senior" not in title and "Registered" not in title else title.replace("Senior ", "")),
            "company": company,
            "dates": f"{start} – {'Present' if i == 0 else end}",
            "bullets": [b.format(**fill) for b in bullets],
        })
        end = start
    grad = end - rng.randint(0, 1)
    return {
        "summary": role["summary"],
        "skills": role["skills"],
        "jobs": jobs,
        "education": {"degree": role["degree"], "school": rng.choice(SCHOOLS), "year": str(grad)},
        "languages": rng.choice(LANGUAGES),
        "palette": PALETTES[cid % len(PALETTES)],
    }


@lru_cache(maxsize=None)
def avatar_png(cid: int, size: int = 400, first_name: str = "") -> bytes:
    """Illustrated head-and-shoulders portrait, drawn at 3x and downsampled for smooth edges."""
    rng = random.Random(cid * 7919)
    s = size * 3
    accent, light = PALETTES[cid % len(PALETTES)]
    skin, hair, shirt = rng.choice(SKIN), rng.choice(HAIR), rng.choice(SHIRTS)
    # styles: 0 side part, 1 curly, 2 long, 3 close crop
    style = rng.choice([0, 1, 2, 2]) if first_name.strip() in FEMININE else rng.choice([0, 1, 3, 3])

    img = Image.new("RGB", (s, s), light)
    d = ImageDraw.Draw(img)
    # soft backdrop circle
    d.ellipse([s * .08, s * .08, s * .92, s * .92], fill=_mix(light, accent, .18))

    cx = s / 2
    # shoulders / shirt
    d.ellipse([cx - s * .40, s * .70, cx + s * .40, s * 1.25], fill=shirt)
    # collar
    d.polygon([(cx - s * .09, s * .70), (cx, s * .80), (cx + s * .09, s * .70)], fill="#FFFFFF")
    # neck
    d.rectangle([cx - s * .07, s * .56, cx + s * .07, s * .72], fill=_mix(skin, "#000000", .12))
    # long hair behind head
    if style == 2:
        d.rounded_rectangle([cx - s * .21, s * .26, cx + s * .21, s * .70], radius=s * .1, fill=hair)
    # head
    d.ellipse([cx - s * .17, s * .24, cx + s * .17, s * .64], fill=skin)
    # ears
    for side in (-1, 1):
        d.ellipse([cx + side * s * .17 - s * .03, s * .42, cx + side * s * .17 + s * .03, s * .50], fill=skin)
    # hair on top
    if style == 3:   # close crop
        d.chord([cx - s * .175, s * .22, cx + s * .175, s * .50], 180, 360, fill=hair)
    elif style == 1:  # curly
        for i in range(9):
            x = cx - s * .17 + i * s * .0425
            d.ellipse([x - s * .05, s * .20, x + s * .05, s * .32], fill=hair)
        d.chord([cx - s * .18, s * .22, cx + s * .18, s * .46], 180, 360, fill=hair)
    else:            # side part / long
        d.chord([cx - s * .185, s * .20, cx + s * .185, s * .50], 180, 360, fill=hair)
        d.polygon([(cx - s * .18, s * .36), (cx + s * .05, s * .27), (cx - s * .18, s * .30)], fill=hair)
    # simple face
    eye = "#2B2B2B"
    for side in (-1, 1):
        ex = cx + side * s * .065
        d.ellipse([ex - s * .014, s * .43, ex + s * .014, s * .458], fill=eye)
    d.arc([cx - s * .06, s * .48, cx + s * .06, s * .56], 20, 160, fill=_mix(skin, "#7A2E2E", .55), width=int(s * .012))

    img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _mix(a: str, b: str, t: float) -> str:
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))

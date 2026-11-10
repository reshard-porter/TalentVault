"""End-to-end tests: a real headless browser against the bundled demo portal."""
from __future__ import annotations

import socket
import threading
import zipfile
from pathlib import Path

import openpyxl
import pytest
from werkzeug.serving import make_server

from demo_portal.app import CANDIDATES, create_app
from exporter.config import Config
from exporter.runner import run_export
from exporter.sites import LoginError
from exporter.state import Checkpoint


@pytest.fixture(scope="module")
def portal_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = make_server("127.0.0.1", port, create_app(), threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def make_cfg(url: str, out: Path, **overrides) -> Config:
    cfg = Config(adapter="demo_portal", base_url=url, username="demo", password="demo123",
                 filters={"job_title": "Engineer"}, output_dir=out, delay_seconds=0, retries=1)
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def expected(title: str = "engineer", location: str | None = None) -> list[dict]:
    return [c for c in CANDIDATES
            if title in c["job_title"].lower() and (not location or c["location"] == location)]


def sheet_rows(path: Path) -> list[dict]:
    ws = openpyxl.load_workbook(path).active
    headers = [c.value for c in ws[1]]
    return [dict(zip(headers, row)) for row in ws.iter_rows(min_row=2, values_only=True)]


def test_full_export_creates_two_folders(portal_url, tmp_path):
    result = run_export(make_cfg(portal_url, tmp_path))
    want = expected()

    assert result.excel_file.parent == tmp_path / "Excel Data"
    rows = sheet_rows(result.excel_file)
    assert len(rows) == len(want) == result.records
    assert {r["Candidate ID"] for r in rows} == {str(c["id"]) for c in want}
    for col in ("First Name", "Last Name", "Email Address", "Phone Number", "Job Title"):
        assert all(r[col] for r in rows), col

    pdfs = sorted((tmp_path / "PDF").glob("*.pdf"))
    with_resume = [c for c in want if c["resume"]]
    assert len(pdfs) == len(with_resume) == result.pdfs
    assert any(c["resume"] == "docx" for c in with_resume)        # Word uploads were converted
    assert all(p.read_bytes()[:5] == b"%PDF-" for p in pdfs)
    linked = {r["Resume PDF"] for r in rows if r["Resume PDF"]}
    assert linked == {p.name for p in pdfs}                        # every PDF matches a spreadsheet row
    assert not result.failed


def test_values_are_cleaned_and_never_formulas(portal_url, tmp_path):
    result = run_export(make_cfg(portal_url, tmp_path))
    rows = {r["Candidate ID"]: r for r in sheet_rows(result.excel_file)}
    assert rows["1003"]["Job Title"] == "=Senior Software Engineer"   # kept as text
    xml = zipfile.ZipFile(result.excel_file).read("xl/worksheets/sheet1.xml").decode()
    assert "<f>" not in xml
    messy = CANDIDATES[5]
    if str(messy["id"]) in rows:
        assert rows[str(messy["id"])]["First Name"] == messy["first_name"].strip()


def test_location_filter(portal_url, tmp_path):
    result = run_export(make_cfg(portal_url, tmp_path, filters={"job_title": "", "location": "Remote"}))
    assert result.records == len(expected("", "Remote"))


def test_wrong_password_fails_clearly(portal_url, tmp_path):
    with pytest.raises(LoginError):
        run_export(make_cfg(portal_url, tmp_path, password="wrong"))


def test_interrupted_run_resumes_without_duplicates(portal_url, tmp_path):
    first = run_export(make_cfg(portal_url, tmp_path, max_records=4))
    # simulate a crash after 4 profiles: put the finished checkpoint back
    cfg = make_cfg(portal_url, tmp_path)
    import json
    key = json.dumps([cfg.adapter, cfg.base_url, cfg.filters], sort_keys=True)
    cp = Checkpoint(tmp_path / ".state" / "checkpoint.json", key)
    for row in sheet_rows(first.excel_file):
        cp.add({"id": row["Candidate ID"], "first_name": row["First Name"], "last_name": row["Last Name"],
                "email": row["Email Address"], "phone": row["Phone Number"], "job_title": row["Job Title"],
                "resume_file": row["Resume PDF"] or "", "profile_url": row["Profile URL"],
                "collected_at": row["Collected At (UTC)"]})

    second = run_export(cfg)
    assert second.resumed_from_checkpoint
    rows = sheet_rows(second.excel_file)
    assert len(rows) == len(expected())
    assert len({r["Candidate ID"] for r in rows}) == len(rows)
    assert not (tmp_path / ".state" / "checkpoint.json").exists()   # cleared after a clean finish


def test_every_portal_page_and_link_works():
    """Crawl the portal while signed in: every internal link must load, and no link may be a dead '#'."""
    import re
    client = create_app().test_client()
    client.post("/login", data={"username": "demo", "password": "demo123"})
    queue, seen = ["/candidates", "/jobs", "/reports", "/settings", "/jobs/new"], set()
    while queue:
        url = queue.pop()
        if url in seen or "/logout" in url:
            continue
        seen.add(url)
        resp = client.get(url)
        assert resp.status_code == 200, url
        if resp.mimetype == "text/html":
            html = resp.get_data(as_text=True)
            assert 'href="#"' not in html, url
            queue += [h.replace("&amp;", "&") for h in re.findall(r'href="(/[^"]*)"', html)]
    assert len(seen) > 50
    resp = client.post("/settings", data={"full_name": "Test User", "email": "t@example.com", "page_size": "10"},
                       follow_redirects=True)
    assert b"Settings saved" in resp.data and b"Test User" in resp.data

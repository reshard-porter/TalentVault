"""Orchestrates one export run: log in, filter, visit each profile, save the resume, write Excel."""
from __future__ import annotations

import json
import logging
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from .config import Config
from .documents import ConversionError, safe_filename, save_as_pdf
from .excel import write_workbook
from .sites import get_adapter
from .state import Checkpoint

log = logging.getLogger("exporter")
REQUIRED = ("first_name", "last_name")


@dataclass
class RunResult:
    excel_file: Path | None = None
    records: int = 0
    pdfs: int = 0
    no_resume: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    duplicates: int = 0
    resumed_from_checkpoint: bool = False


def setup_logging(output_dir: Path, stamp: datetime) -> Path:
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"run_{stamp:%Y-%m-%d_%H%M%S}.log"
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S")
    log.handlers.clear()
    log.setLevel(logging.INFO)
    for handler in (logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return log_file


def with_retries(action, attempts: int, what: str):
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except (PlaywrightError, TimeoutError) as exc:
            if attempt == attempts:
                raise
            wait = 2 ** attempt
            log.warning("%s failed (attempt %d/%d): %s. Retrying in %ds",
                        what, attempt, attempts, str(exc).splitlines()[0], wait)
            time.sleep(wait)


def run_export(cfg: Config, fresh: bool = False) -> RunResult:
    stamp = datetime.now()   # local time for file names; collected_at stays UTC
    log_file = setup_logging(cfg.output_dir, stamp)
    adapter = get_adapter(cfg.adapter, cfg.base_url)
    job_key = json.dumps([cfg.adapter, cfg.base_url, cfg.filters], sort_keys=True)
    checkpoint = Checkpoint(cfg.output_dir / ".state" / "checkpoint.json", job_key)
    if fresh:
        checkpoint.clear()

    result = RunResult(resumed_from_checkpoint=checkpoint.resumed)
    if checkpoint.resumed:
        log.info("Resuming previous run: %d candidates already collected", len(checkpoint.records))
    seen_emails = {r["email"].lower() for r in checkpoint.records.values() if r.get("email")}

    log.info("Site: %s (%s)  Filters: %s", cfg.adapter, cfg.base_url, cfg.filters or "none")
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch(headless=cfg.headless)
        context = browser.new_context(accept_downloads=True)
        context.set_default_timeout(cfg.timeout_seconds * 1000)
        page = context.new_page()
        try:
            with_retries(lambda: adapter.login(page, cfg.username, cfg.password), cfg.retries, "Login")
            log.info("Logged in")
            total = with_retries(lambda: adapter.apply_filters(page, cfg.filters), cfg.retries, "Filtering")
            log.info("Filtered results: %s", total if total is not None else "unknown")

            urls = list(dict.fromkeys(adapter.iter_profile_urls(page)))   # ordered, de-duplicated
            if cfg.max_records:
                urls = urls[: cfg.max_records]
            log.info("Profiles to process: %d", len(urls))

            profile_page = context.new_page()
            for n, url in enumerate(urls, start=1):
                try:
                    with_retries(lambda: profile_page.goto(url), cfg.retries, f"Opening {url}")
                    rec = adapter.read_profile(profile_page)
                    rec["id"] = str(rec.get("id") or url.rstrip("/").rsplit("/", 1)[-1])
                    if checkpoint.has(rec["id"]):
                        continue
                    if any(not rec.get(f) for f in REQUIRED):
                        raise ValueError(f"missing {', '.join(f for f in REQUIRED if not rec.get(f))}")
                    email = rec.get("email", "").lower()
                    if email and email in seen_emails:
                        result.duplicates += 1
                        log.info("[%d/%d] Skipped duplicate email %s", n, len(urls), email)
                        continue

                    rec["profile_url"] = url
                    rec["collected_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    rec["resume_file"] = ""
                    link = adapter.resume_link(profile_page)
                    if link is None:
                        result.no_resume.append(rec["id"])
                        log.info("[%d/%d] %s %s: no resume on file", n, len(urls), rec["first_name"], rec["last_name"])
                    else:
                        def download():
                            with profile_page.expect_download() as info:
                                link.click()
                            dl = info.value
                            local = Path(tmp) / f"dl_{rec['id']}"
                            dl.save_as(local)
                            return local, dl.suggested_filename
                        local, original = with_retries(download, cfg.retries, f"Resume download {rec['id']}")
                        name = safe_filename(rec["last_name"], rec["first_name"], rec["id"]) + ".pdf"
                        save_as_pdf(local, original, cfg.pdf_dir / name)
                        rec["resume_file"] = name
                        log.info("[%d/%d] %s %s: saved %s", n, len(urls), rec["first_name"], rec["last_name"], name)

                    if email:
                        seen_emails.add(email)
                    checkpoint.add(rec)
                except (PlaywrightError, ValueError, ConversionError, OSError) as exc:
                    result.failed.append(url)
                    log.error("[%d/%d] Failed %s: %s", n, len(urls), url, str(exc).splitlines()[0])
                if cfg.delay_seconds:
                    time.sleep(cfg.delay_seconds)
        finally:
            browser.close()

    records = sorted(checkpoint.records.values(), key=lambda r: (r["last_name"].lower(), r["first_name"].lower()))
    result.records = len(records)
    result.pdfs = sum(1 for r in records if r.get("resume_file"))
    result.excel_file = write_workbook(records, cfg.excel_dir, cfg.pdf_dir, stamp)
    if not result.failed:
        checkpoint.clear()   # finished cleanly; next run starts fresh

    log.info("Done. %d contacts -> %s", result.records, result.excel_file)
    log.info("%d resumes -> %s  (%d without a resume, %d duplicates skipped, %d failed)",
             result.pdfs, cfg.pdf_dir, result.records - result.pdfs, result.duplicates, len(result.failed))
    if result.failed:
        log.warning("Some profiles failed. Run again to retry only those. Details: %s", log_file)
    return result

from __future__ import annotations

from typing import Iterator
from urllib.parse import urljoin

from playwright.sync_api import Locator, Page

from .base import LoginError, SiteAdapter


class DemoPortalAdapter(SiteAdapter):
    """Adapter for the bundled TalentVault demo portal."""

    name = "demo_portal"
    FIELDS = ("first_name", "last_name", "email", "phone", "job_title")

    def login(self, page: Page, username: str, password: str) -> None:
        page.goto(f"{self.base_url}/login")
        page.fill("#username", username)
        page.fill("#password", password)
        page.click("#login-btn")
        page.wait_for_load_state("domcontentloaded")
        if page.locator("#login-error").count():
            raise LoginError(page.inner_text("#login-error"))

    def apply_filters(self, page: Page, filters: dict) -> int | None:
        page.goto(f"{self.base_url}/candidates")
        if filters.get("job_title"):
            page.fill("#filter-title", str(filters["job_title"]))
        if filters.get("location"):
            page.select_option("#filter-location", str(filters["location"]))
        page.click("#apply-filters")
        page.wait_for_selector("#result-count")
        text = page.inner_text("#result-count").split()[0]
        return int(text) if text.isdigit() else None

    def iter_profile_urls(self, page: Page) -> Iterator[str]:
        while True:
            hrefs = page.eval_on_selector_all("a.profile-link", "els => els.map(e => e.getAttribute('href'))")
            for href in hrefs:
                yield urljoin(page.url, href)
            nxt = page.locator("a.next")
            if not nxt.count():
                return
            nxt.click()
            page.wait_for_load_state("domcontentloaded")

    def read_profile(self, page: Page) -> dict:
        profile = page.locator("#profile")
        record = {"id": profile.get_attribute("data-id")}
        for field in self.FIELDS:
            loc = page.locator(f'[data-field="{field}"]')
            record[field] = loc.inner_text().strip() if loc.count() else ""
        return record

    def resume_link(self, page: Page) -> Locator | None:
        link = page.locator("#resume-link")
        return link if link.count() else None

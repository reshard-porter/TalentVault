"""Site adapters hold everything that is specific to one website (selectors, login form,
filters, pagination). The rest of the tool is generic, so supporting another portal
means writing one small adapter class instead of touching the export logic."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from playwright.sync_api import Locator, Page


class LoginError(Exception):
    pass


class SiteAdapter(ABC):
    name = "base"

    def __init__(self, base_url: str):
        self.base_url = base_url

    @abstractmethod
    def login(self, page: Page, username: str, password: str) -> None:
        """Sign in, raising LoginError on bad credentials."""

    @abstractmethod
    def apply_filters(self, page: Page, filters: dict) -> int | None:
        """Open the results list with the filters applied. Return the result count if shown."""

    @abstractmethod
    def iter_profile_urls(self, page: Page) -> Iterator[str]:
        """Yield every candidate profile URL, following pagination."""

    @abstractmethod
    def read_profile(self, page: Page) -> dict:
        """Return id, first_name, last_name, email, phone, job_title from an open profile page."""

    @abstractmethod
    def resume_link(self, page: Page) -> Locator | None:
        """Return the resume download link on an open profile, or None if there is no resume."""

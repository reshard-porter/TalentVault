"""Loads config.yaml and credentials. Credentials come from environment variables
(or a prompt), so they never live in the code or the config file."""
from __future__ import annotations

import getpass
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    adapter: str
    base_url: str
    username: str
    password: str
    filters: dict = field(default_factory=dict)
    output_dir: Path = Path("output")
    excel_folder: str = "Excel Data"
    pdf_folder: str = "PDF"
    headless: bool = True
    max_records: int = 0          # 0 = no limit
    delay_seconds: float = 0.5    # polite pause between profile visits
    retries: int = 3
    timeout_seconds: int = 30

    @property
    def excel_dir(self) -> Path:
        return self.output_dir / self.excel_folder

    @property
    def pdf_dir(self) -> Path:
        return self.output_dir / self.pdf_folder


class ConfigError(Exception):
    pass


def load_config(path: str | Path, prompt: bool = True) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}. Copy config.example.yaml to config.yaml first.")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    site, out, run = raw.get("site", {}), raw.get("output", {}), raw.get("run", {})

    for key in ("adapter", "base_url"):
        if not site.get(key):
            raise ConfigError(f"Missing site.{key} in {path}")

    user_env = site.get("username_env", "PORTAL_USERNAME")
    pass_env = site.get("password_env", "PORTAL_PASSWORD")
    username = os.environ.get(user_env)
    password = os.environ.get(pass_env)
    if not username and prompt:
        username = input(f"Username ({user_env} not set): ").strip()
    if not password and prompt:
        password = getpass.getpass(f"Password ({pass_env} not set): ")
    if not username or not password:
        raise ConfigError(f"Set {user_env} and {pass_env} environment variables with the portal login.")

    return Config(
        adapter=site["adapter"],
        base_url=site["base_url"].rstrip("/"),
        username=username,
        password=password,
        filters={k: v for k, v in (raw.get("filters") or {}).items() if v not in (None, "")},
        output_dir=Path(out.get("dir", "output")),
        excel_folder=out.get("excel_folder", "Excel Data"),
        pdf_folder=out.get("pdf_folder", "PDF"),
        headless=bool(run.get("headless", True)),
        max_records=int(run.get("max_records", 0) or 0),
        delay_seconds=float(run.get("delay_seconds", 0.5)),
        retries=max(1, int(run.get("retries", 3))),
        timeout_seconds=int(run.get("timeout_seconds", 30)),
    )

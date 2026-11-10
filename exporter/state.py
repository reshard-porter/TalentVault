"""Checkpoint file so an interrupted run picks up where it stopped instead of starting over.

The checkpoint is tied to the site and filters it was made with; changing either starts fresh.
It is removed after a run finishes successfully."""
from __future__ import annotations

import json
import os
from pathlib import Path


class Checkpoint:
    def __init__(self, path: Path, job_key: str):
        self.path = path
        self.job_key = job_key
        self.records: dict[str, dict] = {}
        self.resumed = False
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("job_key") == job_key:
                self.records = data.get("records", {})
                self.resumed = bool(self.records)

    def has(self, cid: str) -> bool:
        return cid in self.records

    def add(self, record: dict) -> None:
        self.records[record["id"]] = record
        self._save()

    def clear(self) -> None:
        self.records = {}
        if self.path.exists():
            self.path.unlink()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"job_key": self.job_key, "records": self.records}, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self.path)   # atomic, so a crash never leaves a half-written file

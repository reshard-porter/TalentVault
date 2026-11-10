"""Writes the collected contacts to a formatted .xlsx file."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

COLUMNS = [
    ("First Name", "first_name"),
    ("Last Name", "last_name"),
    ("Email Address", "email"),
    ("Phone Number", "phone"),
    ("Job Title", "job_title"),
    ("Resume PDF", "resume_file"),
    ("Candidate ID", "id"),
    ("Profile URL", "profile_url"),
    ("Collected At (UTC)", "collected_at"),
]


def as_text(value) -> str:
    return "" if value is None else str(value).strip()


def write_workbook(records: list[dict], excel_dir: Path, pdf_dir: Path, stamp: datetime) -> Path:
    excel_dir.mkdir(parents=True, exist_ok=True)
    path = excel_dir / f"candidates_{stamp:%Y-%m-%d_%H%M%S}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "Candidates"
    ws.append([header for header, _ in COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(vertical="center")

    resume_col = [key for _, key in COLUMNS].index("resume_file") + 1
    for rec in records:
        ws.append([as_text(rec.get(key, "")) for _, key in COLUMNS])
        for cell in ws[ws.max_row]:
            if cell.data_type == "f":
                # website text such as "=HYPERLINK(...)" is stored as plain text, never run as a formula
                cell.data_type = "s"
        if rec.get("resume_file"):
            cell = ws.cell(row=ws.max_row, column=resume_col)
            # relative link so it still works after the output folder is moved or zipped
            cell.hyperlink = f"../{pdf_dir.name}/{rec['resume_file']}"
            cell.font = Font(color="0563C1", underline="single")

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for idx, (header, key) in enumerate(COLUMNS, start=1):
        longest = max([len(header)] + [len(str(r.get(key, ""))) for r in records])
        ws.column_dimensions[get_column_letter(idx)].width = min(longest + 2, 60)

    wb.save(path)
    return path

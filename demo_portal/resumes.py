"""Professional two-column resumes (PDF and Word) for the demo candidates."""
from __future__ import annotations

import io

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageDraw
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from .content import avatar_png, clean_title, resume_details

INK = "#1E2430"
MUTED = "#5B6472"


def _round_photo(c: dict, size: int = 360) -> bytes:
    img = Image.open(io.BytesIO(avatar_png(c["id"], size, c["first_name"]))).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    img.putalpha(mask)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------- PDF

def make_pdf(c: dict) -> bytes:
    info = resume_details(c["id"], c["job_title"])
    accent, light = info["palette"]
    name = f"{c['first_name'].strip()} {c['last_name']}"
    title = clean_title(c["job_title"])

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=LETTER)
    pdf.setTitle(f"{name} – Resume")
    pdf.setAuthor(name)
    W, H = LETTER
    side_w = 200

    # sidebar
    pdf.setFillColor(HexColor(accent))
    pdf.rect(0, 0, side_w, H, stroke=0, fill=1)
    photo = 120
    px, py = (side_w - photo) / 2, H - 52 - photo
    pdf.setFillColor(HexColor(light))
    pdf.circle(side_w / 2, py + photo / 2, photo / 2 + 5, stroke=0, fill=1)
    pdf.drawImage(ImageReader(io.BytesIO(_round_photo(c))), px, py, photo, photo, mask="auto")

    y = py - 40

    def side_heading(text: str):
        nonlocal y
        pdf.setFillColor(white)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(24, y, text.upper())
        pdf.setStrokeColor(HexColor(light))
        pdf.setLineWidth(0.8)
        pdf.line(24, y - 6, side_w - 24, y - 6)
        y -= 24

    def side_text(text: str, size: float = 9, bold: bool = False, gap: float = 13):
        nonlocal y
        pdf.setFillColor(HexColor(light) if not bold else white)
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        for line in simpleSplit(text, "Helvetica", size, side_w - 48):
            pdf.drawString(24, y, line)
            y -= gap

    side_heading("Contact")
    for label, value in (("Phone", c["phone"]), ("Email", c["email"]), ("Location", c["location"])):
        side_text(label, 7.5, bold=True, gap=11)
        side_text(value, 8.5)
        y -= 4
    y -= 10

    side_heading("Skills")
    for skill in info["skills"]:
        pdf.setFillColor(HexColor(light))
        pdf.circle(28, y + 3, 1.8, stroke=0, fill=1)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(36, y, skill)
        y -= 14
    y -= 12

    side_heading("Languages")
    for lang in info["languages"]:
        side_text(lang)

    # main column
    x = side_w + 36
    mw = W - x - 40
    y = H - 72
    pdf.setFillColor(HexColor(INK))
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawString(x, y, name.upper())
    y -= 22
    pdf.setFillColor(HexColor(accent))
    pdf.setFont("Helvetica", 13)
    pdf.drawString(x, y, title)
    y -= 34

    def heading(text: str):
        nonlocal y
        pdf.setFillColor(HexColor(accent))
        pdf.rect(x, y - 2, 4, 13, stroke=0, fill=1)
        pdf.setFillColor(HexColor(INK))
        pdf.setFont("Helvetica-Bold", 11.5)
        pdf.drawString(x + 12, y, text.upper())
        y -= 22

    def para(text: str, size: float = 9.5, color: str = MUTED, indent: float = 0, lead: float = 13.5):
        nonlocal y
        pdf.setFillColor(HexColor(color))
        pdf.setFont("Helvetica", size)
        for line in simpleSplit(text, "Helvetica", size, mw - indent):
            pdf.drawString(x + indent, y, line)
            y -= lead

    heading("Profile")
    para(info["summary"])
    y -= 16

    heading("Experience")
    for job in info["jobs"]:
        pdf.setFillColor(HexColor(INK))
        pdf.setFont("Helvetica-Bold", 10.5)
        pdf.drawString(x, y, job["title"])
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(HexColor(MUTED))
        pdf.drawRightString(x + mw, y, job["dates"])
        y -= 14
        pdf.setFillColor(HexColor(accent))
        pdf.setFont("Helvetica-Oblique", 9.5)
        pdf.drawString(x, y, job["company"])
        y -= 16
        for bullet in job["bullets"]:
            pdf.setFillColor(HexColor(accent))
            pdf.circle(x + 4, y + 3, 1.7, stroke=0, fill=1)
            para(bullet, indent=12)
        y -= 12

    heading("Education")
    ed = info["education"]
    pdf.setFillColor(HexColor(INK))
    pdf.setFont("Helvetica-Bold", 10.5)
    pdf.drawString(x, y, ed["degree"])
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(HexColor(MUTED))
    pdf.drawRightString(x + mw, y, ed["year"])
    y -= 14
    pdf.setFillColor(HexColor(accent))
    pdf.setFont("Helvetica-Oblique", 9.5)
    pdf.drawString(x, y, ed["school"])

    # footer
    pdf.setFont("Helvetica", 7)
    pdf.setFillColor(HexColor("#9AA1AC"))
    pdf.drawString(x, 28, f"Fictional demo candidate #{c['id']} · generated for testing")
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


# --------------------------------------------------------------------------- Word

def _shade(cell, hex_color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color.lstrip("#"))
    tc_pr.append(shd)


def _no_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tbl_pr.append(borders)


def _rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.lstrip("#"))


def _run(par, text, size=9.5, bold=False, italic=False, color=INK):
    r = par.add_run(text)
    r.font.size, r.font.bold, r.font.italic = Pt(size), bold, italic
    r.font.color.rgb = _rgb(color)
    r.font.name = "Arial"
    return r


def _par(cell_or_doc, space_after=2, align=None):
    p = cell_or_doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if align is not None:
        p.alignment = align
    return p


def make_docx(c: dict) -> bytes:
    info = resume_details(c["id"], c["job_title"])
    accent, light = info["palette"]
    name = f"{c['first_name'].strip()} {c['last_name']}"
    title = clean_title(c["job_title"])

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.59), Cm(27.94)
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Cm(0)
    doc.core_properties.title = f"{name} – Resume"

    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    _no_borders(table)
    side, main = table.rows[0].cells
    widths = (Cm(7.0), Cm(14.59))
    tbl_pr = table._tbl.tblPr
    tbl_w = OxmlElement("w:tblW")
    tbl_w.set(qn("w:w"), str(int(sum(w.twips for w in widths))))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_pr.append(tbl_w)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    for grid_col, w in zip(table._tbl.tblGrid.findall(qn("w:gridCol")), widths):
        grid_col.set(qn("w:w"), str(int(w.twips)))
    for cell, w in zip((side, main), widths):
        cell.width = w
    row_pr = table.rows[0]._tr.get_or_add_trPr()
    height = OxmlElement("w:trHeight")
    height.set(qn("w:val"), str(int(27.85 * 567)))
    height.set(qn("w:hRule"), "atLeast")
    row_pr.append(height)
    _shade(side, accent)

    # sidebar
    side.paragraphs[0].paragraph_format.space_before = Pt(30)
    side.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    side.paragraphs[0].add_run().add_picture(io.BytesIO(_round_photo(c)), width=Cm(4.2))

    def side_heading(text):
        p = _par(side, 4)
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.left_indent = Cm(0.8)
        _run(p, text.upper(), 10, bold=True, color="#FFFFFF")

    def side_line(text, bold=False, size=9):
        p = _par(side, 2)
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.right_indent = Cm(0.5)
        _run(p, text, size, bold=bold, color="#FFFFFF" if bold else light)

    side_heading("Contact")
    for label, value in (("Phone", c["phone"]), ("Email", c["email"]), ("Location", c["location"])):
        side_line(label, bold=True, size=8)
        side_line(value)
    side_heading("Skills")
    for skill in info["skills"]:
        side_line(f"•  {skill}")
    side_heading("Languages")
    for lang in info["languages"]:
        side_line(lang)

    # main column
    def main_par(space_after=2, space_before=0):
        p = _par(main, space_after)
        p.paragraph_format.left_indent = Cm(1.0)
        p.paragraph_format.right_indent = Cm(1.2)
        p.paragraph_format.space_before = Pt(space_before)
        return p

    p = main.paragraphs[0]
    p.paragraph_format.space_before = Pt(46)
    p.paragraph_format.left_indent = Cm(1.0)
    _run(p, name.upper(), 24, bold=True)
    _run(main_par(18), title, 13, color=accent)

    def heading(text):
        p = main_par(6, 10)
        _run(p, "▌ ", 11, bold=True, color=accent)
        _run(p, text.upper(), 11.5, bold=True)

    heading("Profile")
    _run(main_par(6), info["summary"], 9.5, color=MUTED)

    heading("Experience")
    for job in info["jobs"]:
        p = main_par(0, 4)
        _run(p, job["title"], 10.5, bold=True)
        _run(p, f"   |   {job['dates']}", 9, color=MUTED)
        _run(main_par(4), job["company"], 9.5, italic=True, color=accent)
        for bullet in job["bullets"]:
            bp = main_par(2)
            bp.paragraph_format.left_indent = Cm(1.5)
            bp.paragraph_format.first_line_indent = Cm(-0.4)
            _run(bp, "•  ", 9.5, bold=True, color=accent)
            _run(bp, bullet, 9.5, color=MUTED)

    heading("Education")
    ed = info["education"]
    p = main_par(0)
    _run(p, ed["degree"], 10.5, bold=True)
    _run(p, f"   |   {ed['year']}", 9, color=MUTED)
    _run(main_par(4), ed["school"], 9.5, italic=True, color=accent)

    # Word requires a paragraph after a table; keep it tiny so nothing spills onto page 2
    tail = doc.add_paragraph()
    fmt = tail.paragraph_format
    fmt.space_after = fmt.space_before = Pt(0)
    fmt.line_spacing = Pt(1)
    tail.add_run("").font.size = Pt(1)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

"""Generate four small PDFs and compare two real exports of each one."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from reportlab.pdfgen import canvas

from build_sample import FONTS, HERE, SIZE, field, footer, page_header, render_page, write


def negative_sign(doc):
    page_header(doc, "Inventory adjustment")
    field(doc, 228, "Part number", "CP-82")
    write(doc, 34, 166, "Change in stock", 12)
    write(doc, 211, 158, "18", 27, bold=True)
    # The minus sign is a vector rule, exactly as it would look in a chart.
    doc.setLineWidth(3)
    doc.line(191, 168, 207, 168)
    write(doc, 34, 86, "Stock is recorded in individual units.", 11)


def outlined_label(doc):
    page_header(doc, "Shipping label")
    field(doc, 230, "Route", "West dock")
    # Converting lettering to paths keeps it visible but removes selectable characters.
    from fontTools.pens.basePen import BasePen
    from fontTools.ttLib import TTFont

    with TTFont(FONTS / "VeraBd.ttf") as font:
        glyphs = font.getGlyphSet()
        mapping = font.getBestCmap()
        path = doc.beginPath()

        class LetterPen(BasePen):
            def _moveTo(self, point):
                path.moveTo(*point)
            def _lineTo(self, point):
                path.lineTo(*point)
            def _curveToOne(self, a, b, c):
                path.curveTo(*a, *b, *c)
            def _closePath(self):
                path.close()

        doc.saveState()
        doc.translate(34, 130)
        scale = 34 / font["head"].unitsPerEm
        doc.scale(scale, scale)
        for char in "EXPRESS":
            glyph = glyphs[mapping[ord(char)]]
            path = doc.beginPath()
            glyph.draw(LetterPen(glyphs))
            doc.drawPath(path, fill=1, stroke=0)
            doc.translate(glyph.width, 0)
        doc.restoreState()


def table_order(doc):
    page_header(doc, "Dock allocations")
    left, right = 34, 235
    for y, text in ((236, "West dock"), (195, "East dock"), (154, "North dock")):
        write(doc, left, y, text, 13)
    for y, text in ((236, "14 pallets"), (195, "32 pallets"), (154, "8 pallets")):
        write(doc, right, y, text, 13, bold=True)


def missing_boundaries(doc):
    for page, batch in ((1, "AX-15"), (2, "BZ-80")):
        page_header(doc, "Batch record")
        field(doc, 232, "Batch code", batch)
        footer(doc, page)
        if page == 1:
            doc.showPage()


def extract_pdf(pdf, flags):
    return subprocess.check_output(["pdftotext", *flags, "-enc", "UTF-8", str(pdf), "-"])


def ocr_first_page(pdf):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "page.png"
        with render_page(pdf, 1, 3) as img:
            img.save(path)
        return subprocess.check_output(["tesseract", str(path), "stdout", "-l", "eng", "--psm", "6"])


# The check, method and artifact names are also used when generating each report.
CASES = [
    ("minus-sign", "Inventory adjustment", negative_sign, ["-layout"], None,
     "Text layer", "OCR", [(1, "Part number", "CP-82"), (1, "Signed change", "-18")]),
    ("outline", "Shipping label", outlined_label, ["-layout"], None,
     "Text layer", "OCR", [(1, "Route", "West dock"), (1, "Service level", "EXPRESS")]),
    ("table-order", "Dock allocations", table_order, ["-raw"], ["-layout"],
     "Content order", "Visual layout", [(1, "West allocation", "West dock 14 pallets"),
                                         (1, "East allocation", "East dock 32 pallets"),
                                         (1, "North allocation", "North dock 8 pallets")]),
    ("page-breaks", "Batch records", missing_boundaries, ["-layout", "-nopgbrk"], ["-layout"],
     "No page breaks", "With page breaks", [(1, "First batch", "AX-15"), (2, "Second batch", "BZ-80")]),
]


def build():
    for slug, title, draw, first, second, name, compare_name, rows in CASES:
        pdf = HERE / (slug + ".pdf")
        doc = canvas.Canvas(str(pdf), pagesize=SIZE, invariant=1)
        doc.setTitle(title)
        doc.setAuthor("PDF Extraction Check")
        draw(doc)
        doc.showPage()
        doc.save()
        before = HERE / (slug + "-before.txt")
        after = HERE / (slug + "-after.txt")
        before.write_bytes(extract_pdf(pdf, first))
        after.write_bytes(ocr_first_page(pdf) if second is None else extract_pdf(pdf, second))
        spec = HERE / (slug + ".json")
        checks = [{"page": n, "label": label, "text": phrase} for n, label, phrase in rows]
        spec.write_text(json.dumps({"document": title, "checks": checks}, indent=2) + "\n", encoding="utf-8")
        result = subprocess.run([sys.executable, str(HERE.parent / "check.py"), str(spec), str(before),
                        "--name", name, "--compare", str(after), "--compare-name", compare_name,
                        "--pdf", str(pdf), "--html", str(HERE / (slug + ".html"))])
        if result.returncode not in (0, 1):
            result.check_returncode()


if __name__ == "__main__":
    build()

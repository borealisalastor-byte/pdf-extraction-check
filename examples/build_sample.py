"""Rebuild the fictional receiving record and the two real extraction outputs."""
from io import BytesIO
from pathlib import Path
import subprocess
import tempfile

import pypdfium2 as pdfium
import reportlab
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


HERE = Path(__file__).resolve().parent
SIZE = (460, 390)
INK = "#163a3c"
MUTED = "#466265"
LINE = "#c3d1c8"
FONTS = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("Record", str(FONTS / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("RecordBold", str(FONTS / "VeraBd.ttf")))


def write(c, x, y, text, size=12, bold=False, color=INK):
    c.setFillColor(HexColor(color))
    c.setFont("RecordBold" if bold else "Record", size)
    c.drawString(x, y, text)


def rules(c, y):
    c.setStrokeColor(HexColor(LINE))
    c.setLineWidth(0.7)
    c.line(34, y, SIZE[0] - 34, y)


def page_header(c, title):
    write(c, 34, 347, "NORTH PIER SUPPLY", 10, True)
    rules(c, 333)
    write(c, 34, 295, title, 27, True)


def field(c, y, label, value):
    write(c, 34, y, label, 12, color=MUTED)
    write(c, 195, y, value, 14, True)
    rules(c, y - 13)


def footer(c, number):
    write(c, 34, 24, f"Page {number} of 2", 10, color=MUTED)


def render_page(pdf, number, scale):
    with pdfium.PdfDocument(pdf) as doc:
        page = doc[number - 1]
        bitmap = page.render(scale=scale)
        try:
            return bitmap.to_pil().convert("RGB")
        finally:
            bitmap.close()
            page.close()


def build():
    inspection = BytesIO()
    scan = canvas.Canvas(inspection, pagesize=SIZE, invariant=1)
    page_header(scan, "Inspection record")
    field(scan, 240, "Inspection code", "KX-741")
    field(scan, 190, "Quantity on hold", "4 units held")
    field(scan, 140, "Disposition", "HOLD FOR REVIEW")
    write(scan, 34, 83, "One carton requires a second inspection.", 11)
    scan.showPage()
    scan.save()

    source = HERE / "receiving-record.pdf"
    doc = canvas.Canvas(str(source), pagesize=SIZE, invariant=1)
    doc.setTitle("Receiving record")
    doc.setAuthor("PDF Extraction Check")
    page_header(doc, "Receiving record")
    field(doc, 240, "Receipt number", "RCV-2048")
    field(doc, 190, "Quantity received", "24 units")
    field(doc, 140, "Delivery", "Ceramic spacers")
    write(doc, 34, 83, "Inspection details appear on the following page.", 11)
    footer(doc, 1)
    doc.showPage()
    with render_page(inspection.getvalue(), 1, 3) as scan_image:
        doc.drawImage(ImageReader(scan_image), 0, 0, width=SIZE[0], height=SIZE[1])
    footer(doc, 2)
    doc.showPage()
    doc.save()

    raw = subprocess.check_output(["pdftotext", "-layout", "-enc", "UTF-8", str(source), "-"])
    (HERE / "text-layer.txt").write_bytes(raw)
    with tempfile.TemporaryDirectory() as temp:
        page_path = Path(temp) / "page-2.png"
        with render_page(source, 2, 3) as page_image:
            page_image.save(page_path)
        ocr = subprocess.check_output(["tesseract", str(page_path), "stdout", "-l", "eng", "--psm", "6"])
    first_page = raw.split(b"\f")[0]
    (HERE / "text-plus-ocr.txt").write_bytes(first_page + b"\f" + ocr.rstrip() + b"\n\f")


if __name__ == "__main__":
    build()

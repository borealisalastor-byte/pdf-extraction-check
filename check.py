"""Test page-specific facts in text or Markdown extracted from a PDF."""

import argparse
import base64
import html
import io
import json
import re
import sys
import unicodedata
from pathlib import Path


PAGE_MARKER = re.compile(r"^[ \t]*<!--[ \t]*page:[ \t]*(\d+)[ \t]*-->[ \t]*\r?$", re.I | re.M)
TOKEN = re.compile(r"(?<!\w)[+-]?(?:\d+(?:[.,]\d+)*|[.,]\d+)(?:e[+-]?\d+)?(?!\w)|\w+|[^\s]")
TEMPLATE = Path(__file__).with_name("report.template.html")


def tokens(text):
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("\u00ad", "").replace("\u2212", "-")
    return TOKEN.findall(normalized)


def contains_sequence(haystack, needle):
    width = len(needle)
    return any(haystack[pos:pos + width] == needle
               for pos, token in enumerate(haystack) if token == needle[0])


def read_spec(path):
    spec = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(spec, dict) or not isinstance(spec.get("checks"), list) or not spec["checks"]:
        raise ValueError("The checks file must contain a nonempty checks array.")
    if not isinstance(spec.get("document"), str) or not spec["document"].strip():
        raise ValueError("Set document to a title in the checks file.")
    for index, check in enumerate(spec["checks"], start=1):
        if not isinstance(check, dict) or type(check.get("page")) is not int or check["page"] < 1:
            raise ValueError(f"Check {index} needs a positive integer page.")
        if any(not isinstance(check.get(key), str) or not check[key].strip()
               for key in ("label", "text")):
            raise ValueError(f"Check {index} needs a nonempty label and text.")
        if not tokens(check["text"]):
            raise ValueError(f"Check {index} needs visible text.")
    return spec


def split_pages(text, page_count):
    if "\f" in text and PAGE_MARKER.search(text.replace("\f", "\n")):
        raise ValueError("Use either form feeds or numbered page markers in each export.")
    markers = list(PAGE_MARKER.finditer(text))
    if markers:
        if text[:markers[0].start()].strip():
            raise ValueError("Put the first page marker before the text.")
        numbers = [int(marker[1]) for marker in markers]
        if numbers[0] < 1 or numbers != sorted(set(numbers)):
            raise ValueError("Numbered page markers must be positive, unique and increasing.")
        ends = [marker.start() for marker in markers[1:]] + [len(text)]
        return {number: text[marker.end():end].strip()
                for number, marker, end in zip(numbers, markers, ends)}
    if "\f" in text:
        chunks = text.split("\f")
        if not chunks[-1].strip():
            chunks.pop()  # Poppler terminates the last page with a form feed.
        return {i: content.strip() for i, content in enumerate(chunks, start=1)}
    if page_count == 1:
        return {1: text.strip()}
    return None


def evaluate(label, text, checks, page_count):
    pages = split_pages(text, page_count)
    selected = sorted({check["page"] for check in checks})
    excerpts = {page: pages[page] for page in selected if pages is not None and page in pages}
    page_tokens = {page: tokens(content) for page, content in excerpts.items()}
    outcomes = []
    for check in checks:
        page = check["page"]
        if pages is None:
            result = "Unmapped"
        elif page not in pages:
            result = "Page missing"
        elif contains_sequence(page_tokens[page], tokens(check["text"])):
            result = "Found"
        else:
            result = "Missing"
        outcomes.append(result)
    return {"label": label, "outcomes": outcomes, "text": excerpts}


def pdf_previews(path, pages):
    try:
        import pypdfium2 as pdfium
    except ImportError as err:
        raise ValueError("PDF previews need pypdfium2 and Pillow. Install requirements.txt.") from err
    previews = {}
    with pdfium.PdfDocument(path) as document:
        count = len(document)
        for number in pages:
            if number > count:
                raise ValueError(f"Check refers to page {number}, but the source PDF has {count} pages.")
            page = document[number - 1]
            width, height = page.get_size()
            bitmap = page.render(scale=min(2.0, 1200 / max(width, height)))
            try:
                with bitmap.to_pil().convert("RGB") as image:
                    with io.BytesIO() as out:
                        image.save(out, format="PNG", optimize=True)
                        previews[number] = "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")
            finally:
                bitmap.close()
                page.close()
    return count, previews


def write_report(path, spec, runs, previews):
    template = TEMPLATE.read_text(encoding="utf-8")
    payload = {"document": spec["document"], "checks": spec["checks"], "runs": runs,
               "images": previews}
    encoded = json.dumps(payload, ensure_ascii=True).replace("<", r"\u003c")
    fallback = [f"<h1>{html.escape(spec['document'])}</h1>"]
    for run in runs:
        title = html.escape(run["label"])
        found = run["outcomes"].count("Found")
        fallback.append(f"<h2>{title} · {found}/{len(spec['checks'])} found</h2><ul>")
        for check, result in zip(spec["checks"], run["outcomes"]):
            fallback.append(f"<li>Page {check['page']} · {html.escape(check['label'])} · "
                            f"{html.escape(check['text'])} · {html.escape(result)}</li>")
        fallback.append("</ul>")
    report = template.replace("__STATIC_RESULTS__", "".join(fallback), 1)
    before, after = report.rsplit("__REPORT_DATA__", 1)
    path.write_text(before + encoded + after, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checks", type=Path, help="JSON file with page numbers and expected text")
    parser.add_argument("extraction", type=Path, help="UTF-8 text or Markdown export")
    parser.add_argument("--compare", type=Path, help="Second export. Its checks determine the exit code.")
    parser.add_argument("--name", help="Display name for the first export")
    parser.add_argument("--compare-name", help="Display name for the second export")
    parser.add_argument("--pdf", type=Path, help="Original PDF to validate page numbers and render previews")
    parser.add_argument("--html", type=Path, help="Write a standalone interactive report")
    args = parser.parse_args(argv)
    try:
        inputs = [path.resolve() for path in (args.checks, args.extraction, args.compare, args.pdf) if path]
        if args.html and args.html.resolve() in [*inputs, TEMPLATE.resolve(), Path(__file__).resolve()]:
            raise ValueError("Choose an HTML output path different from the inputs and program files.")
        if args.compare_name and not args.compare:
            raise ValueError("--compare-name needs a second export supplied with --compare.")
        spec = read_spec(args.checks)
        checks = spec["checks"]
        selected = sorted({check["page"] for check in checks})
        count, previews = pdf_previews(args.pdf, selected) if args.pdf else (selected[-1], {})
        inputs_to_test = [(args.name or args.extraction.name, args.extraction)]
        if args.compare:
            inputs_to_test.append((args.compare_name or args.compare.name, args.compare))
        runs = [evaluate(label, path.read_text(encoding="utf-8-sig"), checks, count)
                for label, path in inputs_to_test]
        for run in runs:
            found = run["outcomes"].count("Found")
            print(f"{run['label']} — {found}/{len(checks)} checks found")
            for check, result in zip(checks, run["outcomes"]):
                if result != "Found":
                    print(f"  {result} | page {check['page']} | {check['label']} | {check['text']}")
        if args.html:
            write_report(args.html, spec, runs, previews)
    except (OSError, UnicodeError, ValueError, RuntimeError, ImportError) as err:
        print(f"Input error: {err}", file=sys.stderr)
        return 2
    return int(any(result != "Found" for result in runs[-1]["outcomes"]))


if __name__ == "__main__":
    sys.exit(main())

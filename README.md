# PDF Extraction Check

Catch missing facts in text or Markdown before an AI system reads the document. Give the checker a few phrases from the original PDF and the page where each one belongs. It produces an offline HTML report and an exit code for automated tests.

[Explore five PDFs that break AI readers](https://borealisalastor-byte.github.io/pdf-extraction-check/) · [Reproduce the examples](examples/README.md)

A receiving record illustrates the problem. The inspection sheet contains a code, a quantity, and a decision. A text-layer export of that page contains only “Page 2 of 2.” OCR recovers the missing fields. On a different document, both methods lose a minus sign and change the meaning of an inventory adjustment.

| Example | First method | Second method |
| --- | --- | --- |
| Scanned page with a selectable footer | Text layer · 2/5 | OCR on page 2 · 5/5 |
| Minus sign drawn as a line | Text layer · 1/2 | OCR · 1/2 |
| Shipping label drawn as outlines | Text layer · 1/2 | OCR · 2/2 |
| Table painted by column | Content order · 0/3 | Visual layout · 3/3 |
| Export without physical page breaks | Unmapped · 0/2 | Page breaks preserved · 2/2 |

## Try it

Open `examples/report.html` to explore the included result immediately. Use Python 3.9 or newer to check another export. The command-line checks use the Python standard library.

```sh
python check.py examples/checks.json examples/text-layer.txt
```

The sample above exits with code 1 because three checks fail. To see both exports beside the source pages, install the optional preview dependencies and build the report.

```sh
python -m pip install -r requirements.txt
python check.py examples/checks.json examples/text-layer.txt --name "Text layer" --compare examples/text-plus-ocr.txt --compare-name "Text + OCR" --pdf examples/receiving-record.pdf --html review.html
```

Open `review.html` in a browser. The first missing check determines the opening page. Switch between the two methods to inspect each result. The report embeds the original images and extracted text for checked pages. You can share that file on its own.

## Check your own documents

Choose phrases whose loss would affect a downstream answer. Put the expected strings in a UTF-8 JSON file and include each physical page number, starting at 1.

```json
{
  "document": "Inspection records",
  "checks": [
    {"page": 2, "label": "Inspection code", "text": "KX-741"}
  ]
}
```

Supply UTF-8 text or Markdown from your extraction pipeline. The checker understands form feeds from `pdftotext` and numbered Markdown comments on separate lines. For example:

```markdown
<!-- page: 1 -->
Receiving record

<!-- page: 2 -->
Inspection code KX-741
```

Use explicit page markers when a parser omits a page. A missing numbered page is reported as `Page missing`. An export with no boundaries is reported as `Unmapped` when a multi-page source is known. Providing `--pdf` verifies physical page numbers against the file. Without it, page count is inferred from your highest numbered check.

A check looks for a contiguous sequence of tokens on its specified page. Matching ignores case and whitespace at token boundaries and normalizes Unicode. Punctuation and number signs matter. A passing check establishes that the specified text occurred somewhere on that page. Verifying table-cell relationships, reading order and numerical meaning requires additional checks or human review. Rasterized letters inside a checked phrase may be misread by OCR and will trigger a missing result.

## Automate it

Use exit code 0 for all checks found, 1 for missing or unmapped checks, and 2 for invalid input. With `--compare`, the second export determines the exit code. Supply `--html` to save a report when a check fails.

```sh
python -m unittest discover -v
```

To reproduce the sample outputs, install ReportLab in addition to the preview dependencies, and make Poppler's `pdftotext` and Tesseract with English language data available on your path. Run `python examples/build_sample.py`. The included outputs were produced with Poppler 25.03.0 and Tesseract 5.5.0. OCR output may vary by version.

## Contribute an example

A small document you can redistribute, its page-specific checks, the raw extraction, and the command that produced it make a useful new test case. A synthetic document that reproduces an omission is welcome.

# Reproduce the gallery

Open the [gallery](../index.html) or run each case against the committed UTF-8 exports. The examples are original, synthetic documents. The numbers below are counts of page-specific text checks on these fixtures.

| Case | First export | Second export | Result |
| --- | --- | --- | --- |
| [Scan with a selectable footer](report.html) | Poppler text layer | Tesseract on page 2 | 2/5 → 5/5 |
| [Drawn minus sign](minus-sign.html) | Poppler text layer | Tesseract on page 1 | 1/2 → 1/2 |
| [Letters converted to outlines](outline.html) | Poppler text layer | Tesseract on page 1 | 1/2 → 2/2 |
| [Table printed one column at a time](table-order.html) | Poppler `-raw` | Poppler `-layout` | 0/3 → 3/3 |
| [Page breaks removed](page-breaks.html) | Poppler `-layout -nopgbrk` | Poppler `-layout` | 0/2 mapped → 2/2 |

From the repository root, compare one pair of exports. Choose another case by replacing the name in all three paths.

```sh
python check.py examples/table-order.json examples/table-order-before.txt --compare examples/table-order-after.txt
```

The drawn minus is a useful control. In the source PDF the stock adjustment is negative eighteen. Both recorded exports say eighteen. The checker reports the missing sign and exits with code 1 even when OCR is supplied.

## Regenerate the documents and exports

The checked-in results use Poppler 25.03.0 and Tesseract 5.5.0 with English language data. Run the commands with `pdftotext` and `tesseract` on your path. Results can differ with the tool or language-data version.

```sh
python -m pip install -r requirements.txt reportlab fonttools
python examples/build_sample.py
python check.py examples/checks.json examples/text-layer.txt --name "Text layer" --compare examples/text-plus-ocr.txt --compare-name "Text + OCR" --pdf examples/receiving-record.pdf --html examples/report.html
python examples/build_gallery.py
python -m unittest discover -v
```

Each generator records the commands used for its extraction pair. The JSON checks list expected text by physical page. To contribute a case, include a redistributable PDF, its expected text, both raw exports, and the commands and tool versions that produced them.

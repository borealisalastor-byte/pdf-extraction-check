import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import check


EXAMPLES = Path(__file__).with_name("examples")
SPEC = EXAMPLES / "checks.json"


class CheckTests(unittest.TestCase):
    def test_mixed_native_and_scanned_pdf_exports(self):
        checks = check.read_spec(SPEC)["checks"]
        for name, expected in (("text-layer.txt", 2), ("text-plus-ocr.txt", 5)):
            with self.subTest(name=name):
                run = check.evaluate(name, (EXAMPLES / name).read_text(), checks, 2)
                self.assertEqual(expected, run["outcomes"].count("Found"))

    def test_text_on_another_page_does_not_pass(self):
        result = check.evaluate("test", "KX-741\fDifferent page\f",
                                [{"page": 2, "text": "KX-741"}], 2)
        self.assertEqual(result["outcomes"], ["Missing"])

    def test_unnumbered_raw_export_with_multiple_pages_is_unmapped(self):
        result = check.evaluate("test", "KX-741", [{"page": 1, "text": "KX-741"}], 2)
        self.assertEqual(result["outcomes"], ["Unmapped"])

    def test_markers_can_skip_a_page(self):
        text = "<!-- page: 1 -->\nReceipt\n<!-- page: 3 -->\nEND"
        checks = [{"page": n, "text": "END"} for n in (1, 2, 3)]
        self.assertEqual(check.evaluate("test", text, checks, 3)["outcomes"],
                         ["Missing", "Page missing", "Found"])

    def test_invalid_markers_are_rejected(self):
        for text in ("<!-- page: 0 -->\ntext", "<!-- page: 2 -->\n<!-- page: 1 -->",
                     "<!-- page: 1 -->\n<!-- page: 1 -->", "wrong\n<!-- page: 2 -->",
                     "<!-- page: 1 -->\ftext"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                check.split_pages(text, 3)

    def test_poppler_terminator_preserves_an_empty_last_page(self):
        self.assertEqual(check.split_pages("one\f\f", 2), {1: "one", 2: ""})

    def test_matching_distinguishes_numbers_and_words(self):
        examples = [("hold\nFOR review", "HOLD FOR REVIEW", True),
                    ("rate −4.5%", "-4.5%", True), ("rate -4.50%", "4.50%", False),
                    ("amount 14.90", "4.9", False), ("count .5", "5", False),
                    ("code ABC4", "4", False), ("withheld", "held", False)]
        for source, expected, outcome in examples:
            with self.subTest(source=source):
                self.assertEqual(check.contains_sequence(check.tokens(source), check.tokens(expected)), outcome)

    def test_cli_exit_codes_and_source_protection(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            args = [str(SPEC), str(EXAMPLES / "text-layer.txt")]
            report = Path(temp) / "report.html"
            self.assertEqual(check.main(args + ["--html", str(report)]), 1)
            self.assertTrue(report.is_file())
            self.assertEqual(check.main(args + ["--compare", str(EXAMPLES / "text-plus-ocr.txt")]), 0)
            self.assertEqual(check.main(args + ["--html", str(SPEC)]), 2)
            self.assertEqual(check.main(args + ["--html", str(check.TEMPLATE)]), 2)
            self.assertEqual(check.main(args + ["--compare-name", "Missing file"]), 2)

    def test_malformed_checks_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "invalid.json"
            for checks in ([], [{}], [{"page": True, "label": "x", "text": "y"}],
                           [{"page": 1, "label": "x", "text": "\u00ad"}]):
                with self.subTest(checks=checks), self.assertRaises(ValueError):
                    path.write_text(json.dumps({"document": "Example", "checks": checks}))
                    check.read_spec(path)

    def test_html_embeds_input_as_json_text(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.html"
            document = "</script><b>sample</b>"
            check.write_report(path, {"document": document, "checks": []}, [], {})
            html = path.read_text()
            self.assertNotIn(document, html)
            self.assertIn(r"\u003c/script>", html)


if __name__ == "__main__":
    unittest.main()

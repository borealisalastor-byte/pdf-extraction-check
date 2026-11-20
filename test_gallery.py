"""Regression checks for the published sample exports. No OCR install is required."""
import unittest
from pathlib import Path

from check import evaluate, read_spec


EXAMPLES = Path(__file__).with_name("examples")


class GalleryTests(unittest.TestCase):
    def assert_case(self, slug, before, after):
        checks = read_spec(EXAMPLES / (slug + ".json"))["checks"]
        page_count = max(check["page"] for check in checks)
        for method, expected in (("before", before), ("after", after)):
            with self.subTest(method=method):
                export = (EXAMPLES / f"{slug}-{method}.txt").read_text(encoding="utf-8")
                self.assertEqual(evaluate(method, export, checks, page_count)["outcomes"], expected)

    def test_vector_minus_is_lost_by_both_extractors(self):
        self.assert_case("minus-sign", ["Found", "Missing"], ["Found", "Missing"])

    def test_ocr_reads_outlined_letters(self):
        self.assert_case("outline", ["Found", "Missing"], ["Found", "Found"])

    def test_layout_reconnects_labels_and_values(self):
        self.assert_case("table-order", ["Missing"] * 3, ["Found"] * 3)

    def test_page_breaks_preserve_physical_page_numbers(self):
        self.assert_case("page-breaks", ["Unmapped"] * 2, ["Found"] * 2)


if __name__ == "__main__":
    unittest.main()

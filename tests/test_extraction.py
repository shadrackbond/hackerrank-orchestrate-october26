"""Cache and provenance tests use synthetic documents, not public answers."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from test_audit import fixture, CAPTURE, CUTOFF
from ghost_audit.core import EvidenceIndex, Investigation, Rejected
from ghost_audit.extraction import VERSION, prepare_visual_index, source_cache_path
from ghost_audit.extraction import local_image_extract, pdf_extract


class ExtractionTests(unittest.TestCase):
    def test_cached_image_is_not_processed_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset"
            dataset.mkdir()
            fixture(dataset)
            image = dataset / "evidence" / "custom.png"
            image.write_bytes(b"synthetic image bytes")
            manifest = dataset / "evidence_files.csv"
            with manifest.open("a") as f:
                f.write(f"image_custom,evidence/custom.png,fixture,{CAPTURE}\n")
            cache = root / "cache"
            segments = [{"text": "old@example.test account_target",
                         "location": "image=1,region=top-left"}]
            with patch("ghost_audit.extraction.local_image_extract", return_value=segments) as extractor:
                first = prepare_visual_index(dataset, cache, "model-x")
                second = prepare_visual_index(dataset, cache, "model-x")
                self.assertEqual(extractor.call_count, 1)
            self.assertEqual(first["image_extracted"], 1)
            self.assertEqual(second["image_extracted"], 0)
            self.assertGreaterEqual(second["cache_hits"], 1)
            index = EvidenceIndex(dataset, cache, "local-ocr")
            session = Investigation(index, fixture_request(dataset))
            initial = session.call("resolve_identity", {})
            self.assertIn("image_custom", [m["file_id"] for m in initial["candidates"]])
            visual = session.call("inspect_visual_evidence", {"evidence_id": "image_custom"})
            self.assertEqual(visual["observations"][0]["source_location"],
                             "evidence/custom.png#image=1,region=top-left")
            self.assertEqual(visual["observations"][0]["observation_at"], CAPTURE)
            self.assertIn("Visual state adapter required: image_custom", session.ledger["remaining_gaps"])

    def test_pdf_cache_key_ignores_image_model_but_image_key_does_not(self):
        a = source_cache_path("/tmp/cache", b"content", ".pdf", "model-one")
        b = source_cache_path("/tmp/cache", b"content", ".pdf", "model-two")
        c = source_cache_path("/tmp/cache", b"changed", ".pdf", "model-one")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(source_cache_path("/tmp/cache", b"image", ".png", "model-one"),
                            source_cache_path("/tmp/cache", b"image", ".png", "model-two"))

    def test_local_ocr_preserves_source_coordinates_and_scanned_pdf_page(self):
        from PIL import Image, ImageDraw, ImageFont
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = Image.new("RGB", (600, 150), "white")
            font = ImageFont.truetype("DejaVuSans.ttf", 42)
            ImageDraw.Draw(image).text((24, 35), "HELLO 1234", fill="black", font=font)
            png = root / "scan.png"
            pdf = root / "scan.pdf"
            image.save(png)
            image.save(pdf)
            visual = local_image_extract(png)
            self.assertTrue(any("HELLO" in r["text"] for r in visual))
            self.assertTrue(all(r["location"].startswith("image=1,bbox=") for r in visual))
            pages = pdf_extract(pdf)
            self.assertTrue(any("HELLO" in r["text"] for r in pages))
            self.assertTrue(all(r["location"].startswith("page=1,image=1,bbox=") for r in pages))

    def test_duplicate_content_is_extracted_once_within_one_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset"
            dataset.mkdir()
            fixture(dataset)
            for name in ("copy_a.png", "copy_b.png"):
                (dataset / "evidence" / name).write_bytes(b"identical fictional scan")
            with (dataset / "evidence_files.csv").open("a") as f:
                f.write(f"image_a,evidence/copy_a.png,fixture,{CAPTURE}\n")
                f.write(f"image_b,evidence/copy_b.png,fixture,{CAPTURE}\n")
            with patch("ghost_audit.extraction.local_image_extract", return_value=[
                {"text": "old@example.test", "location": "image=1,bbox=0,0,10,10"}]) as extractor:
                result = prepare_visual_index(dataset, root / "cache", "model-x")
            self.assertEqual(extractor.call_count, 1)
            self.assertEqual(result["image_extracted"], 1)
            self.assertEqual(result["cache_hits"], 1)

    def test_visual_evidence_captured_after_cutoff_is_not_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            image = root / "evidence" / "late.png"
            image.write_bytes(b"late")
            with (root / "evidence_files.csv").open("a") as f:
                f.write("late_image,evidence/late.png,fixture,2026-02-04T00:00:00Z\n")
            cache = root / "cache"
            cache.mkdir()
            path = source_cache_path(cache, b"late", ".png", "model-x")
            path.write_text(json.dumps({"version": VERSION, "content_sha256": hashlib.sha256(b"late").hexdigest(),
               "extractor": "codex-vision", "segments": [{"text": "old@example.test",
               "location": "image=1,region=center"}]}))
            session = Investigation(EvidenceIndex(root, cache, "model-x"), fixture_request(root))
            candidates = session.call("resolve_identity", {})["candidates"]
            self.assertNotIn("late_image", [m["file_id"] for m in candidates])
            with self.assertRaisesRegex(Rejected, "eligible identity-linked"):
                session.call("inspect_visual_evidence", {"evidence_id": "late_image"})


def fixture_request(dataset):
    with (dataset / "sample_deletion_requests.csv").open(newline="") as f:
        return next(csv.DictReader(f))


if __name__ == "__main__":
    unittest.main()

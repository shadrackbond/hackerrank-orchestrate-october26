"""Independent context/resource and provenance regressions; no live inference."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ghost_audit.core import rows
from ghost_audit.extraction import VERSION, source_cache_path
from ghost_audit.public_index import PublicIndex, _json_rows
from ghost_audit.public_runner import investigate
from test_audit import fixture, csv_file, CAPTURE


class ContextResourceTests(unittest.TestCase):
    def document(self, root, request, *, collection=None, records=None, source="collector"):
        path = "evidence/unrelated.json"
        obj = {"captured_at": CAPTURE, "source": source, "records": records or []}
        if collection: obj["collection"] = collection
        (root / path).write_text(json.dumps(obj))
        csv_file(root / "evidence_files.csv", ["file_id", "file_path", "origin", "captured_at"], [
            {"file_id": "structured_proof", "file_path": path, "origin": "independent_exporter", "captured_at": CAPTURE}])

    def test_financial_register_is_context_not_a_legal_hold_resource(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = fixture(root)
            self.document(root, request, records=[{"system": "account_service", "resource_id": "profile_fixture",
                "record_type": "USER_PROFILE", "result": "FOUND", "subject_reference": "old@example.test"}])
            blob = b"synthetic cached financial document"
            (root / "evidence/arbitrary.pdf").write_bytes(blob)
            with (root / "evidence_files.csv").open("a") as stream:
                stream.write(f"context_proof,evidence/arbitrary.pdf,finance_collector,{CAPTURE}\n")
            cache = root / "cache"
            cache.mkdir()
            segments = [{"text": text, "location": f"page=1,line={n}"} for n, text in enumerate([
                "DISPUTED ORDERS AND TAX RECORDS REGISTER", "Disputed order entries",
                "1     order_custom | user_target | Card dispute | 04 May 2025 | USD 9.00 | Retain until 04 May 2033 | AR"], 1)]
            source_cache_path(cache, blob, ".pdf", "local-ocr").write_text(json.dumps({
                "version": VERSION, "content_sha256": hashlib.sha256(blob).hexdigest(),
                "extractor": "synthetic_cached_fixture_NOT_model", "segments": segments}))
            index = PublicIndex(root, cache)
            self.assertEqual(len(index.contexts), 1)
            self.assertNotIn("category", index.contexts[0])
            self.assertFalse(any(o["category"] == "LEGAL_HOLD_RECORD" for o in index.observations))
            result = investigate(index, request)
            self.assertEqual(result["output"]["deletion_status"], "INCOMPLETE")
            self.assertEqual({s["resource_id"] for s in result["output"]["steps_json"]}, {"profile_fixture"})
            self.assertEqual(result["ledger"]["contextual_evidence"][0]["record"]["order_reference"], "order_custom")

    def test_retained_order_schema_requires_semantic_legal_hold_evidence(self):
        meta = {"file_id": "proof", "file_path": "evidence/neutral.json", "origin": "finance", "captured_at": CAPTURE}
        base = {"captured_at": CAPTURE, "source": "legal_service", "collection": "retained_order_records"}
        ordinary = {"resource_id": "order_custom", "subject_reference": "user_target", "retained_until": "2033-01-01T00:00:00Z"}
        found, _ = _json_rows({**base, "records": [ordinary]}, meta)
        self.assertEqual(found[0]["evidence_role"], "CONTEXT")
        held, _ = _json_rows({**base, "records": [{**ordinary, "legal_hold_active": True}]}, meta)
        self.assertEqual(held[0]["category"], "LEGAL_HOLD_RECORD")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = fixture(root)
            self.document(root, request, collection="retained_order_records", source="legal_service",
                          records=[{**ordinary, "legal_hold_active": True}])
            rule = {"rule_id": "independent_hold_rule", "data_category": "LEGAL_HOLD_RECORD",
                    "condition": "A supplied legal hold is active", "required_action": "RETAIN"}
            csv_file(root / "deletion_rules.csv", list(rule), [rule])
            result = investigate(PublicIndex(root), request)
            self.assertEqual(result["output"]["deletion_status"], "COMPLETE")
            self.assertEqual(result["output"]["steps_json"][0]["operation"], "VERIFY_RECORD_PRESENT")

    def test_export_schema_normalizes_system_but_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = fixture(root)
            record = {"resource_id": "download_fixture", "owner_email": "old@example.test", "file_name": "data.zip",
                      "created_at": "2026-01-01T00:00:00Z", "expires_at": "2027-01-01T00:00:00Z", "download_available": True}
            self.document(root, request, collection="customer_export_jobs", source="archival_worker", records=[record])
            index = PublicIndex(root)
            obs = index.observations[0]
            self.assertEqual(obs["system_id"], "export_service")
            self.assertEqual(obs["document_source"], "archival_worker")
            self.assertEqual(obs["source_system_label"], "archival_worker")
            self.assertEqual(obs["source_origin"], "independent_exporter")
            self.assertEqual(obs["record"], record)
            rule = {"rule_id": "export_rule", "data_category": "USER_EXPORT", "condition": "Always", "required_action": "DELETE"}
            csv_file(root / "deletion_rules.csv", list(rule), [rule])
            result = investigate(PublicIndex(root), request)
            self.assertEqual({s["system_id"] for s in result["output"]["steps_json"]}, {"export_service"})
            # An explicit resource system is not overwritten by a source-schema inference.
            self.document(root, request, collection="customer_export_jobs", source="archival_worker",
                          records=[{**record, "system": "regional_export_service"}])
            self.assertEqual(PublicIndex(root).observations[0]["system_id"], "regional_export_service")

    def test_missing_resource_identity_does_not_create_an_id_or_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = fixture(root)
            self.document(root, request, records=[{"system": "account_service", "record_type": "USER_PROFILE",
                "subject_reference": "old@example.test", "result": "NOT_FOUND"}])
            result = investigate(PublicIndex(root), request)
            self.assertIsNone(result["output"])
            self.assertTrue(any(g.startswith("Resource identity unproved:") for g in result["ledger"]["remaining_gaps"]))
            self.assertEqual(result["ledger"]["discovered_resources"], [])


if __name__ == "__main__": unittest.main()

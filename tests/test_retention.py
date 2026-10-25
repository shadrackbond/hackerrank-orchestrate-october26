"""Independent retention proofs; cached synthetic documents, no model or public labels."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ghost_audit.engine import _policy, _compliant, retention_proof
from ghost_audit.extraction import VERSION, source_cache_path
from ghost_audit.public_index import PublicIndex
from ghost_audit.public_runner import investigate
from test_audit import csv_file


AUDIT = "2026-02-03T00:00:00Z"
CAPTURE = "2026-02-01T00:00:00Z"
RULES = {
    "SECURITY_AUDIT_LOG": [{"condition": "Record is within the supplied retention period", "required_action": "RETAIN"}],
    "LEGAL_HOLD_RECORD": [{"condition": "A supplied legal hold is active", "required_action": "RETAIN"}],
}


def observation(record, category="SECURITY_AUDIT_LOG", fid="readback", **extra):
    return {"system_id": "security_service", "resource_id": "journal_fixture", "category": category,
            "evidence_id": fid, "capture_at": CAPTURE, "observed_at": CAPTURE,
            "source_location": "evidence/neutral.json#records/0", "state": "PRESENT",
            "record": record, **extra}


class RetentionTests(unittest.TestCase):
    def test_active_explicit_requirement_and_alias_format(self):
        obs = observation({"retained_until": "2027-01-01T00:00:00Z"})
        self.assertEqual(_policy(RULES, obs, AUDIT), ("RETAIN", None))
        self.assertFalse(_compliant("RETAIN", {**obs, "state": "ABSENT"}))

    def test_expired_requirement_has_no_invented_fallback(self):
        obs = observation({"retention_until": "2026-01-31T00:00:00Z"})
        self.assertEqual(retention_proof(obs, AUDIT)["status"], "EXPIRED")
        action, gap = _policy(RULES, obs, AUDIT)
        self.assertIsNone(action)
        self.assertIn("no fallback treatment supplied", gap)

    def test_presence_capture_and_readback_time_are_insufficient(self):
        obs = observation({"recorded_at": CAPTURE, "event_name": "account_deletion_reviewed"})
        self.assertTrue(_compliant("RETAIN", obs))
        self.assertEqual(retention_proof(obs, AUDIT)["status"], "INSUFFICIENT")
        self.assertIsNone(_policy(RULES, obs, AUDIT)[0])

    def test_ordinary_retention_date_is_not_a_legal_hold(self):
        obs = observation({"retained_until": "2027-01-01T00:00:00Z", "retention_reason": "tax_record"},
                          category="LEGAL_HOLD_RECORD")
        self.assertEqual(retention_proof(obs, AUDIT)["status"], "INSUFFICIENT")
        self.assertIsNone(_policy(RULES, obs, AUDIT)[0])
        # An explicit active hold can outlive an ordinary retention schedule.
        held = {**obs, "record": {"retained_until": "2026-01-01T00:00:00Z", "hold_active": True}}
        self.assertEqual(_policy(RULES, held, AUDIT), ("RETAIN", None))
        released = {**held, "record": {"hold_active": False}}
        self.assertEqual(retention_proof(released, AUDIT)["status"], "EXPIRED")

    def test_join_requires_same_resource_subject_and_eligible_source(self):
        current = observation({"subject_reference": "person_target"})
        doc = observation({"subject_reference": "person_target", "retention_until": "2027-01-01T00:00:00Z"}, fid="document")
        proof = retention_proof(current, AUDIT, [doc])
        self.assertEqual(proof["status"], "ACTIVE")
        self.assertEqual(proof["proof"][0]["evidence_id"], "document")
        for unrelated in (
            {**doc, "resource_id": "different_journal"},
            {**doc, "record": {**doc["record"], "subject_reference": "person_other"}},
            {**doc, "capture_at": "2026-02-04T00:00:00Z"},
        ):
            self.assertEqual(retention_proof(current, AUDIT, [unrelated])["status"], "INSUFFICIENT")

    def test_conflicting_requirements_and_impossible_chronology(self):
        current = observation({"retention_until": "2027-01-01T00:00:00Z"})
        conflicting = observation({"retention_until": "2026-01-01T00:00:00Z"}, fid="conflicting")
        self.assertEqual(retention_proof(current, AUDIT, [conflicting])["status"], "CONTRADICTORY")
        invalid = observation({"event_recorded_at": "2026-02-01T00:00:00Z", "retention_until": "2026-01-01T00:00:00Z"})
        self.assertEqual(retention_proof(invalid, AUDIT)["status"], "CONTRADICTORY")

    def test_cached_document_join_and_consistent_rename_invariance(self):
        original = {"subject": "person_alpha", "email": "alpha@example.test", "resource": "entry_alpha",
                    "case": "request_alpha", "document_id": "document_alpha", "readback_id": "readback_alpha",
                    "document_path": "evidence/random_a.pdf", "readback_path": "evidence/random_b.json"}
        renamed = {"subject": "person_omega", "email": "omega@example.test", "resource": "entry_omega",
                   "case": "request_omega", "document_id": "document_omega", "readback_id": "readback_omega",
                   "document_path": "evidence/unrelated_z.pdf", "readback_path": "evidence/unrelated_y.json"}
        def build(root, names):
            (root / "evidence").mkdir()
            identity = {"user_id": names["subject"], "name": "Fictional Subject", "email": names["email"],
                        "phone": "", "email_hash": "", "updated_at": "2026-01-01T00:00:00Z"}
            csv_file(root / "user_identities.csv", list(identity), [identity])
            csv_file(root / "user_audit_log.csv", ["audit_id", "user_id", "event_time", "field_name", "old_value", "new_value"], [])
            csv_file(root / "system_activity.csv", ["activity_id", "event_time", "event_type", "source_system",
                "target_system", "resource_id", "reported_result", "details"], [])
            rule = {"rule_id": names["subject"] + "_rule", "data_category": "SECURITY_AUDIT_LOG",
                    **RULES["SECURITY_AUDIT_LOG"][0]}
            csv_file(root / "deletion_rules.csv", list(rule), [rule])
            doc = root / names["document_path"]
            blob = ("synthetic cached document " + names["resource"]).encode()
            doc.write_bytes(blob)
            cache = root / "cache"
            cache.mkdir()
            segments = [{"text": text, "location": f"page=1,line={n}"} for n, text in enumerate([
                "SIGNED RECORD EXTRACT", "Journal entry", "Event reference " + names["resource"],
                "subject reference " + names["subject"], "recorded 12 Jan 2026 04 03 UTC",
                "retain until 12 Jan 2027 04 03 UTC", "integrity seal valid"], 1)]
            source_cache_path(cache, blob, ".pdf", "local-ocr").write_text(json.dumps({
                "version": VERSION, "content_sha256": hashlib.sha256(blob).hexdigest(),
                "extractor": "independent_synthetic_cache_NOT_model", "segments": segments}))
            read_at = "2026-02-02T00:00:00Z"
            (root / names["readback_path"]).write_text(json.dumps({"exported_at": read_at, "origin": "security_service",
                "records": [{"recorded_at": read_at, "system": "security_service", "record_type": "SECURITY_AUDIT_LOG",
                             "resource_id": names["resource"], "subject_reference": names["subject"], "result": "FOUND"}]}))
            manifest = [{"file_id": names[k + "_id"], "file_path": names[k + "_path"], "origin": "security_service",
                         "captured_at": CAPTURE if k == "document" else read_at} for k in ("document", "readback")]
            csv_file(root / "evidence_files.csv", list(manifest[0]), manifest)
            request = {"case_id": names["case"], "email": names["email"], "audit_at": AUDIT,
                       "request_text": "Please erase my account and audit retained records."}
            return investigate(PublicIndex(root, cache), request)
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            before, after = build(Path(a), original), build(Path(b), renamed)
        replacements = {value: renamed[key] for key, value in original.items()}
        def translate(value):
            if isinstance(value, dict): return {key: translate(item) for key, item in value.items()}
            if isinstance(value, list): return [translate(item) for item in value]
            return replacements.get(value, value)
        self.assertIsNotNone(before["output"])
        self.assertEqual(translate(before["output"]), after["output"])
        self.assertEqual(before["output"]["deletion_status"], "COMPLETE")
        self.assertEqual(after["output"]["steps_json"][0]["evidence_id"], renamed["readback_id"])
        checks = after["ledger"]["retention_assessments"]
        self.assertTrue(any(p["evidence_id"] == renamed["document_id"] for c in checks for p in c["proof"]))


if __name__ == "__main__": unittest.main()

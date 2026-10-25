"""Independent parser and policy regressions; no public answers are loaded."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ghost_audit.public_index import PublicIndex, _json_rows, _log_rows, _sql_rows, _handover_rows, linked
from ghost_audit.public_runner import _policy, _compliant, deletion_intent, _make_output, _scope_kind
from test_audit import fixture

CAPTURE = "2026-02-01T00:00:00Z"
META = {"file_id": "proof", "file_path": "evidence/proof.json", "captured_at": CAPTURE}
IDENTITY = {"user_id": "user_target", "aliases": [
    {"field": "email", "value": "old@example.test"},
    {"field": "email", "value": "new@example.test"},
    {"field": "user_id", "value": "user_target"}]}


class PublicIndexTests(unittest.TestCase):
    def test_json_skips_future_row_without_losing_earlier_rows(self):
        obj = {"exported_at": CAPTURE, "origin": "operational_store", "records": [
            {"recorded_at": "2026-01-31T00:00:00Z", "system": "account_service",
             "resource_id": "account_target", "record_type": "USER_PROFILE",
             "result": "FOUND", "subject_reference": "old@example.test"},
            {"recorded_at": "2026-02-02T00:00:00Z", "system": "account_service",
             "resource_id": "account_future", "record_type": "USER_PROFILE",
             "result": "NOT_FOUND", "subject_reference": "old@example.test"}]}
        found, _ = _json_rows(obj, META)
        self.assertEqual([x["resource_id"] for x in found], ["account_target"])
        self.assertTrue(linked(found[0]["record"], IDENTITY))

    def test_trace_join_and_decoy_veto(self):
        text = "\n".join([
            "2026-02-01T00:00:00Z service=account_service trace_id=tr-a event=profile_lookup_started lookup_key=old@example.test",
            "2026-02-01T00:00:00Z service=account_service trace_id=tr-b event=profile_lookup_started lookup_key=old.extra@example.test",
            "2026-02-01T00:00:00Z service=account_service trace_id=tr-a event=profile_lookup_completed resource_id=account_target rows=0",
            "2026-02-01T00:00:00Z service=account_service trace_id=tr-b event=profile_lookup_completed resource_id=account_decoy rows=1 customer_reference=user_other",
        ])
        found, _ = _log_rows(text, META)
        matched = [x["resource_id"] for x in found if linked(x["record"], IDENTITY)]
        self.assertEqual(matched, ["account_target"])
        self.assertEqual(found[0]["state"], "ABSENT")

    def test_later_trace_identifier_cannot_relabel_earlier_readback(self):
        meta = {**META, "captured_at": "2026-02-03T00:00:00Z"}
        text = "\n".join([
            "2026-02-01T00:00:00Z service=account_service trace_id=tr-a event=profile_lookup_completed resource_id=account_target rows=1",
            "2026-02-02T00:00:00Z service=account_service trace_id=tr-a event=profile_lookup_started lookup_key=old@example.test",
        ])
        found, _ = _log_rows(text, meta)
        self.assertEqual(len(found), 1)
        self.assertFalse(linked(found[0]["record"], IDENTITY))

    def test_sql_inspects_other_categories_and_replica_scopes(self):
        sql = f"""-- Captured at: {CAPTURE}
CREATE TABLE customer_data_primary(resource_id TEXT,origin_system TEXT,collection_name TEXT,record_json TEXT,updated_at TEXT);
CREATE TABLE customer_data_read_replica(resource_id TEXT,origin_system TEXT,collection_name TEXT,record_json TEXT,updated_at TEXT);
INSERT INTO customer_data_primary VALUES('search_target','search_service','customer_search_documents','{{"resource_id":"search_target","email":"old@example.test"}}','{CAPTURE}');
INSERT INTO customer_data_read_replica VALUES('analytics_target','analytics_platform','customer_analytics_reports','{{"resource_id":"analytics_target","user_id":"user_target","email":"old@example.test"}}','{CAPTURE}');
"""
        found, scopes = _sql_rows(sql, META)
        self.assertEqual({x["category"] for x in found}, {"SEARCH_INDEX_ENTRY", "ANALYTICS_PROFILE"})
        self.assertEqual(len({x["scope"] for x in found}), 2)
        self.assertEqual(len(scopes), 2)
        self.assertEqual(len({_scope_kind(x) for x in found}), 2)

    def test_handover_requires_exact_identifier(self):
        text = (f"- {CAPTURE} | account_service | account_target | USER_PROFILE | NOT_FOUND | old@example.test\n"
                f"- {CAPTURE} | account_service | account_decoy | USER_PROFILE | FOUND | old.extra@example.test\n")
        found, _ = _handover_rows(text, META)
        self.assertEqual([x["resource_id"] for x in found if linked(x["record"], IDENTITY)], ["account_target"])

    def test_policy_retention_tombstone_and_process_order(self):
        rules = {"SECURITY_AUDIT_LOG": [{"condition": "Record is within the supplied retention period",
                                          "required_action": "RETAIN"}],
                 "ACCOUNT_TOMBSTONE": [{"condition": "Account is deleted and only a stable internal user_id is needed to preserve references to retained records",
                                        "required_action": "REDACT"}]}
        audit = {"system_id": "security_service", "category": "SECURITY_AUDIT_LOG", "resource_id": "audit_target",
                 "record": {"retention_until": "2027-01-01T00:00:00Z"}, "state": "PRESENT"}
        tomb = {"category": "ACCOUNT_TOMBSTONE", "resource_id": "tomb_target",
                "record": {"subject_reference": "user_target", "email": "old@example.test"}, "state": "PRESENT"}
        self.assertEqual(_policy(rules, audit, CAPTURE), ("RETAIN", None))
        self.assertFalse(_compliant("REDACT", tomb))
        def obs(rid, category, state):
            return {"system_id": "system", "resource_id": rid, "category": category,
                    "state": state, "record": {}, "evidence_id": "proof"}
        output = _make_output("custom", [
            {"obs": obs("account", "USER_PROFILE", "PRESENT"), "action": "DELETE", "compliant": False},
            {"obs": obs("flow", "DATA_FLOW", "ACTIVE"), "action": "DISABLE", "compliant": False},
            {"obs": obs("backup", "BACKUP_ARCHIVE", "ACTIVE"), "action": "BLOCK", "compliant": False}])
        remediation = [s["operation"] for s in output["steps_json"] if s["phase"] == "REMEDIATION"]
        self.assertEqual(remediation, ["DISABLE_DATA_FLOW", "BLOCK_RESTORE", "DELETE_RECORD"])
        self.assertTrue(all(s["evidence_id"] == "" for s in output["steps_json"] if s["phase"] != "FINDING"))

    def test_request_intent(self):
        self.assertFalse(deletion_intent("Please export my data. Do not delete my account."))
        self.assertTrue(deletion_intent("Veuillez supprimer définitivement mon compte."))
        self.assertTrue(deletion_intent("このアカウントの削除を依頼します。"))
        self.assertTrue(deletion_intent("Please check that the profile is gone and remaining records cannot identify me."))

    def test_public_index_cannot_read_reference_answers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root)
            (root / "sample_output.csv").write_text("forbidden reference contents")
            original = Path.open
            def guarded(path, *args, **kwargs):
                if path.name == "sample_output.csv":
                    raise AssertionError("Reference answer entered prediction path")
                return original(path, *args, **kwargs)
            with patch.object(Path, "open", guarded):
                index = PublicIndex(root, root / "cache")
                self.assertTrue(index.observations)


if __name__ == "__main__": unittest.main()

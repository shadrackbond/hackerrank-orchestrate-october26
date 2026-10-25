"""Scripted independent regressions; no model is invoked and no public answers read."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ghost_audit.core import Investigation, Rejected
from ghost_audit.public_index import PublicIndex, _log_rows, _visual_rows, linked, case_view
from ghost_audit.public_runner import investigate
from test_audit import fixture, csv_file, CAPTURE, CUTOFF


class IntegratedAgentTests(unittest.TestCase):
    def make_dataset(self, root, records):
        request = fixture(root)
        path = "evidence/neutral_document.json"
        (root / path).write_text(json.dumps({"exported_at": CAPTURE, "origin": "readback_service", "records": records}))
        csv_file(root / "evidence_files.csv", ["file_id", "file_path", "origin", "captured_at"], [
            {"file_id": "proof_scoped", "file_path": path, "origin": "readback", "captured_at": CAPTURE}])
        return request

    def test_json_policy_tools_and_diagnostic_share_rejection_and_compilation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = self.make_dataset(root, [{"system": "analytics_platform", "record_type": "ANALYTICS_PROFILE",
                "resource_id": "report_custom", "user_id": "user_target", "email": "old@example.test",
                "result": "IDENTIFIABLE", "recorded_at": CAPTURE}])
            rules = [{"rule_id": "analytics_rule", "data_category": "ANALYTICS_PROFILE",
                      "condition": "Record is still attributable to a user", "required_action": "ANONYMIZE"},
                     {"rule_id": "irrelevant_rule", "data_category": "USER_PROFILE", "condition": "Always", "required_action": "DELETE"}]
            csv_file(root / "deletion_rules.csv", list(rules[0]), rules)
            index = PublicIndex(root)
            session = Investigation(index, request)
            session.call("resolve_identity", {})
            inspected = session.call("inspect_evidence", {"evidence_id": "proof_scoped"})
            self.assertEqual(inspected["resources"][0]["required_action"], "ANONYMIZE")
            session.call("inspect_activity", {})
            proposal = session.decision_proposal()
            invalid = {**proposal, "deletion_status": "COMPLETE"}
            with self.assertRaisesRegex(Rejected, "required INCOMPLETE"):
                session.call("propose_decision", invalid)
            result = session.call("propose_decision", proposal)
            self.assertEqual(session.proposal_attempts, 2)
            diagnostic = investigate(index, request)
            self.assertEqual(diagnostic["output"], result)
            self.assertEqual(diagnostic["model_usage"]["calls"], 0)
            self.assertIn("DIAGNOSTIC", diagnostic["execution_kind"])
            self.assertEqual([s["operation"] for s in result["steps_json"]],
                             ["REPORT_EXPOSED_PII", "ANONYMIZE_RECORD", "VERIFY_RECORD_ANONYMIZED"])

    def test_complete_accepts_scoped_readback_without_sql_or_seven_systems(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = self.make_dataset(root, [{"recorded_at": CAPTURE, "system": "account_service",
                "resource_id": "retired_custom", "record_type": "USER_PROFILE", "result": "NOT_FOUND",
                "subject_reference": "old@example.test"}])
            result = investigate(PublicIndex(root), request)
            self.assertEqual(result["output"]["deletion_status"], "COMPLETE")
            step = result["output"]["steps_json"][0]
            self.assertEqual((step["operation"], step["evidence_id"]), ("VERIFY_RECORD_ABSENT", "proof_scoped"))
            self.assertTrue(result["ledger"]["coverage"]["complete_scope_certified"])

    def test_empty_unmatched_export_never_creates_absence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = self.make_dataset(root, [])
            result = investigate(PublicIndex(root), request)
            self.assertIsNone(result["output"])
            self.assertEqual(result["facts"], [])
            self.assertIn("No identity-linked resource state", result["ledger"]["remaining_gaps"])

    def test_explicit_source_reference_without_readback_remains_a_gap(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = self.make_dataset(root, [{"recorded_at": CAPTURE, "system": "search_service",
                "resource_id": "search_custom", "record_type": "SEARCH_INDEX_ENTRY", "result": "FOUND",
                "subject_reference": "old@example.test", "source_resource_id": "source_custom"}])
            rule = {"rule_id": "search_rule", "data_category": "SEARCH_INDEX_ENTRY", "condition": "Always", "required_action": "DELETE"}
            csv_file(root / "deletion_rules.csv", list(rule), [rule])
            result = investigate(PublicIndex(root), request)
            self.assertIsNone(result["output"])
            self.assertTrue(any("source_custom" in g and "state proof" in g for g in result["ledger"]["remaining_gaps"]))

    def test_stable_lookup_identifiers_match_with_conflict_and_time_controls(self):
        identity = {"user_id": "user_target", "aliases": [{"field": "user_id", "value": "user_target"}]}
        meta = {"file_id": "independent_log", "file_path": "evidence/random.log", "captured_at": CAPTURE}
        text = "\n".join([
            f"{CAPTURE} service=security_service trace_id=tr-good event=audit_record_read_completed resource_id=journal_a rows=1 correlation_key=user_target",
            f"{CAPTURE} service=security_service trace_id=tr-other event=audit_record_query_started subject_ref=user_other",
            f"{CAPTURE} service=security_service trace_id=tr-other event=audit_record_read_completed resource_id=journal_b rows=1 correlation_key=user_target",
            "2026-02-04T00:00:00Z service=security_service trace_id=tr-late event=audit_record_read_completed resource_id=journal_future rows=1 correlation_key=user_target",
        ])
        observations, _ = _log_rows(text, meta)
        self.assertEqual([o["resource_id"] for o in observations if linked(o["record"], identity)], ["journal_a"])
        self.assertTrue(linked({"subject_ref": "user_target"}, identity))

    def test_uncorrelated_lines_cannot_supply_each_others_identity(self):
        meta = {"file_id": "loose", "file_path": "evidence/loose.log", "captured_at": CAPTURE}
        identity = {"user_id": "user_target", "aliases": [{"field": "email", "value": "old@example.test"}]}
        observations, _ = _log_rows(
            f"{CAPTURE} service=account_service event=profile_lookup_started lookup_key=old@example.test\n"
            f"{CAPTURE} service=account_service event=profile_lookup_completed resource_id=unknown rows=1", meta)
        self.assertFalse(linked(observations[0]["record"], identity))

    def test_log_null_is_not_a_conflicting_subject_or_exposed_identifier(self):
        meta = {"file_id": "null_fixture", "file_path": "evidence/neutral.log", "captured_at": CAPTURE}
        identity = {"user_id": "user_target", "aliases": [{"field": "user_id", "value": "user_target"}]}
        found, _ = _log_rows(f"{CAPTURE} service=analytics_platform trace_id=tr-n event=analytics_profile_read_completed "
            "resource_id=aggregate_custom correlation_key=user_target customer_reference=null email=null phone=null email_hash=null", meta)
        self.assertTrue(linked(found[0]["record"], identity))
        self.assertEqual(found[0]["state"], "ANONYMIZED")
        self.assertIsNone(found[0]["record"]["customer_reference"])

    def test_visual_adapter_uses_content_under_unrelated_filenames(self):
        def parse(path):
            meta = {"file_id": "arbitrary_id", "file_path": path, "captured_at": CAPTURE}
            index = SimpleNamespace(visual_observations={"arbitrary_id": [{
                "text": "Customer details account_793 email: fictional@example.test",
                "source_location": path + "#image=1,bbox=1,2,3,4"}]})
            return _visual_rows(index, meta)[0]
        a, b = parse("evidence/unknown.png"), parse("evidence/backup_restore_console.png")
        self.assertTrue(a)
        for key in ("system_id", "category", "state", "record"):
            self.assertEqual(a[0][key], b[0][key])

    def test_catalog_identity_link_grounds_resource_but_not_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = self.make_dataset(root, [{"recorded_at": CAPTURE, "system": "account_service",
                "resource_id": "hidden_custom", "record_type": "USER_PROFILE", "result": "FOUND"}])
            index = PublicIndex(root)
            index.activity.append({"activity_id": "link_custom", "event_time": CAPTURE,
                "event_type": "LINK_RESOURCE_IDENTITY", "target_system": "account_service",
                "resource_id": "hidden_custom", "details": "Catalog linked hidden_custom to user_target.",
                "reported_result": "SUCCESS"})
            identity = index.identity(request["email"], CUTOFF)
            observations, _, _, links = case_view(index, identity, CUTOFF)
            self.assertEqual([o["resource_id"] for o in observations], ["hidden_custom"])
            self.assertEqual(len(links), 1)
            index.activity[0]["event_time"] = "2026-02-04T00:00:00Z"
            self.assertEqual(case_view(index, identity, CUTOFF)[0], [])


if __name__ == "__main__": unittest.main()

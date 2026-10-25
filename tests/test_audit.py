"""Independent synthetic cases; no sample answers or evaluation labels are loaded."""
import copy
import csv
import json
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ghost_audit.core import EvidenceIndex, Investigation, Limits, Rejected, write_csv


EARLY = "2026-01-01T00:00:00Z"
CAPTURE = "2026-02-01T00:00:00Z"
CUTOFF = "2026-02-03T00:00:00Z"
LATE = "2026-02-04T00:00:00Z"


def csv_file(path, fields, records):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def snapshot(capture=CAPTURE, present=True):
    # A decoy shares a similar email but is a different subject and resource.
    schema = "(resource_id TEXT, user_id TEXT, email TEXT, updated_at TEXT)"
    text = f"-- Captured at: {capture}\n-- Scope: complete profile tables; subject lookup old@example.test\n"
    for table in ("customer_profiles_primary", "customer_profiles_failover_replica"):
        text += f"CREATE TABLE {table} {schema};\n"
        text += f"INSERT INTO {table} VALUES ('account_decoy','user_other','old.extra@example.test','{EARLY}');\n"
    if present:
        text += f"INSERT INTO customer_profiles_failover_replica VALUES ('account_target','user_target','old@example.test','{EARLY}');\n"
    return text


def fixture(root, future=False, later_absence=False):
    (root / "evidence").mkdir()
    identities = [{"user_id": "user_target", "name": "Fictional Target", "email": "new@example.test",
                   "phone": "+1 555 010 9999", "email_hash": "hash-target", "updated_at": EARLY},
                  {"user_id": "user_other", "name": "Fictional Target", "email": "old.extra@example.test",
                   "phone": "+1 555 010 8888", "email_hash": "hash-other", "updated_at": EARLY}]
    csv_file(root / "user_identities.csv", list(identities[0]), identities)
    history = [{"audit_id": "audit_alias", "user_id": "user_target", "event_time": EARLY,
                "field_name": "email", "old_value": "old@example.test", "new_value": "new@example.test"}]
    csv_file(root / "user_audit_log.csv", list(history[0]), history)
    policy = {"rule_id": "custom_profile_rule", "data_category": "USER_PROFILE", "condition": "Always", "required_action": "DELETE"}
    csv_file(root / "deletion_rules.csv", list(policy), [policy])
    csv_file(root / "system_activity.csv", ["activity_id", "event_time", "event_type", "source_system",
        "target_system", "resource_id", "reported_result", "details"], [])
    manifests = []
    for fid, at, content in [("proof_early", CAPTURE, snapshot())] + (
        [("proof_future", LATE, snapshot(LATE, False))] if future else []) + (
        [("proof_absent", "2026-02-02T00:00:00Z", snapshot("2026-02-02T00:00:00Z", False))] if later_absence else []):
        path = f"evidence/{fid}.sql"
        (root / path).write_text(content)
        manifests.append({"file_id": fid, "file_path": path, "origin": "synthetic_profile_inventory", "captured_at": at})
    csv_file(root / "evidence_files.csv", list(manifests[0]), manifests)
    request = {"case_id": "custom_historical", "email": "old@example.test", "requested_at": EARLY,
               "reported_status": "COMPLETE", "reported_at": EARLY, "audit_at": CUTOFF,
               "request_text": "Please erase my account and its personal information."}
    csv_file(root / "sample_deletion_requests.csv", list(request), [request])
    return request


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, **kwargs):
        request = fixture(self.root, **kwargs)
        session = Investigation(EvidenceIndex(self.root), request)
        session.call("resolve_identity", {})
        session.call("search_evidence", {})
        session.call("inspect_profile_snapshot", {"evidence_id": "proof_early"})
        if kwargs.get("later_absence"):
            session.call("inspect_profile_snapshot", {"evidence_id": "proof_absent"})
        session.call("search_evidence", {})
        session.call("inspect_activity", {})
        return session

    def proposal(self, status="INCOMPLETE", evidence="proof_early", state="PRESENT"):
        return {"authorized": True, "request_quote": "Please erase my account", "deletion_status": status,
                "resources": [{"system_id": "account_service", "resource_id": "account_target", "state": state,
                               "required_action": "DELETE", "evidence_id": evidence}]}

    def test_non_deletion_contract(self):
        request = fixture(self.root)
        request["request_text"] = "Please export my records. Do not delete my account."
        session = Investigation(EvidenceIndex(self.root), request)
        # Explicitly a validator test, not a fake claim of live model classification.
        proposal = {"authorized": False, "request_quote": "Do not delete my account.",
                    "deletion_status": "NOT_APPLICABLE", "resources": []}
        result = session.call("propose_decision", proposal)
        self.assertEqual(result, {"case_id": "custom_historical", "deletion_status": "NOT_APPLICABLE", "steps_json": []})

    def test_explicit_deletion_audit_rejects_non_deletion_proposal(self):
        request = fixture(self.root)
        request["request_text"] = "Please check that the profile is gone and remaining records cannot identify me."
        session = Investigation(EvidenceIndex(self.root), request)
        proposal = {"authorized": False, "request_quote": "profile is gone",
                    "deletion_status": "NOT_APPLICABLE", "resources": []}
        with self.assertRaisesRegex(Rejected, "explicitly authorizes"):
            session.call("propose_decision", proposal)
        self.assertIsNone(session.result)

    def test_historical_identifier_and_decoy(self):
        session = self.prepare()
        self.assertEqual(session.identity["user_id"], "user_target")
        result = session.call("propose_decision", self.proposal())
        self.assertEqual([s["resource_id"] for s in result["steps_json"]], ["account_target"] * 3)
        self.assertEqual([s["evidence_id"] for s in result["steps_json"]], ["proof_early", "", ""])
        self.assertEqual([s["operation"] for s in result["steps_json"]],
                         ["REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_ABSENT"])

    def test_post_cutoff_evidence_is_not_searchable_or_citable(self):
        session = self.prepare(future=True)
        self.assertEqual(session.ledger["candidates"], ["proof_early"])
        with self.assertRaisesRegex(Rejected, "eligible identity-linked"):
            session.call("inspect_profile_snapshot", {"evidence_id": "proof_future"})
        with self.assertRaisesRegex(Rejected, "citation"):
            session.validate_proposal(self.proposal(evidence="proof_future"))
        result = session.validate_proposal(self.proposal())
        self.assertEqual(result["deletion_status"], "INCOMPLETE")

    def test_invalid_status_and_policy_are_rejected(self):
        session = self.prepare()
        with self.assertRaisesRegex(Rejected, "required INCOMPLETE"):
            session.call("propose_decision", self.proposal(status="COMPLETE"))
        wrong_policy = self.proposal()
        wrong_policy["resources"][0]["required_action"] = "RETAIN"
        with self.assertRaisesRegex(Rejected, "policy"):
            session.call("propose_decision", wrong_policy)
        self.assertIsNone(session.result)
        self.assertEqual(session.report()["internal_state"], "UNRESOLVED")

    def test_scripted_rejection_then_correction_within_budget(self):
        session = self.prepare()
        with self.assertRaisesRegex(Rejected, "required INCOMPLETE"):
            session.call("propose_decision", self.proposal(status="COMPLETE"))
        accepted = session.call("propose_decision", self.proposal())
        self.assertEqual(accepted["deletion_status"], "INCOMPLETE")
        self.assertEqual(session.proposal_attempts, 2)
        self.assertLessEqual(session.proposal_attempts, session.limits.proposal_attempts)
        self.assertEqual([event["accepted"] for event in session.trace if event["tool"] == "propose_decision"],
                         [False, True])
        self.assertEqual(session.report()["internal_state"], "SUPPORTED_SCOPE_RESOLVED")

    def test_complete_requires_cited_absence_across_replicas(self):
        session = self.prepare(later_absence=True)
        result = session.call("propose_decision", self.proposal("COMPLETE", "proof_absent", "ABSENT"))
        self.assertEqual(len(result["steps_json"]), 1)
        self.assertEqual(result["steps_json"][0]["evidence_id"], "proof_absent")
        self.assertEqual(result["steps_json"][0]["phase"], "VERIFICATION")

    def test_unknown_formats_prevent_complete(self):
        session = self.prepare(later_absence=True)
        session.ledger["deferred_sources"] = ["opaque_image"]
        with self.assertRaisesRegex(Rejected, "prevents a COMPLETE"):
            session.validate_proposal(self.proposal("COMPLETE", "proof_absent", "ABSENT"))

    def test_tool_proposal_and_wall_time_limits(self):
        request = fixture(self.root)
        index = EvidenceIndex(self.root)
        session = Investigation(index, request, Limits(tool_calls=1))
        session.call("resolve_identity", {})
        with self.assertRaisesRegex(Rejected, "Tool-call budget"):
            session.call("search_evidence", {})
        self.assertIsNone(session.result)
        session = Investigation(index, request, Limits(proposal_attempts=1))
        with self.assertRaises(Rejected):
            session.call("propose_decision", {})
        with self.assertRaisesRegex(Rejected, "Proposal-attempt"):
            session.call("propose_decision", {})
        session = Investigation(index, request, Limits(case_seconds=1))
        session.started -= 2
        with self.assertRaisesRegex(Rejected, "Case timeout"):
            session.call("resolve_identity", {})
        self.assertIsNone(session.result)

    def test_future_identity_does_not_leak(self):
        request = fixture(self.root)
        index = EvidenceIndex(self.root)
        index.history[0]["event_time"] = LATE
        index.identities[0]["updated_at"] = LATE
        with self.assertRaisesRegex(Rejected, "Identity unresolved"):
            index.identity("new@example.test", CUTOFF)

    def test_tool_timeout_cannot_be_followed_by_acceptance(self):
        session = self.prepare()
        session.limits = Limits(tool_seconds=0.001)
        original = session.index.search
        def slow_search(*args):
            time.sleep(0.005)
            return original(*args)
        with patch.object(session.index, "search", side_effect=slow_search):
            with self.assertRaisesRegex(Rejected, "Tool timeout"):
                session.call("search_evidence", {})
        with self.assertRaisesRegex(Rejected, "Tool timeout"):
            session.call("propose_decision", self.proposal())
        self.assertIsNone(session.result)

    def test_process_gap_survives_another_search(self):
        session = self.prepare()
        session.index.activity.append({"activity_id": "flow_claim", "event_time": CAPTURE,
            "event_type": "RESTORE_BACKUP", "source_system": "backup", "target_system": "account_service",
            "resource_id": "backup_target", "reported_result": "SUCCESS", "details": "subject user_target"})
        session.call("inspect_activity", {})
        session.call("search_evidence", {})
        self.assertIn("backup_target", session.ledger["discovered_processes"])
        with self.assertRaisesRegex(Rejected, "Unresolved investigation gaps"):
            session.validate_proposal(self.proposal())

    def test_future_activity_is_excluded(self):
        session = self.prepare()
        session.index.activity.append({"activity_id": "future_flow", "event_time": LATE,
            "event_type": "RESTORE_BACKUP", "source_system": "backup", "target_system": "account_service",
            "resource_id": "account_target", "reported_result": "SUCCESS", "details": "subject user_target"})
        self.assertEqual(session.call("inspect_activity", {})["claims_not_state_proof"], [])

    def test_sql_cannot_attach_external_database(self):
        session = self.prepare()
        session.index.contents["proof_early"] += "\nATTACH DATABASE '/tmp/forbidden.db' AS outside;"
        with self.assertRaisesRegex(Rejected, "not authorized"):
            session.call("inspect_profile_snapshot", {"evidence_id": "proof_early"})

    def test_reference_answers_are_not_read_by_predictor(self):
        request = fixture(self.root)
        forbidden = self.root / "sample_output.csv"
        forbidden.write_text("not even valid CSV")
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path.name == "sample_output.csv":
                raise AssertionError("Prediction attempted to read reference answers")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", guarded):
            index = EvidenceIndex(self.root)
            self.assertEqual(index.identity(request["email"], CUTOFF)["user_id"], "user_target")

    def test_ambiguous_identity_is_not_merged(self):
        request = fixture(self.root)
        index = EvidenceIndex(self.root)
        index.identities[1]["email"] = "old@example.test"
        with self.assertRaisesRegex(Rejected, "2 candidate"):
            index.identity(request["email"], CUTOFF)

    def test_csv_round_trip(self):
        session = self.prepare()
        result = session.validate_proposal(self.proposal())
        path = self.root / "review.csv"
        write_csv(path, result)
        with path.open() as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, ["case_id", "deletion_status", "steps_json"])
            records = list(reader)
        self.assertEqual(len(records), 1)
        self.assertEqual(json.loads(records[0]["steps_json"]), result["steps_json"])


if __name__ == "__main__":
    unittest.main()

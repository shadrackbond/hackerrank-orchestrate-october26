"""Synthetic tool/replay fixtures only. No model, public references or live usage."""
import copy
import contextlib
import io
from dataclasses import replace
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ghost_audit.core import Investigation, Limits, Rejected
from ghost_audit.authorization import deletion_authorization
from ghost_audit.engine import _policy, _compliant
from ghost_audit.public_index import PublicIndex, _record_state
from ghost_audit.presentation import compact
from ghost_audit.saved import seal, load, revalidate, aggregate_usage
from ghost_audit.delivery import batch
from test_audit import fixture, csv_file, CAPTURE


class CorrectnessTests(unittest.TestCase):
    def test_negation_scope_paraphrases_and_both_proposal_directions(self):
        limited = ["I am not requesting deletion; please export my data",
            "I do not want my profile deleted. Send an export instead.",
            "No account deletion, please; I only want a download.",
            "Please refrain from erasing my profile and export the records.",
            "Account removal is not requested; I need access to my records.",
            "Please remove me from your marketing lists.",
            "Delete my advertising account but preserve my shopping account.",
            "Remove my marketing account and keep the customer profile.",
            "Erase my personal data from promotional mailing lists; keep my account.",
            "Delete my marketing profile and leave my account open."]
        with tempfile.TemporaryDirectory() as directory:
            request = fixture(Path(directory)); index = PublicIndex(Path(directory))
            for text in limited:
                with self.subTest(text=text):
                    self.assertIs(deletion_authorization(text), False)
                    session = Investigation(index, {**request, "request_text": text})
                    wrong = {"authorized": True, "request_quote": text, "deletion_status": "COMPLETE", "resources": []}
                    with self.assertRaisesRegex(Rejected, "scope or negation"):
                        session.call("propose_decision", wrong)
                    output = session.call("propose_decision", {**wrong, "authorized": False, "deletion_status": "NOT_APPLICABLE"})
                    self.assertEqual(output["steps_json"], [])
            for text in ("Export my data first, then delete my account.",
                         "Delete my account and unsubscribe me from marketing.",
                         "Do not send an export and delete my account instead.",
                         "Erase all my personal data including marketing information.",
                         "I am not asking for an export; please erase all my personal data."):
                self.assertIs(deletion_authorization(text), True, text)
                session = Investigation(index, {**request, "request_text": text})
                with self.assertRaisesRegex(Rejected, "explicitly authorizes"):
                    session.call("propose_decision", {"authorized": False, "request_quote": text,
                        "deletion_status": "NOT_APPLICABLE", "resources": []})

    def test_claimed_redaction_and_anonymization_cannot_override_fields(self):
        for subject, email in (("opaque-alpha", "alpha@example.test"), ("renamed-omega", "omega@example.test")):
            for category, state, action in (("ACCOUNT_TOMBSTONE", "REDACTED", "REDACT"),
                                            ("ANALYTICS_PROFILE", "ANONYMIZED", "ANONYMIZE")):
                row = {"result": state, "user_id": subject, "name": None,
                    "email": email, "phone": None, "email_hash": None}
                self.assertEqual(_record_state(row, category), "UNKNOWN")
                self.assertFalse(_compliant(action, {"category": category, "state": state, "record": row}))
                row["email"] = None
                if action == "ANONYMIZE": row["user_id"] = None
                self.assertEqual(_record_state(row, category), state)
                self.assertTrue(_compliant(action, {"category": category, "state": state, "record": row}))
                self.assertFalse(_compliant(action, {"category": category, "state": state, "record": {"result": state}}))

    def test_support_context_needs_a_grounded_relationship_not_just_text(self):
        rules = {"SUPPORT_MESSAGE": [{"condition": "Conversation contains shared customer, agent, or order context that must be retained",
                                     "required_action": "REDACT"}]}
        for field in ("message_text", "message_excerpt", "body", "content"):
            obs = {"category": "SUPPORT_MESSAGE", "resource_id": "arbitrary-note", "record": {field: "Hello, thank you."}}
            self.assertIsNotNone(_policy(rules, obs, "2026-02-03T00:00:00Z")[1])

            for ref in ("purchase-alpha", "renamed-reference-omega"):
                obs["record"] = {field: f"We discussed {ref} with the customer.", "order_reference": ref}
                self.assertEqual(_policy(rules, obs, "2026-02-03T00:00:00Z"), ("REDACT", None))
            obs["record"] = {field: "The replacement has been dispatched.", "author_role": "agent"}
            self.assertEqual(_policy(rules, obs, "2026-02-03T00:00:00Z"), ("REDACT", None))
            obs["record"] = {field: "Hello", "shared_context_verified": True}
            self.assertIsNotNone(_policy(rules, obs, "2026-02-03T00:00:00Z")[1])

    def test_conflicting_treatment_readback_prevents_a_final_case_decision(self):
        for category, result, action in (("ACCOUNT_TOMBSTONE", "REDACTED", "REDACT"),
                                         ("ANALYTICS_PROFILE", "ANONYMIZED", "ANONYMIZE")):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory); request = fixture(root)
                record = {"system": "identity_service", "record_type": category, "resource_id": "opaque-note",
                    "user_id": "user_target", "name": None, "email": "old@example.test", "phone": None,
                    "email_hash": None, "result": result}
                (root / "evidence/arbitrary.json").write_text(json.dumps({"origin": "readback", "records": [record]}))
                meta = {"file_id": "opaque-proof", "file_path": "evidence/arbitrary.json", "origin": "readback", "captured_at": CAPTURE}
                csv_file(root / "evidence_files.csv", list(meta), [meta])
                rule = {"rule_id": "independent-rule", "data_category": category, "condition": "Always", "required_action": action}
                csv_file(root / "deletion_rules.csv", list(rule), [rule])
                session = Investigation(PublicIndex(root), request)
                session.call("resolve_identity", {})
                session.call("inspect_evidence", {"evidence_id": "opaque-proof"})
                session.call("inspect_activity", {})
                self.assertTrue(session.ledger["unresolved_contradictions"])
                with self.assertRaisesRegex(Rejected, "Unresolved investigation"):
                    session.call("propose_decision", session.decision_proposal())
                self.assertIsNone(session.result)



class SavedDecisionTests(unittest.TestCase):
    def saved(self, root):
        request = fixture(root); index = PublicIndex(root)
        session = Investigation(index, request)
        session.call("resolve_identity", {})
        session.call("inspect_evidence", {"evidence_id": "proof_early"})
        session.call("inspect_activity", {})
        session.call("propose_decision", session.decision_proposal())
        run = root / "attempt"; run.mkdir()
        report = session.report()
        (run / "investigation.json").write_text(json.dumps(report))
        seal(run, "SCRIPTED_REPLAY_TEST")
        manifest, report = load(run / "decision.json")
        return request, index, run, manifest, report

    def test_replay_is_contract_checked_and_preserves_scripted_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            request,index,run,manifest,report = self.saved(Path(directory))
            rebuilt = revalidate(index, request, manifest, report, Limits())
            self.assertEqual(rebuilt["output"], report["output"])
            self.assertEqual(rebuilt["execution_kind"], "SCRIPTED_REPLAY_TEST")
            self.assertEqual(rebuilt["decision_provenance"]["new_model_calls"], 0)
            self.assertEqual(aggregate_usage([manifest])["saved_runtime_invocations"], 0)
            changed = copy.deepcopy(report); changed["output"]["steps_json"].pop()
            with self.assertRaisesRegex(Rejected, "differs"):
                revalidate(index, request, manifest, changed)

    def test_delivery_imports_replays_and_records_stale_rejections_without_a_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request,index,run,manifest,report = self.saved(root)
            with contextlib.redirect_stdout(io.StringIO()):
                first = batch(root, root / "cache", root / "batch-a", samples=True, saved_decisions=[run])
                second = batch(root, root / "cache", root / "batch-b", samples=True, saved_decisions=[run])
                stale = batch(root, root / "cache", root / "batch-c", samples=True, saved_decisions=[run],
                              saved_limits=replace(Limits(), tool_calls=9))
            self.assertEqual(first["decision_provenance_counts"], {"SCRIPTED_REPLAY_TEST": 1})
            self.assertEqual(second["saved_usage"]["new_model_calls"], 0)
            self.assertEqual(stale["saved_import_rejections"], 1)
            self.assertEqual(stale["decision_provenance_counts"], {"DETERMINISTIC_DIAGNOSTIC_NOT_LIVE_AGENT": 1})
            self.assertTrue((root / "batch-c" / "saved_imports.json").exists())

    def test_stale_request_inputs_configuration_and_trace_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            request,index,run,manifest,report = self.saved(Path(directory))
            with self.assertRaisesRegex(Rejected, "complete current request"):
                revalidate(index, {**request, "audit_at": "2026-02-02T00:00:00Z"}, manifest, report)
            with self.assertRaisesRegex(Rejected, "configuration"):
                revalidate(index, request, manifest, report, replace(Limits(), tool_calls=9))
            for field in ("rules", "manifest", "identities", "visual_observations"):
                old = copy.deepcopy(getattr(index, field))
                if isinstance(old, list): getattr(index, field).append({"changed": "participant fact"})
                else: getattr(index, field)["changed"] = {"participant": "fact"}
                with self.assertRaisesRegex(Rejected, "stale"):
                    revalidate(index, request, manifest, report)
                setattr(index, field, old)
            broken = copy.deepcopy(report); broken["trace"][0]["arguments"] = {"file_path": "unapproved"}
            with self.assertRaisesRegex(Rejected, "recorded validation outcome"):
                revalidate(index, request, manifest, broken)
            (run / "investigation.json").write_text("{}")
            with self.assertRaisesRegex(Rejected, "checksum"):
                load(run / "decision.json")

    def test_usage_deduplicates_invocations_and_keeps_unknowns_visible(self):
        # Numeric usage below is synthetic aggregation input, never a live observation.
        item = {"kind": "MODEL_ASSISTED", "invocation_id": "synthetic-a", "usage": {
            "provider": "SYNTHETIC_TEST_ONLY", "requested_model": "synthetic-not-live", "usage_available": True,
            "tokens": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 5}, "wall_seconds": 2}}
        missing = copy.deepcopy(item); missing["invocation_id"] = "synthetic-b"
        missing["usage"].update(usage_available=False, tokens=None)
        usage = aggregate_usage([item, item, missing])
        row = next(iter(usage["known_usage_subtotals_by_model"].values()))
        self.assertEqual((row["input_tokens"], row["uncached_input_tokens"], row["output_tokens"]), (100, 20, 5))
        self.assertEqual(usage["saved_runtime_invocations"], 2)
        self.assertFalse(usage["totals_complete"])

    def test_native_artifact_shape_and_usage_checks_with_offline_synthetic_events(self):
        # This tests the MODEL_ASSISTED file format, not a real model interaction.
        with tempfile.TemporaryDirectory() as directory:
            request,index,run,manifest,report = self.saved(Path(directory))
            amounts = {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 5}
            usage = {"provider": "SYNTHETIC_TEST_ONLY", "requested_model": "synthetic-not-live",
                "usage_available": True, "tokens": amounts, "outcome": "finished", "wall_seconds": 2}
            (run / "model_events.jsonl").write_text(json.dumps({"type": "turn.completed", "usage": amounts}) + "\n")
            (run / "usage.json").write_text(json.dumps(usage))
            seal(run, "MODEL_ASSISTED", usage, {"model": "synthetic-not-live", "limits": report["limits"]})
            sealed, _ = load(run / "decision.json")
            self.assertEqual(sealed["usage"]["provider"], "SYNTHETIC_TEST_ONLY")
            import main as application
            argv = ["main.py", "--samples", "--case", request["case_id"], "--model", "synthetic-not-live",
                    "--dataset", str(Path(directory)), "--run-dir", str(run), "--resume"]
            with patch.object(sys, "argv", argv), patch.object(application, "run_codex") as model, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(application.main(), 0)
                model.assert_not_called()
            (run / "model_events.jsonl").write_text("{}\n")
            with self.assertRaisesRegex(Rejected, "trace checksum"):
                load(run / "decision.json")

    def test_compact_response_pages_records_and_omits_global_graph(self):
        original = {"observations": [{"category": "USER_PROFILE", "resource_id": str(n), "trace_proof": []}
                                     for n in range(100)], "resource_links": [{"graph": "large"}] * 300}
        value = compact(original, 20, 10)
        self.assertEqual(len(value["observations"]), 10)
        self.assertEqual(value["pagination"]["observations"]["next_offset"], 30)
        self.assertNotIn("resource_links", value)
        self.assertEqual(len(original["observations"]), 100)


if __name__ == "__main__": unittest.main()

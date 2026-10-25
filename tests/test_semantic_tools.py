"""Synthetic validator interactions, explicitly not live model behavior."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ghost_audit.core import EvidenceIndex, Investigation, Rejected
from ghost_audit.extraction import VERSION, source_cache_path
from test_audit import fixture, csv_file, CAPTURE


class SemanticToolTests(unittest.TestCase):
    def session(self, root, visual=False, other_subject=False, explicit_type=True):
        request = fixture(root)
        rule = {"rule_id": "support_rule", "data_category": "SUPPORT_MESSAGE",
                "condition": "Conversation contains shared customer, agent, or order context that must be retained",
                "required_action": "REDACT"}
        csv_file(root / "deletion_rules.csv", list(rule), [rule])
        suffix = ".pdf" if visual else ".log"
        path = root / ("evidence/neutral" + suffix)
        cache = root / "cache"
        if visual:
            blob = b"independent cached customer record"
            path.write_bytes(blob)
            cache.mkdir()
            lines = ["Support reference ticket_X / note_custom", "Customer old@example.test",
                     "Order ORD-X: agent arranged a delivery update."]
            if explicit_type: lines.append("Conversation record note_custom")
            if other_subject: lines.append("Another customer different@example.test")
            source_cache_path(cache, blob, suffix, "local-ocr").write_text(json.dumps({"version": VERSION,
                "content_sha256": hashlib.sha256(blob).hexdigest(), "extractor": "synthetic_cache_NOT_model",
                "segments": [{"text": text, "location": f"page=1,line={n}"} for n, text in enumerate(lines, 1)]}))
        else:
            path.write_text(f'{CAPTURE} service=support_platform trace_id=tr-custom event=message_scan_started subject_key=old@example.test\n'
                f'{CAPTURE} service=support_platform trace_id=tr-custom event=message_read resource_id=note_custom '
                'body="Agent discussed order ORD-X and old@example.test in the delivery conversation."\n')
        row = {"file_id": "proof_custom", "file_path": "evidence/neutral" + suffix,
               "origin": "support_platform", "captured_at": CAPTURE}
        csv_file(root / "evidence_files.csv", list(row), [row])
        session = Investigation(EvidenceIndex(root, cache if visual else None, "local-ocr"), request)
        session.call("resolve_identity", {})
        session.call("inspect_evidence", {"evidence_id": "proof_custom"})
        return session

    def proposal(self, session, visual=False):
        units = session.call("read_semantic_evidence", {"evidence_id": "proof_custom"})["units"]
        def quote(unit, role): return {"source_location": unit["source_location"], "quote": unit["text"], "role": role}
        quotes = [quote(units[1], "CONTEXT")]
        if visual:
            quotes = [quote(units[0], "RESOURCE"), quote(units[1], "SUBJECT"), quote(units[2], "CONTEXT")]
            quotes.extend(quote(u, "TYPE") for u in units if "Conversation record" in u["text"])
        return {"kind": "VISUAL_SUPPORT_RECORD" if visual else "SUPPORT_SHARED_CONTEXT", "evidence_id": "proof_custom",
                "system_id": "support_platform", "resource_id": "note_custom", "conclusion": "CONFIRMED",
                **({"context_type": "SHARED_ORDER"} if not visual else {}), "supporting_quotes": quotes, "explanation": "The quoted customer record contains shared order context."}

    def test_cited_context_interpretation_uses_shared_policy_compilation(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.session(Path(folder))
            accepted = session.call("propose_semantic_assessment", self.proposal(session))
            self.assertIsNotNone(accepted["assessment"]["observation"])
            session.call("inspect_activity", {})
            output = session.call("propose_decision", session.decision_proposal())
            self.assertEqual(output["deletion_status"], "INCOMPLETE")
            self.assertEqual([s["operation"] for s in output["steps_json"]],
                             ["REPORT_EXPOSED_PII", "REDACT_RECORD", "VERIFY_RECORD_REDACTED"])
            self.assertEqual(session.proposal_attempts, 2)

    def test_operational_metadata_and_fabricated_resource_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.session(Path(folder))
            proposal = self.proposal(session)
            unit = session.call("read_semantic_evidence", {"evidence_id": "proof_custom"})["units"][0]
            proposal["supporting_quotes"] = [{"source_location": unit["source_location"], "quote": unit["text"], "role": "CONTEXT"}]
            with self.assertRaisesRegex(Rejected, "Operational lookup"):
                session.call("propose_semantic_assessment", proposal)
            proposal["resource_id"] = "invented_resource"
            with self.assertRaisesRegex(Rejected, "not grounded"):
                session.call("propose_semantic_assessment", proposal)
            self.assertIsNone(session.result)

    def test_visual_customer_record_requires_literal_subject_and_resource(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.session(Path(folder), visual=True)
            session.call("propose_semantic_assessment", self.proposal(session, visual=True))
            session.call("inspect_activity", {})
            output = session.call("propose_decision", session.decision_proposal())
            self.assertEqual({s["resource_id"] for s in output["steps_json"]}, {"note_custom"})
            self.assertEqual(output["steps_json"][0]["evidence_id"], "proof_custom")
        with tempfile.TemporaryDirectory() as folder:
            session = self.session(Path(folder), visual=True, other_subject=True)
            with self.assertRaisesRegex(Rejected, "unassociated subject"):
                session.call("propose_semantic_assessment", self.proposal(session, visual=True))

    def test_shared_order_and_support_reference_do_not_establish_category(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.session(Path(folder), visual=True, explicit_type=False)
            with self.assertRaisesRegex(Rejected, "category unproved"):
                session.call("propose_semantic_assessment", self.proposal(session, visual=True))
            self.assertIsNone(session.result)
            self.assertFalse(session.semantic_observations)

    def test_unknown_review_does_not_clear_gaps_or_accept_final_output(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.session(Path(folder))
            proposal = self.proposal(session)
            proposal["conclusion"] = "INSUFFICIENT"
            review = session.call("propose_semantic_assessment", proposal)
            self.assertIsNone(review["assessment"]["observation"])
            self.assertTrue(session.ledger["remaining_gaps"])
            self.assertIsNone(session.result)


if __name__ == "__main__": unittest.main()

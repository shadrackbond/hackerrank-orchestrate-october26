"""Independent structural/contract regressions; no public reference inputs."""
import copy
import contextlib
import io
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ghost_audit.contract import validate_report
from ghost_audit.core import Rejected
from ghost_audit.public_index import PublicIndex, _json_rows, _log_rows, _record_state, _visual_rows, linked
from ghost_audit.public_runner import investigate
from ghost_audit.delivery import batch
from test_audit import CAPTURE, fixture
from test_public_index import IDENTITY


class DeliveryTests(unittest.TestCase):
    def test_search_hit_identity_is_not_the_query_or_wrapper_id(self):
        meta = {"file_id": "independent_proof", "file_path": "evidence/renamable.json", "captured_at": CAPTURE}
        payload = {"source": "search_service", "collection": "index_queries", "records": [{
            "resource_id": "query_task", "query": "old@example.test", "hits": {"total": 2, "documents": [
                {"resource_id": "actual_document", "email": "old@example.test"},
                {"resource_id": "unrelated_document", "email": "someone@example.test"}]}}]}
        observations, _ = _json_rows(payload, meta)
        self.assertEqual([o["resource_id"] for o in observations], ["actual_document", "unrelated_document"])
        self.assertEqual([o["resource_id"] for o in observations if linked(o["record"], IDENTITY)], ["actual_document"])

    def test_order_prose_with_support_reference_is_not_a_message_resource(self):
        meta = {"file_id": "context_only", "file_path": "evidence/neutral.pdf", "captured_at": CAPTURE}
        text = "Support reference ticket-Q / support_731; shared order conversation for old@example.test"
        index = SimpleNamespace(visual_observations={"context_only": [{"text": text,
            "source_location": "evidence/neutral.pdf#page=1,line=1"}]})
        self.assertEqual(_visual_rows(index, meta)[0], [])

    def test_contact_index_is_not_a_conversation_and_preserves_origin(self):
        meta = {"file_id": "opaque_evidence", "file_path": "evidence/arbitrary.log", "origin": "support_platform",
                "captured_at": CAPTURE}
        text = (f"{CAPTURE} service=support_replica trace_id=tr-independent event=contact_query_started "
                "lookup_key=old@example.test source=historic_contact_index\n"
                f"{CAPTURE} service=support_replica trace_id=tr-independent event=contact_query_completed "
                "resource_id=opaque_contact rows=1")
        observations, _ = _log_rows(text, meta)
        self.assertEqual(len(observations), 1)
        obs = observations[0]
        self.assertEqual((obs["category"], obs["system_id"]), ("SECONDARY_IDENTIFIER", "support_platform"))
        self.assertEqual(obs["source_system_label"], "support_replica")
        self.assertEqual(len(obs["trace_proof"]), 2)
        self.assertTrue(linked(obs["record"], IDENTITY))
        # A bare support reference proves no conversation category or state.
        bare = text.replace("contact_query", "ticket_query").replace("historic_contact_index", "order_register")
        self.assertEqual(_log_rows(bare, meta)[0], [])

    def test_missing_tombstone_fields_do_not_prove_redaction(self):
        self.assertEqual(_record_state({"user_id": "opaque-subject"}, "ACCOUNT_TOMBSTONE"), "UNKNOWN")
        self.assertEqual(_record_state({"user_id": "opaque-subject", "name": None, "email": None,
            "phone": None, "email_hash": None}, "ACCOUNT_TOMBSTONE"), "REDACTED")

    def test_unknown_process_flags_do_not_prove_disabled_or_blocked(self):
        for record, category in [({"enabled": "unknown"}, "DATA_FLOW"),
                                 ({"eligible": True}, "BACKUP_ARCHIVE"),
                                 ({"restore_allowed": "unknown"}, "BACKUP_ARCHIVE")]:
            self.assertEqual(_record_state(record, category), "UNKNOWN")
        self.assertEqual(_record_state({"eligible": True, "deletion_block": False}, "BACKUP_ARCHIVE"), "ACTIVE")
        self.assertEqual(_record_state({"deletion_block": True}, "BACKUP_ARCHIVE"), "BLOCKED")

    def report(self, root):
        request = fixture(root)
        report = investigate(PublicIndex(root), request)
        self.assertIsNotNone(report["output"])
        return report

    def test_delivery_rejects_missing_steps_invalid_future_citations_and_cutoff(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.report(Path(directory))
            self.assertEqual(validate_report(report), report["output"])
            missing = copy.deepcopy(report)
            missing["output"]["steps_json"].pop()
            with self.assertRaisesRegex(Rejected, "coverage"):
                validate_report(missing)
            citation = copy.deepcopy(report)
            citation["output"]["steps_json"][-1]["evidence_id"] = "independent_proof"
            with self.assertRaisesRegex(Rejected, "empty citations"):
                validate_report(citation)
            late = copy.deepcopy(report)
            for observation in late["observations"]:
                observation["capture_at"] = "2027-01-01T00:00:00Z"
            with self.assertRaisesRegex(Rejected, "audit_at"):
                validate_report(late)

    def test_unresolved_cannot_be_delivered(self):
        with self.assertRaisesRegex(Rejected, "unresolved"):
            validate_report({"output": None})

    def test_public_subset_never_passes_submission_publication_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            output = root / "output.csv"
            with contextlib.redirect_stdout(io.StringIO()):
                summary = batch(root, root / "cache", root / "diagnostic", samples=True, publish=output)
            self.assertEqual(summary["resolved"], 1)
            self.assertIn("publication_blocker", summary)
            self.assertFalse(output.exists())
            self.assertTrue((root / "diagnostic" / "supported_partial.csv").exists())


if __name__ == "__main__": unittest.main()

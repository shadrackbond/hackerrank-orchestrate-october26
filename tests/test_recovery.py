"""Independent recovery fixtures. Semantic proposals here are scripted, not model calls."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ghost_audit.authorization import Authorization, authorization_status
from ghost_audit.core import Investigation, Rejected
from ghost_audit.public_index import PublicIndex
from ghost_audit.proof import support_context_proof
from ghost_audit.semantic import validate_assessment
from test_audit import fixture, csv_file, CAPTURE


class RecoveryTests(unittest.TestCase):
    def test_three_way_authorization_and_french_morphology(self):
        for text in ("Je demande la suppression de mon compte.",
                     "Veuillez supprimer définitivement le compte et ses données personnelles.",
                     "Je souhaite l'effacement de mes données personnelles.",
                     "Je ne demande pas un export, mais je souhaite supprimer mon compte."):
            self.assertEqual(authorization_status(text), Authorization.YES)
        for text in ("Je ne demande pas la suppression du compte, seulement un export.",
                     "Ne supprimez pas mon compte.",
                     "Supprimez mes données des listes publicitaires uniquement.",
                     "Remove me from marketing only; keep the account.",
                     "Please export my data.",
                     "Unsubscribe me from your marketing lists."):
            self.assertEqual(authorization_status(text), Authorization.NO)
        for text in ("أطلب حذف حسابي وإرسال export", "Export mis datos y borrar mi cuenta."):
            self.assertEqual(authorization_status(text), Authorization.UNCERTAIN)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); request = fixture(root)
            request["request_text"] = "أطلب حذف حسابي وإرسال export"
            session = Investigation(PublicIndex(root), request)
            session.call("resolve_identity", {})
            session.call("inspect_evidence", {"evidence_id": "proof_early"})
            session.call("inspect_activity", {})
            # A grounded model interpretation is not vetoed by an unknown language.
            output = session.call("propose_decision", session.decision_proposal())
            self.assertEqual(output["deletion_status"], "INCOMPLETE")

    def test_order_context_without_an_order_identifier_is_not_just_a_keyword(self):
        for field in ("body", "message_text", "message_excerpt", "content"):
            for text in ("A buyer requested an order status update.",
                         "The customer provided information for a delivery question."):
                self.assertTrue(support_context_proof({field: text}))
            for text in ("Hello", "Order", "The word order appears in this sentence."):
                self.assertFalse(support_context_proof({field: text}))
        self.assertFalse(support_context_proof({"body": "Hello", "author_role": "agent"}))

    def semantic_fixture(self, fmt, resource, subject):
        fid, path = "independent-proof", "evidence/arbitrary." + fmt
        content = "The shopper needed help restoring access after an unsuccessful verification check."
        record = {"resource_id": resource, "body": content}
        location = path + ("#records/4" if fmt == "json" else "#line=8,trace=tr-arbitrary" if fmt == "log" else "#page=2,line=8")
        observation = {"system_id": "support_platform", "resource_id": resource, "evidence_id": fid,
                       "category": "SUPPORT_MESSAGE", "record": record, "observed_at": CAPTURE,
                       "source_location": location}
        unit = {"source_location": location, "text": json.dumps(record) if fmt == "json" else
                "trace=tr-arbitrary resource_id=" + resource + " body=" + content if fmt == "log" else content}
        visual = fmt == "pdf"
        units = [unit]
        quotes = [{"source_location": path + "#line=8" if fmt == "log" else location, "quote": content, "role": "CONTEXT"}]
        if visual:
            observation["record"] = {"resource_id": resource, "visual_text": content}
            for line, text, role in ((2, resource, "RESOURCE"), (3, subject, "SUBJECT")):
                loc = path + f"#page=2,line={line}"
                units.append({"source_location": loc, "text": text})
                quotes.append({"source_location": loc, "quote": text, "role": role})
        index = SimpleNamespace(manifest={fid: {"captured_at": CAPTURE, "file_path": path}},
            visual_observations={fid: [{"source_location": u["source_location"], "text": u["text"]} for u in units]} if visual else {},
            contents={fid: unit["text"]})
        if fmt == "log":
            # The raw line is numbered consistently with the observation's location.
            index.contents[fid] = "\n"*7 + unit["text"]
        session = SimpleNamespace(index=index, identity={"aliases": [{"field": "email", "value": subject}]},
            ledger={"candidates": [fid], "identity_links": []}, inspected={fid},
            request={"audit_at": "2026-02-03T00:00:00Z"}, observations=[observation])
        proposal = {"kind": "SUPPORT_SHARED_CONTEXT", "context_type": "SHARED_CUSTOMER", "evidence_id": fid,
            "system_id": "support_platform", "resource_id": resource, "conclusion": "CONFIRMED",
            "supporting_quotes": quotes, "explanation": "The cited content preserves the customer's support interaction about restoring access."}
        return session, proposal

    def test_semantic_interpretation_accepts_equivalent_json_log_and_visual_content(self):
        for fmt in ("json", "log", "pdf"):
            for resource, subject in (("note-alpha", "alpha@example.test"), ("renamed-omega", "omega@example.test")):
                session, proposal = self.semantic_fixture(fmt, resource, subject)
                review = validate_assessment(session, proposal)
                self.assertTrue(review["observation"]["record"]["shared_context_verified"])
                proposal["supporting_quotes"][0]["quote"] = "unsupported invented message"
                with self.assertRaises(Rejected): validate_assessment(session, proposal)

    def test_semantic_proposal_cannot_use_serialization_as_substantive_content(self):
        for text in ("Hello", "order"):
            session, proposal = self.semantic_fixture("json", "renamed-reference", "person@example.test")
            session.observations[0]["record"]["body"] = text
            proposal["supporting_quotes"][0]["quote"] = text
            with self.assertRaisesRegex(Rejected, "greeting or isolated keyword"):
                validate_assessment(session, proposal)


if __name__ == "__main__": unittest.main()

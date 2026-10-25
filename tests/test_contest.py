"""Independent final-path regressions, with no public reference inputs."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ghost_audit.contest import contest_intent, investigate_contest, validate_prediction, validate_csv
from ghost_audit.core import Rejected
from ghost_audit.public_index import PublicIndex
from test_audit import fixture, csv_file, CAPTURE


class ContestTests(unittest.TestCase):
    def test_language_scope_and_unknowns(self):
        for text in ("Quero excluir a minha conta e os dados pessoais.",
                     "계정 삭제를 요청합니다.",
                     "Veuillez supprimer mon compte."):
            self.assertIs(contest_intent(text)[0], True)
        for text in ("Please replace my phone number and keep the profile active.",
                     "Send a copy of my invoices; leave the account active."):
            self.assertIs(contest_intent(text)[0], False)
        for text in ("Texto desconhecido.", "Não excluir a conta.", "계정을 삭제하지 마세요."):
            self.assertIsNone(contest_intent(text)[0])

    def test_unknown_retention_does_not_erase_independent_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = fixture(root)
            # Add a policy-conditioned record to the same actual source.
            with (root / "evidence_files.csv").open() as stream:
                manifest = list(csv.DictReader(stream))
            source = root / manifest[0]["file_path"]
            with source.open("a") as stream:
                stream.write("CREATE TABLE security_audit_records (resource_id TEXT, user_id TEXT, email TEXT);\n"
                             "INSERT INTO security_audit_records VALUES ('independent-retained-note', 'user_target', 'old@example.test');\n")
            with (root / "deletion_rules.csv").open("a") as stream:
                stream.write("conditional-retain,SECURITY_AUDIT_LOG,Record is within the supplied retention period,RETAIN\n")
            report = investigate_contest(PublicIndex(root), request)
            self.assertEqual(report["output"]["deletion_status"], "INCOMPLETE")
            self.assertTrue(report["prediction_assessment"]["status_established"])
            self.assertFalse(report["prediction_assessment"]["plan_certified"])
            self.assertTrue(any(s["phase"] == "FINDING" for s in report["output"]["steps_json"]))
            self.assertFalse(any(s["resource_id"] == "independent-retained-note" for s in report["output"]["steps_json"]))

    def test_missing_state_never_becomes_complete_or_fabricated_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = fixture(root)
            request["email"] = "not-associated@example.test"
            report = investigate_contest(PublicIndex(root), request)
            self.assertEqual(report["output"]["deletion_status"], "INCOMPLETE")
            self.assertEqual(report["output"]["steps_json"], [])
            self.assertFalse(report["prediction_assessment"]["status_established"])
            report["output"]["deletion_status"] = "COMPLETE"
            with self.assertRaises(Rejected):
                validate_prediction(report)

    def test_final_path_citation_cutoff_and_future_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = fixture(root)
            report = investigate_contest(PublicIndex(root), request)
            validate_prediction(report)
            late = copy.deepcopy(report)
            for obs in late["observations"]:
                obs["capture_at"] = "2039-01-01T00:00:00Z"
            with self.assertRaises(Rejected):
                validate_prediction(late)
            future = copy.deepcopy(report)
            future["output"]["steps_json"][-1]["evidence_id"] = "unearned-citation"
            with self.assertRaises(Rejected):
                validate_prediction(future)

    def test_serialized_case_set_is_exact_sorted_and_unique(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.csv"
            path.write_text('case_id,deletion_status,steps_json\nb,INCOMPLETE,[]\na,INCOMPLETE,[]\n')
            with self.assertRaises(Rejected):
                validate_csv(path, [{"case_id": "a"}, {"case_id": "b"}])


if __name__ == "__main__":
    unittest.main()

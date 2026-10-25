"""Independent historical link graphs; no public answers or model calls."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ghost_audit.core import Investigation
from ghost_audit.public_index import PublicIndex, case_view
from ghost_audit.public_runner import investigate
from test_audit import fixture, csv_file, CAPTURE, CUTOFF, LATE


class HistoricalLinkTests(unittest.TestCase):
    def prepare(self, root, renamed=False):
        request = fixture(root)
        names = {"subject": "user_target", "old": "old@example.test", "new": "new@example.test",
                 "resource": "aggregate_target", "decoy": "aggregate_unrelated", "old_fid": "history_proof",
                 "new_fid": "current_proof", "old_path": "evidence/first.json", "new_path": "evidence/second.json"}
        if renamed:
            replacements = {"user_target": "person_omega", "old@example.test": "prior@fiction.test",
                            "new@example.test": "current@fiction.test"}
            for filename in ("user_identities.csv", "user_audit_log.csv"):
                path = root / filename
                text = path.read_text()
                for before, after in replacements.items(): text = text.replace(before, after)
                path.write_text(text)
            request["email"] = replacements[request["email"]]
            names = {"subject": "person_omega", "old": "prior@fiction.test", "new": "current@fiction.test",
                     "resource": "row_zeta", "decoy": "row_delta", "old_fid": "source_cyan", "new_fid": "source_magenta",
                     "old_path": "evidence/arbitrary_x.json", "new_path": "evidence/arbitrary_y.json"}
        rules = [{"rule_id": "profile_rule", "data_category": "USER_PROFILE", "condition": "Always", "required_action": "DELETE"},
                 {"rule_id": "export_rule", "data_category": "USER_EXPORT", "condition": "Always", "required_action": "DELETE"},
                 {"rule_id": "analytics_rule", "data_category": "ANALYTICS_PROFILE", "condition": "Record is still attributable to a user", "required_action": "ANONYMIZE"}]
        csv_file(root / "deletion_rules.csv", list(rules[0]), rules)
        return request, names

    def historical(self, root, renamed=False):
        request, names = self.prepare(root, renamed)
        earlier, later = "2026-01-31T00:00:00Z", "2026-02-02T00:00:00Z"
        old = {"resource_id": names["resource"], "user_id": None, "email": names["old"], "phone": None, "email_hash": None}
        anonymous = {**old, "email": None}
        for path, at, records in [(names["old_path"], earlier, [old]),
                                  (names["new_path"], later, [anonymous, {**anonymous, "resource_id": names["decoy"]}])]:
            (root / path).write_text(json.dumps({"captured_at": at, "source": "analytics_platform",
                "collection": "customer_analytics_reports", "records": records}))
        manifests = [{"file_id": names["old_fid"], "file_path": names["old_path"], "origin": "independent_snapshot", "captured_at": earlier},
                     {"file_id": names["new_fid"], "file_path": names["new_path"], "origin": "independent_snapshot", "captured_at": later}]
        csv_file(root / "evidence_files.csv", list(manifests[0]), manifests)
        index = PublicIndex(root)
        return investigate(index, request), names

    def test_anonymized_record_retains_a_proven_historical_association(self):
        with tempfile.TemporaryDirectory() as folder:
            result, names = self.historical(Path(folder))
        self.assertEqual(result["output"]["deletion_status"], "COMPLETE")
        self.assertEqual(result["facts"][0]["state"], "ANONYMIZED")
        self.assertEqual(result["output"]["steps_json"][0]["evidence_id"], names["new_fid"])
        edges = result["ledger"]["association_search"]["links"]
        self.assertTrue(any(e["link_type"] == "IDENTITY_CHANGE" for e in edges))
        self.assertTrue(any(e["link_type"] == "EXACT_IDENTIFIER" and e["proof"][0]["evidence_id"] == names["old_fid"] for e in edges))
        self.assertFalse(any(s["phase"] == "FINDING" for s in result["output"]["steps_json"]))

    def test_unrelated_anonymous_neighbor_is_not_associated(self):
        with tempfile.TemporaryDirectory() as folder:
            result, names = self.historical(Path(folder))
        self.assertEqual({s["resource_id"] for s in result["output"]["steps_json"]}, {names["resource"]})
        gaps = result["ledger"]["association_gaps"]
        self.assertTrue(any(g["resource"]["resource_id"] == names["decoy"] and g["subject_membership"] == "UNKNOWN" for g in gaps))

    def relationship(self, root, late=False):
        request, names = self.prepare(root)
        record = {"resource_id": "download_custom", "record_type": "USER_EXPORT", "system": "export_service",
                  "owner_email": names["old"], "result": "FOUND"}
        path = "evidence/neutral.json"
        (root / path).write_text(json.dumps({"exported_at": CAPTURE, "origin": "collector", "records": [record]}))
        sql = f"""-- Captured at: {CAPTURE}
CREATE TABLE customer_profiles_primary(resource_id TEXT,user_id TEXT,email TEXT,updated_at TEXT);
INSERT INTO customer_profiles_primary VALUES('profile_custom',NULL,NULL,'{CAPTURE}');
"""
        (root / "evidence/neutral.sql").write_text(sql)
        manifests = [{"file_id": "root_proof", "file_path": path, "origin": "collector", "captured_at": CAPTURE},
                     {"file_id": "target_proof", "file_path": "evidence/neutral.sql", "origin": "database", "captured_at": CAPTURE}]
        relation = {**record, "source_resource_id": "profile_custom", "source_system_id": "account_service"}
        if late:
            (root / "evidence/later.json").write_text(json.dumps({"exported_at": LATE, "origin": "collector", "records": [relation]}))
            manifests.append({"file_id": "late_relation", "file_path": "evidence/later.json", "origin": "collector", "captured_at": LATE})
        else:
            (root / path).write_text(json.dumps({"exported_at": CAPTURE, "origin": "collector", "records": [relation]}))
        csv_file(root / "evidence_files.csv", list(manifests[0]), manifests)
        return PublicIndex(root), request

    def test_explicit_relation_crosses_json_and_sql_with_direction_and_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            index, request = self.relationship(Path(folder))
            result = investigate(index, request)
        self.assertEqual({f["resource_id"] for f in result["facts"]}, {"download_custom", "profile_custom"})
        edges = [e for e in result["ledger"]["association_search"]["links"] if e["link_type"] == "EXPLICIT_RESOURCE_RELATIONSHIP"]
        self.assertTrue(edges)
        self.assertEqual(edges[0]["from"]["resource_id"], "profile_custom")
        self.assertEqual(edges[0]["to"]["resource_id"], "download_custom")
        self.assertEqual(edges[0]["relationship_type"], "SOURCE_OF")
        self.assertEqual(edges[0]["proof"][0]["evidence_id"], "root_proof")

    def test_late_relationship_is_not_used_even_to_link_an_earlier_observation(self):
        with tempfile.TemporaryDirectory() as folder:
            index, request = self.relationship(Path(folder), late=True)
            identity = index.identity(request["email"], CUTOFF)
            observations, candidates, known, _, search = case_view(index, identity, CUTOFF, return_search=True)
        self.assertNotIn(("account_service", "profile_custom"), known)
        self.assertNotIn("late_relation", candidates)
        self.assertFalse(any(e["link_type"] == "EXPLICIT_RESOURCE_RELATIONSHIP" for e in search["links"]))
        self.assertEqual({o["resource_id"] for o in observations}, {"download_custom"})

    def test_renamed_files_and_identifiers_have_equivalent_decisions(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            left, old = self.historical(Path(a))
            right, new = self.historical(Path(b), renamed=True)
        mapping = {value: new[key] for key, value in old.items()}
        def rename(value):
            if isinstance(value, list): return [rename(v) for v in value]
            if isinstance(value, dict): return {k: rename(v) for k, v in value.items()}
            return mapping.get(value, value)
        self.assertEqual(rename(left["output"]), right["output"])
        self.assertEqual(left["facts"][0]["state"], right["facts"][0]["state"])

    def test_search_exhaustion_distinguishes_failed_adapter_and_uninspected_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request, _ = self.prepare(root)
            (root / "evidence/broken.json").write_text('{ broken: "old@example.test"')
            manifest = {"file_id": "broken_source", "file_path": "evidence/broken.json", "origin": "fixture", "captured_at": CAPTURE}
            csv_file(root / "evidence_files.csv", list(manifest), [manifest])
            session = Investigation(PublicIndex(root), request)
            session.call("resolve_identity", {})
            search = session.ledger["association_search"]
            self.assertEqual(search["status"], "SUPPORTED_SEARCH_EXHAUSTED_WITH_ADAPTER_GAPS")
            self.assertEqual(search["adapter_gaps"][0]["status"], "ADAPTER_FAILURE")
            self.assertIn("broken_source", search["uninspected_candidate_sources"])


if __name__ == "__main__": unittest.main()

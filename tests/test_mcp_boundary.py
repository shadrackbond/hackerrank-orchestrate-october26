"""Process-level negative tests for the child model's only configured MCP server."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from test_audit import fixture
from ghost_audit.server import TOOLS
from ghost_audit.runtime import child_config
from ghost_audit.core import Limits


class MCPBoundaryTests(unittest.TestCase):
    def test_child_config_disables_other_tool_surfaces(self):
        config = child_config(Path('/tmp/code'), ["-m", "ghost_audit.server"],
                              Path('/tmp/child_instructions.txt'), Limits())
        for key in ("features.shell_tool", "features.apply_patch_freeform",
                    "features.apps", "features.multi_agent"):
            self.assertEqual(config[key], "false")
        self.assertEqual(config["web_search"], '"disabled"')
        self.assertEqual(config["mcp_servers.ghost.required"], "true")
        self.assertEqual({k.split(".")[1] for k in config if k.startswith("mcp_servers.")}, {"ghost"})
        self.assertEqual(json.loads(config["mcp_servers.ghost.args"]), ["-m", "ghost_audit.server"])

    def test_server_exposes_only_case_tools_and_denies_arbitrary_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset"
            dataset.mkdir()
            fixture(dataset)
            (dataset / "sample_output.csv").write_text("REFERENCE_SECRET_DO_NOT_READ\n")
            (root / "unrelated.txt").write_text("UNRELATED_SECRET_DO_NOT_READ\n")
            report = root / "report.json"
            code = Path(__file__).resolve().parents[1] / "code"
            env = {**os.environ, "PYTHONPATH": str(code)}
            command = [sys.executable, "-m", "ghost_audit.server", "--dataset", str(dataset),
                       "--requests", "sample_deletion_requests.csv", "--case", "custom_historical",
                       "--report", str(report), "--limits", json.dumps({})]
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, env=env)

            def call(number, method, params=None):
                proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": number, "method": method,
                                             "params": params or {}}) + "\n")
                proc.stdin.flush()
                return json.loads(proc.stdout.readline())

            try:
                listing = call(1, "tools/list")["result"]["tools"]
                self.assertEqual({t["name"] for t in listing}, {t["name"] for t in TOOLS})
                self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in listing))
                call(2, "tools/call", {"name": "resolve_identity", "arguments": {}})
                for number, name, args in (
                    (3, "read_file", {"path": str(dataset / "sample_output.csv")}),
                    (4, "exec_command", {"cmd": "cat ../README.md"}),
                    (5, "inspect_profile_snapshot", {"evidence_id": "sample_output.csv"}),
                    (6, "inspect_profile_snapshot", {"evidence_id": "../../README.md"}),
                    (7, "inspect_visual_evidence", {"evidence_id": "/etc/passwd"}),
                    (8, "search_evidence", {"path": str(dataset / "sample_output.csv")}),
                ):
                    response = call(number, "tools/call", {"name": name, "arguments": args})
                    self.assertTrue(response["result"]["isError"], (name, response))
                    self.assertNotIn("REFERENCE_SECRET_DO_NOT_READ", json.dumps(response))
                    self.assertNotIn("UNRELATED_SECRET_DO_NOT_READ", json.dumps(response))
                state = json.loads(report.read_text())
                self.assertIsNone(state["output"])
                self.assertEqual(state["ledger"]["eligible_sources_inspected"], [])
                self.assertFalse(any(e.get("accepted") for e in state["trace"] if e["tool"] != "resolve_identity"))
            finally:
                proc.stdin.close()
                proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()


if __name__ == "__main__":
    unittest.main()

"""Minimal stdio MCP server exposing only case-scoped read tools and validation."""
import argparse
import json
import sys
from pathlib import Path

from .core import Investigation, Limits, Rejected, rows
from .public_index import PublicIndex


def object_schema(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


STRING = {"type": "string"}
RESOURCE = object_schema({k: STRING for k in
    ("system_id", "resource_id", "state", "required_action", "evidence_id")})
QUOTE = object_schema({"source_location": STRING, "quote": STRING,
                       "role": {"type": "string", "enum": ["RESOURCE", "SUBJECT", "CONTEXT", "STATE", "TYPE", "OWNERSHIP"]}})
TOOLS = [
    {"name": "resolve_identity", "description": "Resolve request email to one subject and eligible historical aliases.",
     "inputSchema": object_schema({})},
    {"name": "search_evidence", "description": "Search indexed participant evidence with validated identifiers. Returns eligible candidates and deferred formats.",
     "inputSchema": object_schema({})},
    {"name": "inspect_evidence", "description": "Inspect one eligible identity/resource-linked evidence source using shared JSON, log, SQL, text, and cached visual adapters. Returns observations, deterministic policy resources, linked candidates, and unresolved gaps.",
     "inputSchema": object_schema({"evidence_id": STRING})},
    {"name": "inspect_visual_evidence", "description": "Read cached PDF/page or image/region transcription for an eligible candidate; state still requires a supported adapter.",
     "inputSchema": object_schema({"evidence_id": STRING})},
    {"name": "inspect_activity", "description": "Read eligible operational claims for discovered resources. Successful mutations do not prove state or active flows.",
     "inputSchema": object_schema({})},
    {"name": "read_semantic_evidence", "description": "Read exact source-located eligible artifact units after inspection. Returns correlated log excerpts or cached PDF page/line text; no file paths accepted.",
     "inputSchema": object_schema({"evidence_id": STRING})},
    {"name": "propose_semantic_assessment", "description": "Submit a narrow source-quoted support-context or visual-support-record interpretation. INSUFFICIENT preserves missing facts. Shares the proposal budget; cannot alter identity, retention, or arbitrary resource state.",
     "inputSchema": object_schema({"kind": {"type": "string", "enum": ["SUPPORT_SHARED_CONTEXT", "VISUAL_SUPPORT_RECORD"]},
         "evidence_id": STRING, "system_id": STRING, "resource_id": STRING,
         "conclusion": {"type": "string", "enum": ["CONFIRMED", "INSUFFICIENT"]},
         "supporting_quotes": {"type": "array", "items": QUOTE}, "explanation": STRING})},
    {"name": "propose_decision", "description": "Validate an intent and resource-treatment proposal; returns canonical output or rejection. No deletion is executed.",
     "inputSchema": object_schema({"authorized": {"type": "boolean"}, "request_quote": STRING,
         "deletion_status": {"type": "string", "enum": ["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"]},
         "resources": {"type": "array", "items": RESOURCE}})},
]
for tool in TOOLS:
    tool["annotations"] = {"readOnlyHint": True, "destructiveHint": False,
                           "idempotentHint": False, "openWorldHint": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--requests", choices=["sample_deletion_requests.csv", "deletion_requests.csv"], required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--limits", required=True)
    parser.add_argument("--visual-cache")
    parser.add_argument("--image-model")
    args = parser.parse_args()
    request = next(r for r in rows(Path(args.dataset) / args.requests) if r["case_id"] == args.case)
    investigation = Investigation(PublicIndex(args.dataset, args.visual_cache, args.image_model or "local-ocr"), request,
                                  Limits(**json.loads(args.limits)))
    report_path = Path(args.report)

    def persist():
        temp = report_path.with_suffix(".tmp")
        temp.write_text(json.dumps(investigation.report(), indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(report_path)

    persist()
    for line in sys.stdin:
        msg = json.loads(line)
        if "id" not in msg:
            continue
        try:
            method = msg["method"]
            if method == "initialize":
                result = {"protocolVersion": msg["params"]["protocolVersion"],
                          "capabilities": {"tools": {}}, "serverInfo": {"name": "ghost-audit", "version": "0.1.0"}}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = msg["params"]
                try:
                    value = investigation.call(params["name"], params.get("arguments", {}))
                    result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": False}
                except (Rejected, KeyError, TypeError, ValueError) as exc:
                    result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
                persist()
            elif method == "ping":
                result = {}
            else:
                raise ValueError("Unsupported MCP method")
            response = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32603, "message": str(exc)}}
        print(json.dumps(response), flush=True)
        if investigation.halt_reason:
            break


if __name__ == "__main__":
    main()

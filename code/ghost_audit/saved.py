"""Content-bound saved decisions, revalidated by replay through the shared tools.

These hashes detect stale/mismatched local artifacts; they are not signatures or
proof of provider billing. Original native traces remain the provenance source.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import uuid

from .core import Investigation, Limits, Rejected
from .contract import validate_report


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def binding(index, request, limits):
    code = Path(__file__).resolve().parent
    implementation = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(code.glob("*.py"))}
    implementation["main.py"] = hashlib.sha256((code.parent / "main.py").read_bytes()).hexdigest()
    return {"version": 1, "request": digest(request), "implementation": digest(implementation),
        "inputs": digest({"evidence": index.digest.hexdigest(), "manifest": index.manifest,
            "identity": index.identities, "history": index.history, "activity": index.activity,
            "rules": index.rules, "visual": index.visual_observations, "opaque": index.opaque}),
        "configuration": {"limits": asdict(limits), "image_model": index.image_model}}


def seal(run_dir, kind, usage=None, runtime_configuration=None):
    """Seal an existing tool report, including unresolved attempts; never infer usage."""
    run_dir = Path(run_dir)
    report = json.loads((run_dir / "investigation.json").read_text())
    if "binding" not in report: raise Rejected("Legacy report lacks an input/configuration binding")
    manifest = {"version": 1, "kind": kind, "case_id": report["case_id"], "binding": report["binding"],
        "invocation_id": str(uuid.uuid4()), "runtime_configuration": runtime_configuration,
        "report_sha256": hashlib.sha256((run_dir / "investigation.json").read_bytes()).hexdigest(),
        "usage": usage, "events_sha256": None}
    if kind == "MODEL_ASSISTED":
        events = run_dir / "model_events.jsonl"
        if not events.is_file() or usage is None: raise Rejected("Native model events and usage metadata required")
        manifest["events_sha256"] = hashlib.sha256(events.read_bytes()).hexdigest()
    temp = run_dir / "decision.tmp"
    temp.write_text(json.dumps(manifest, indent=2) + "\n")
    temp.replace(run_dir / "decision.json")
    return manifest


def load(path):
    path = Path(path)
    manifest = json.loads(path.read_text())
    if manifest.get("version") != 1 or manifest.get("kind") not in {
            "MODEL_ASSISTED", "DETERMINISTIC_DIAGNOSTIC_NOT_LIVE_AGENT", "SCRIPTED_REPLAY_TEST"}:
        raise Rejected("Unsupported saved decision version or provenance")
    report_path = path.parent / "investigation.json"
    if hashlib.sha256(report_path.read_bytes()).hexdigest() != manifest["report_sha256"]:
        raise Rejected("Saved investigation checksum mismatch")
    report = json.loads(report_path.read_text())
    if report.get("binding") != manifest["binding"] or report.get("case_id") != manifest["case_id"]:
        raise Rejected("Saved report and manifest binding disagree")
    if manifest["kind"] == "MODEL_ASSISTED":
        events = path.parent / "model_events.jsonl"
        if hashlib.sha256(events.read_bytes()).hexdigest() != manifest["events_sha256"]:
            raise Rejected("Native model trace checksum mismatch")
        usage_path = path.parent / "usage.json"
        if json.loads(usage_path.read_text()) != manifest["usage"]:
            raise Rejected("Saved usage metadata mismatch")
        config = manifest.get("runtime_configuration") or {}
        usage = manifest["usage"]
        if config.get("model") != usage.get("requested_model") or config.get("limits") != report.get("limits"):
            raise Rejected("Saved runtime configuration mismatch")
        native = [json.loads(line) for line in events.read_text().splitlines() if line.strip()]
        amounts = [e["usage"] for e in native if e.get("type") == "turn.completed" and "usage" in e]
        if bool(amounts) != bool(usage.get("usage_available")):
            raise Rejected("Native trace and usage availability disagree")
        if amounts:
            for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
                if sum(u.get(key, 0) for u in amounts) != usage["tokens"].get(key, 0):
                    raise Rejected("Measured usage disagrees with native trace")
    return manifest, report


def revalidate(index, request, manifest, report, expected_limits=None):
    if report.get("request") != request or manifest["case_id"] != request["case_id"]:
        raise Rejected("Saved decision does not match the complete current request")
    limits = Limits(**report["limits"])
    if min(asdict(limits).values()) <= 0 or (expected_limits is not None and limits != expected_limits):
        raise Rejected("Saved decision limits disagree with current import configuration")
    if binding(index, request, limits) != manifest["binding"]:
        raise Rejected("Saved decision is stale: evidence, policy, configuration or implementation changed")
    if not report.get("output") or report.get("halt_reason"):
        raise Rejected("Saved investigation is unresolved or exhausted")
    if manifest["kind"] == "MODEL_ASSISTED" and manifest["usage"].get("outcome") != "finished":
        raise Rejected("Saved runtime did not finish successfully")
    session = Investigation(index, request, limits)
    trace = report.get("trace", [])
    if not trace or len(trace) > limits.tool_calls: raise Rejected("Saved tool trace is absent or over budget")
    for entry in trace:
        try:
            session.call(entry["tool"], entry["arguments"])
            accepted = True
        except Rejected:
            accepted = False
        if accepted != entry.get("accepted"):
            raise Rejected("Saved tool interaction no longer has its recorded validation outcome")
    rebuilt = session.report()
    if rebuilt["output"] != report["output"]: raise Rejected("Saved output differs from current evidence/policy compilation")
    validate_report(rebuilt)
    rebuilt["execution_kind"] = manifest["kind"]
    rebuilt["decision_provenance"] = {"kind": manifest["kind"], "invocation_id": manifest["invocation_id"],
                                      "validation": "REPLAYED_CURRENT_ENGINE", "new_model_calls": 0}
    return rebuilt


def aggregate_usage(manifests):
    unique = {m["invocation_id"]: m for m in manifests if m["kind"] == "MODEL_ASSISTED"}
    models = {}
    unknown = 0
    for manifest in unique.values():
        usage = manifest["usage"]
        key = usage.get("provider", "unreported") + "/" + usage.get("requested_model", "unreported")
        row = models.setdefault(key, {"runtime_invocations": 0, "input_tokens": 0,
            "cached_input_tokens": 0, "uncached_input_tokens": 0, "output_tokens": 0,
            "wall_seconds": 0, "unknown_usage_invocations": 0})
        row["runtime_invocations"] += 1
        if isinstance(usage.get("wall_seconds"), (int, float)): row["wall_seconds"] += usage["wall_seconds"]
        tokens = usage.get("tokens") if usage.get("usage_available") else None
        if tokens is None:
            unknown += 1; row["unknown_usage_invocations"] += 1
            continue
        for key in ("input_tokens", "cached_input_tokens", "output_tokens"): row[key] += tokens.get(key, 0)
        row["uncached_input_tokens"] += tokens.get("input_tokens", 0) - tokens.get("cached_input_tokens", 0)
    return {"scope": "PREVIOUS_SAVED_INVOCATIONS_INCLUDING_REJECTED_OR_UNRESOLVED_IMPORTS", "new_model_calls": 0,
        "saved_runtime_invocations": len(unique), "known_usage_subtotals_by_model": models,
        "unknown_usage_invocations": unknown, "totals_complete": unknown == 0, "estimated_cost": None}

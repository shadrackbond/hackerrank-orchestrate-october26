"""Bounded MCP presentation; the complete evidence ledger remains in saved reports."""
import copy


def compact(value, offset=0, limit=20):
    value = copy.deepcopy(value)
    paging = {}
    for key in ("observations", "units", "contextual_evidence", "claims_not_state_proof"):
        if isinstance(value.get(key), list):
            values = value[key]
            value[key] = values[offset:offset+limit]
            paging[key] = {"total": len(values), "offset": offset,
                           "next_offset": offset+limit if offset+limit < len(values) else None}
    if "resource_links" in value:
        value["resource_link_count"] = len(value.pop("resource_links"))
    for obs in value.get("observations", []):
        proof = obs.pop("trace_proof", [])
        if proof: obs["trace_source_locations"] = [p["source_location"] for p in proof]
    if "policy_rules" in value and value.get("observations"):
        categories = {o["category"] for o in value["observations"]}
        value["policy_rules"] = [r for r in value["policy_rules"] if r["data_category"] in categories]
    if paging: value["pagination"] = paging
    return value

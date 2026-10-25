"""Participant-evidence normalization for public-case investigation.

This module has no reference-answer path. Every observation retains the manifest
file ID, source location, capture time, observation time, and a concrete scope.
"""
from __future__ import annotations

import json
import re
import shlex
import sqlite3
from collections import defaultdict
from pathlib import Path

from .core import EvidenceIndex, Rejected, eligible, timestamp


CATEGORIES = {
    "customer_profiles": "USER_PROFILE", "profile_lookups": "USER_PROFILE",
    "customer_search_documents": "SEARCH_INDEX_ENTRY", "index_queries": "SEARCH_INDEX_ENTRY",
    "customer_analytics_reports": "ANALYTICS_PROFILE", "customer_analytics_profiles": "ANALYTICS_PROFILE",
    "profiles": "ANALYTICS_PROFILE", "support_records": "SUPPORT_MESSAGE",
    "support_conversations": "SUPPORT_MESSAGE", "tickets": "SUPPORT_MESSAGE",
    "ticket_attachments": "SUPPORT_ATTACHMENT", "customer_export_jobs": "USER_EXPORT",
    "customer_exports": "USER_EXPORT", "exports": "USER_EXPORT",
    "connector_configurations": "DATA_FLOW", "connector_subscriptions": "DATA_FLOW",
    "connectors": "DATA_FLOW", "backup_catalog": "BACKUP_ARCHIVE",
    "backup_restore_entries": "BACKUP_ARCHIVE", "restore_entries": "BACKUP_ARCHIVE",
    "security_audit_events": "SECURITY_AUDIT_LOG", "security_audit_records": "SECURITY_AUDIT_LOG",
    "audit_records": "SECURITY_AUDIT_LOG", "retained_order_records": "LEGAL_HOLD_RECORD",
    "deleted_customer_references": "ACCOUNT_TOMBSTONE",
}
TABLE_SYSTEM = {
    "customer_profiles": "account_service", "customer_search_documents": "search_service",
    "customer_analytics_profiles": "analytics_platform", "support_records": "support_platform",
    "customer_exports": "export_service", "connector_subscriptions": "integration_service",
    "backup_restore_entries": "backup_service", "security_audit_records": "security_service",
}
DIRECT_KEYS = {"user_id", "customer_reference", "subject_reference"}
IDENTIFIER_KEYS = {"email", "customer_email", "owner_email", "requester_email", "phone",
                   "owner_phone", "requester_phone", "email_hash", "lookup_key", "match_key",
                   "subject_key", "correlation_key", "lookup_value"}


def _record_state(row, category):
    if row.get("result") in {"ANONYMIZED", "REDACTED", "BLOCKED", "DISABLED", "ACTIVE"}:
        return row["result"]
    if row.get("result") == "IDENTIFIABLE":
        return "PRESENT"
    if row.get("result") in {"NOT_FOUND", "ABSENT", "DELETED"}:
        return "ABSENT"
    if row.get("result") in {"FOUND", "PRESENT"}:
        return "PRESENT"
    if row.get("status_code") in {404, "404"} or row.get("rows") in {0, "0"}:
        return "ABSENT"
    if category == "SEARCH_INDEX_ENTRY" and row.get("result") in {"miss", "no_hit"}:
        return "ABSENT"
    if category == "SEARCH_INDEX_ENTRY" and row.get("hits", {}).get("total") == 0:
        return "ABSENT"
    if category == "DATA_FLOW":
        return "ACTIVE" if row.get("enabled") in {True, 1, "true", "1"} else "DISABLED"
    if category == "BACKUP_ARCHIVE":
        if "eligible" in row or "deletion_block" in row:
            return "ACTIVE" if row.get("eligible") in {True, 1, "true", "1"} and \
                row.get("deletion_block") in {False, 0, "false", "0"} else "BLOCKED"
        return "ACTIVE" if row.get("restore_allowed") in {True, 1, "true", "1"} else "BLOCKED"
    if category == "ANALYTICS_PROFILE" and not any(row.get(k) for k in
        ("user_id", "customer_reference", "email", "phone", "email_hash")):
        return "ANONYMIZED"
    if category == "SUPPORT_MESSAGE" and (row.get("message_excerpt") or row.get("message_text")) \
            and not any(row.get(k) for k in ("requester_name", "requester_email", "requester_phone")):
        return "REDACTED"
    if category == "ACCOUNT_TOMBSTONE" and not any(row.get(k) for k in
        ("name", "full_name", "email", "phone", "email_hash")):
        return "REDACTED"
    return "PRESENT"


def _obs(meta, location, scope, system, category, record, observed=None, state=None):
    at = observed or meta["captured_at"]
    if not eligible(at, meta["captured_at"]):
        raise Rejected("Observation after source capture: " + meta["file_id"])
    return {"evidence_id": meta["file_id"], "capture_at": meta["captured_at"],
            "observed_at": at, "source_location": meta["file_path"] + "#" + location,
            "scope": scope, "system_id": system, "category": category,
            "resource_id": str(record.get("resource_id", "")), "state": state or _record_state(record, category),
            "record": record}


def _json_rows(obj, meta):
    out, scopes = [], set()
    if "snapshots" in obj:
        groups = [(s["data_store"], s["collection"], s["records"], s.get("captured_at", meta["captured_at"]),
                   f"snapshots/{i}") for i, s in enumerate(obj["snapshots"])]
    elif "service_exports" in obj:
        groups = [(service, coll, records, obj.get("exported_at", meta["captured_at"]),
                   f"service_exports/{service}/{coll}")
                  for service, collections in obj["service_exports"].items()
                  for coll, records in collections.items()]
    else:
        groups = [(obj.get("source", obj.get("origin", "")), obj.get("collection", "records"),
                   obj["records"], obj.get("captured_at", obj.get("exported_at", meta["captured_at"])), "records")]
    for system, collection, records, at, location in groups:
        if not eligible(at, meta["captured_at"]):
            raise Rejected("JSON snapshot after manifest capture")
        scope = f"{meta['file_id']}:{location}"
        scopes.add((scope, system, collection, at))
        for n, row in enumerate(records):
            system_id = row.get("system", system)
            category = row.get("record_type") or CATEGORIES.get(collection)
            if not category:
                continue
            observed = row.get("observed_at", row.get("recorded_at", at))
            if not eligible(observed, meta["captured_at"]):
                continue
            if isinstance(row.get("profile"), dict):
                row = {**row, **row["profile"]}
            if category == "SEARCH_INDEX_ENTRY" and isinstance(row.get("hits"), dict):
                for j, hit in enumerate(row["hits"].get("documents", [])):
                    combined = {**row, **hit, "resource_id": row.get("resource_id", hit.get("resource_id", ""))}
                    out.append(_obs(meta, f"{location}/{n}/hits/{j}", scope, system_id, category,
                                    combined, observed, "PRESENT"))
                if row["hits"].get("total") == 0:
                    out.append(_obs(meta, f"{location}/{n}", scope, system_id, category,
                                    row, observed, "ABSENT"))
            else:
                out.append(_obs(meta, f"{location}/{n}", scope, system_id, category, row, observed))
    return out, scopes


def _handover_rows(text, meta):
    out = []
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"- (\S+) \| (\w+) \| ([\w_]+) \| (\w+) \| (\w+) \| (.+)", line)
        if not match or not eligible(match[1], meta["captured_at"]): continue
        at, system, rid, category, state, subject = match.groups()
        record = {"resource_id": rid, "record_type": category, "result": state,
                  "subject_reference": subject.strip()}
        out.append(_obs(meta, f"line={number}", f"{meta['file_id']}:handover:{system}",
                        system, category, record, at))
    return out, set()


def _sql_rows(text, meta):
    marker = re.search(r"-- Captured at: (\S+)", text)
    if marker and marker[1] != meta["captured_at"]:
        raise Rejected("Inconsistent SQL snapshot capture")
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY
                      if action in {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH} else sqlite3.SQLITE_OK)
    db.set_progress_handler(lambda: 1 if __import__("time").monotonic() > _sql_rows.deadline else 0, 1000)
    try:
        _sql_rows.deadline = __import__("time").monotonic() + 5
        db.executescript(text)
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        scopes = set()
        scope_times = ({r["origin_system"]: r["captured_at"]
                        for r in db.execute("SELECT * FROM snapshot_scope")}
                       if "snapshot_scope" in tables else {})
        out = []
        for system, at in scope_times.items():
            if eligible(at, meta["captured_at"]):
                scopes.add((f"{meta['file_id']}:snapshot_scope", system, "__scope__", at))
        for table in tables:
            if table == "snapshot_scope":
                continue
            records = [dict(r) for r in db.execute('SELECT * FROM "' + table + '"')]
            if table.startswith("customer_data_"):
                for n, row in enumerate(records):
                    record = json.loads(row["record_json"])
                    category = CATEGORIES.get(row["collection_name"])
                    if category:
                        scope = f"{meta['file_id']}:{table}:{row['origin_system']}:{row['collection_name']}"
                        scopes.add((scope, row["origin_system"], row["collection_name"], meta["captured_at"]))
                        out.append(_obs(meta, f"table={table},row={n}", scope, row["origin_system"],
                                        category, record, meta["captured_at"]))
                continue
            base = re.sub(r"_(primary|regional_replica|reporting_replica|failover_replica|read_replica)$", "", table)
            system = TABLE_SYSTEM.get(base, "search_service" if base == "search_documents" else "account_service")
            category = CATEGORIES.get(base, "SEARCH_INDEX_ENTRY" if base == "search_documents" else "USER_PROFILE")
            at = scope_times.get(system, meta["captured_at"])
            scope = f"{meta['file_id']}:{table}"
            scopes.add((scope, system, base, at))
            for n, row in enumerate(records):
                out.append(_obs(meta, f"table={table},row={n}", scope, system, category, row, at))
        return out, scopes
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        raise Rejected("SQL extraction failed: " + str(exc)) from exc
    finally:
        db.close()


def _log_rows(text, meta):
    traces = defaultdict(list)
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        match = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)", line)
        if not match or not eligible(match[1], meta["captured_at"]):
            continue
        payload = {}
        brace = line.find("{")
        if brace >= 0:
            try: payload = json.loads(line[brace:])
            except json.JSONDecodeError: pass
        if not payload:
            message = re.search(r'\bmessage="(.*)"$', line)
            segment = bytes(message[1], "utf-8").decode("unicode_escape") if message else line
            try:
                payload = dict(part.split("=", 1) for part in shlex.split(segment) if "=" in part)
            except ValueError:
                payload = {}
        trace = payload.get("trace_id") or payload.get("requestId")
        if not trace:
            found = re.search(r"\b(?:tr|rb)-[\w-]+", line)
            trace = found[0] if found else ""
        if not payload.get("event"):
            found = re.search(r"\b([a-z_]+(?:started|completed|evaluated|loaded|scan|read)):", line)
            if found: payload["event"] = found[1]
        if not payload.get("service"):
            found = re.search(r"\b(?:service|function)=([\w_]+)", line)
            if found: payload["service"] = found[1]
        traces[trace].append((n, match[1], payload, line))
    for trace, lines in traces.items():
        for n, at, row, line in lines:
            event = row.get("event", "")
            if not row.get("resource_id") or not (event.endswith("completed") or event in
                    {"record_lookup", "message_pii_scan", "attachment_pii_scan", "connector_heartbeat",
                     "message_read", "analytics_profile_read", "contact_lookup_completed",
                     "restore_candidate_evaluated", "connector_config_loaded"}):
                continue
            links = {k: v for _, link_at, payload, _ in lines if eligible(link_at, at)
                     for k, v in payload.items() if k in
                     IDENTIFIER_KEYS | {"subject_ref", "customer_reference"}
                     and v not in {"null", "None"}}
            joined = {**links, **row}
            system = row.get("system", row.get("service", ""))
            category = row.get("record_type") or {
                "account_service": "USER_PROFILE", "profile_service": "USER_PROFILE",
                "search_service": "SEARCH_INDEX_ENTRY", "analytics_platform": "ANALYTICS_PROFILE",
                "support_platform": "SUPPORT_MESSAGE", "support_replica": "SUPPORT_MESSAGE",
                "integration_service": "DATA_FLOW", "backup_service": "BACKUP_ARCHIVE",
                "security_service": "SECURITY_AUDIT_LOG", "export_service": "USER_EXPORT",
            }.get(system)
            if event == "contact_lookup_completed" and system == "analytics_platform":
                category = "SECONDARY_IDENTIFIER"
            if not category:
                continue
            if category == "SEARCH_INDEX_ENTRY" and row.get("result") in {"hit", "hits"}:
                state = "PRESENT"
            elif category == "SEARCH_INDEX_ENTRY" and row.get("result") in {"miss", "no_hit"}:
                state = "ABSENT"
            else: state = None
            scope = f"{meta['file_id']}:log:{system}:{trace or n}"
            out.append(_obs(meta, f"line={n},trace={trace}", scope, system, category, joined, at, state))
    return out, set()


def _visual_rows(index, meta):
    """Only parse labelled resource facts; mere OCR search hits are not state proof."""
    segments = index.visual_observations.get(meta["file_id"], [])
    text = "\n".join(s["text"] for s in segments)
    if not text: return [], set()
    if "legal_retention_register" in meta["file_path"]:
        out = []
        for n, segment in enumerate(segments):
            match = re.search(r"(ORD-\d+)\s*\|\s*(user_\d+)\s*\|.*?Retain until\s+(\d\d?\s+\w+\s+\d{4})",
                              segment["text"])
            if not match: continue
            from datetime import datetime, timezone
            until = datetime.strptime(match[3], "%d %B %Y").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            record = {"resource_id": match[1], "subject_reference": match[2],
                      "retained_until": until, "retention_reason": "disputed order or tax record"}
            out.append(_obs(meta, segment["source_location"].split("#")[-1],
                            f"{meta['file_id']}:legal-register", "legal_service", "LEGAL_HOLD_RECORD", record))
        return out, set()
    # OCR is often noisy. A missing explicit status stays an investigation gap.
    system, category = None, None
    lower = meta["file_path"].lower()
    for word, pair in {
        "account_admin": ("account_service", "USER_PROFILE"),
        "search_index": ("search_service", "SEARCH_INDEX_ENTRY"),
        "connector_management": ("integration_service", "DATA_FLOW"),
        "analytics_profile": ("analytics_platform", "ANALYTICS_PROFILE"),
        "customer_export": ("export_service", "USER_EXPORT"),
        "support_ticket": ("support_platform", "SUPPORT_MESSAGE"),
        "backup_restore": ("backup_service", "BACKUP_ARCHIVE"),
        "security_audit": ("security_service", "SECURITY_AUDIT_LOG"),
        "deleted_account": ("account_service", "ACCOUNT_TOMBSTONE"),
        "object_storage": ("support_platform", "SUPPORT_ATTACHMENT"),
        "marketing_profile": ("marketing_service", "MARKETING_PROFILE"),
    }.items():
        if word in lower: system, category = pair; break
    if not system: return [], set()
    ids = list(dict.fromkeys(re.findall(r"\b(?:account|search|data_flow|analytics|export|support|backup|audit_record|marketing)_\d+\b", text)))
    if len(ids) != 1: return [], set()
    row = {"resource_id": ids[0], "visual_text": text}
    if category == "DATA_FLOW":
        if re.search(r"\b(?:enabled|active|continuous)\b", text, re.I): state = "ACTIVE"
        elif re.search(r"\bdisabled\b", text, re.I): state = "DISABLED"
        else: return [], set()
    elif category == "BACKUP_ARCHIVE":
        if re.search(r"restore.{0,30}(?:allowed|enabled)", text, re.I): state = "ACTIVE"
        elif re.search(r"restore.{0,30}blocked", text, re.I): state = "BLOCKED"
        else: return [], set()
    elif category == "ACCOUNT_TOMBSTONE":
        state = "PRESENT" if re.search(r"\b(?:email|phone|name)\b", text, re.I) else "REDACTED"
    else: state = "PRESENT"
    return [_obs(meta, "visual=labelled-resource", f"{meta['file_id']}:visual", system,
                 category, row, meta["captured_at"], state)], set()


class PublicIndex(EvidenceIndex):
    def __init__(self, dataset, visual_cache):
        super().__init__(dataset, visual_cache, "local-ocr")
        self.observations, self.scopes, self.adapter_gaps = [], set(), []
        for fid, meta in sorted(self.manifest.items()):
            suffix = Path(meta["file_path"]).suffix.lower()
            try:
                if suffix == ".json": found, scopes = _json_rows(json.loads(self.contents[fid]), meta)
                elif suffix == ".sql": found, scopes = _sql_rows(self.contents[fid], meta)
                elif suffix == ".log": found, scopes = _log_rows(self.contents[fid], meta)
                elif suffix == ".txt": found, scopes = _handover_rows(self.contents[fid], meta)
                elif suffix in {".png", ".pdf"}: found, scopes = _visual_rows(self, meta)
                else:
                    self.adapter_gaps.append(f"Unsupported format: {fid}:{suffix}")
                    continue
                self.observations.extend(found)
                self.scopes.update(scopes)
                if suffix in {".png", ".pdf"} and not found:
                    self.adapter_gaps.append("Visual assessment unresolved: " + fid)
            except (Rejected, ValueError, KeyError, TypeError) as exc:
                self.adapter_gaps.append(f"Adapter rejected {fid}: {exc}")
        self.by_resource = defaultdict(list)
        for obs in self.observations:
            if obs["resource_id"]: self.by_resource[obs["resource_id"]].append(obs)


def linked(record, identity):
    """A conflicting stable reference vetoes a coincidental alias match."""
    uid = identity["user_id"]
    aliases = {(a["field"], a["value"].casefold()) for a in identity["aliases"]}
    direct = []
    for key in DIRECT_KEYS:
        value = record.get(key)
        if value and str(value).startswith("user_"): direct.append(str(value))
    if direct:
        return all(value == uid for value in direct)
    for key, value in record.items():
        if value is None or isinstance(value, (dict, list)): continue
        field = "email_hash" if "hash" in key or re.fullmatch(r"[0-9a-fA-F]{64}", str(value)) else "phone" if "phone" in key else \
            "email" if "email" in key or key in IDENTIFIER_KEYS or key == "subject_reference" and "@" in str(value) else None
        if field and (field, str(value).casefold()) in aliases: return True
    for key in ("document", "profile", "subject_selector"):
        nested = record.get(key)
        if isinstance(nested, dict) and linked(nested, identity): return True
        if isinstance(nested, str) and nested.casefold() in {value for field, value in aliases
                                                              if field in {"email", "email_hash", "user_id"}}:
            return True
    return False

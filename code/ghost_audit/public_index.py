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

from .core import EvidenceIndex, Rejected, eligible, timestamp, tokens


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
    "audit_records": "SECURITY_AUDIT_LOG",
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
                   "subject_key", "subject_ref", "correlation_key", "lookup_value", "query"}


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
        flag = row.get("enabled")
        if flag in {True, 1, "true", "1"}: return "ACTIVE"
        if flag in {False, 0, "false", "0"}: return "DISABLED"
        return "UNKNOWN"
    if category == "BACKUP_ARCHIVE":
        truth, falsehood = {True, 1, "true", "1"}, {False, 0, "false", "0"}
        if "eligible" in row or "deletion_block" in row:
            if row.get("deletion_block") in truth or row.get("eligible") in falsehood: return "BLOCKED"
            if row.get("eligible") in truth and row.get("deletion_block") in falsehood: return "ACTIVE"
            return "UNKNOWN"
        if row.get("restore_allowed") in truth: return "ACTIVE"
        if row.get("restore_allowed") in falsehood: return "BLOCKED"
        return "UNKNOWN"
    if category == "ANALYTICS_PROFILE" and not any(k in row for k in
            ("user_id", "customer_reference", "email", "phone", "email_hash")):
        return "UNKNOWN"
    if category == "ANALYTICS_PROFILE" and not any(row.get(k) for k in
        ("user_id", "customer_reference", "email", "phone", "email_hash")):
        return "ANONYMIZED"
    if category == "SUPPORT_MESSAGE" and all(k in row for k in
            ("requester_name", "requester_email", "requester_phone")) and (row.get("message_excerpt") or row.get("message_text")) \
            and not any(row.get(k) for k in ("requester_name", "requester_email", "requester_phone")):
        return "REDACTED"
    if category == "ACCOUNT_TOMBSTONE":
        direct = {"email", "phone", "email_hash"}
        if not direct <= row.keys() or not {"name", "full_name"} & row.keys():
            return "UNKNOWN"
        return "PRESENT" if any(row.get(k) for k in (*direct, "name", "full_name")) else "REDACTED"
    return "PRESENT"


def _obs(meta, location, scope, system, category, record, observed=None, state=None):
    at = observed or meta["captured_at"]
    if not eligible(at, meta["captured_at"]):
        raise Rejected("Observation after source capture: " + meta["file_id"])
    return {"evidence_id": meta["file_id"], "capture_at": meta["captured_at"],
            "observed_at": at, "source_location": meta["file_path"] + "#" + location,
            "scope": scope, "system_id": system, "category": category,
            "source_origin": meta.get("origin", ""),
            "resource_id": str(record.get("resource_id") or ""), "state": state or _record_state(record, category),
            "record": record}


def legal_hold_semantics(record):
    """Dates and order/dispute references alone do not establish a legal hold."""
    return (record.get("record_type") == "LEGAL_HOLD_RECORD"
            or record.get("data_category") == "LEGAL_HOLD_RECORD"
            or isinstance(record.get("legal_hold_active"), bool)
            or str(record.get("hold_type", "")).casefold() == "legal")


def _context(meta, location, record, observed=None):
    return {"evidence_role": "CONTEXT", "evidence_id": meta["file_id"],
            "capture_at": meta["captured_at"], "observed_at": observed or meta["captured_at"],
            "source_location": meta["file_path"] + "#" + location,
            "source_origin": meta.get("origin", ""), "record": record}


def _category(collection, record):
    if collection == "retained_order_records":
        return "LEGAL_HOLD_RECORD" if legal_hold_semantics(record) else None
    return record.get("record_type") or CATEGORIES.get(collection)


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
            category = _category(collection, row)
            observed = row.get("observed_at", row.get("recorded_at", at))
            if not eligible(observed, meta["captured_at"]):
                continue
            if not category:
                if collection == "retained_order_records":
                    out.append(_context(meta, f"{location}/{n}", row, observed))
                continue
            identity_basis = "explicit resource system or source label"
            # This collection has the same owner/file schema under export_service
            # in supplied service snapshots. Source/exporter names are provenance.
            if collection == "customer_export_jobs" and category == "USER_EXPORT" and \
                    {"owner_email", "file_name", "created_at", "expires_at", "download_available"} <= row.keys() and \
                    "system" not in row and "snapshots" not in obj and "service_exports" not in obj:
                system_id = "export_service"
                identity_basis = "customer_export_jobs owner/file/download schema"
            if isinstance(row.get("profile"), dict):
                row = {**row, **row["profile"]}
            if category == "SEARCH_INDEX_ENTRY" and isinstance(row.get("hits"), dict):
                for j, hit in enumerate(row["hits"].get("documents", [])):
                    combined = {**row, **hit, "resource_id": hit.get("resource_id", ""),
                                "lookup_query": row.get("query")}
                    # A query is a selector, not ownership proof for each returned hit.
                    combined.pop("query", None)
                    combined.pop("hits", None)
                    out.append(_obs(meta, f"{location}/{n}/hits/{j}", scope, system_id, category,
                                    combined, observed, "PRESENT"))
                if row["hits"].get("total") == 0:
                    out.append(_obs(meta, f"{location}/{n}", scope, system_id, category,
                                    row, observed, "ABSENT"))
            else:
                out.append(_obs(meta, f"{location}/{n}", scope, system_id, category, row, observed))
            for observation in out:
                if observation.get("source_location", "").startswith(meta["file_path"] + f"#{location}/{n}"):
                    observation["document_source"] = obj.get("source", obj.get("origin", ""))
                    observation["source_system_label"] = system
                    observation["system_identity_basis"] = identity_basis
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


def _sql_rows(text, meta, inventories=None):
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
            records = [dict(r) for r in db.execute('SELECT * FROM "' + table.replace('"', '""') + '"')]
            if table.startswith("customer_data_"):
                if inventories is not None:
                    inventories.append({"evidence_id": meta["file_id"], "system_id": "*", "category": "*",
                        "table": table, "captured_at": meta["captured_at"], "meta": meta,
                        "resources": {(r["origin_system"], r["resource_id"]) for r in records}})
                for n, row in enumerate(records):
                    record = json.loads(row["record_json"])
                    category = _category(row["collection_name"], record)
                    if category:
                        scope = f"{meta['file_id']}:{table}:{row['origin_system']}:{row['collection_name']}"
                        scopes.add((scope, row["origin_system"], row["collection_name"], meta["captured_at"]))
                        out.append(_obs(meta, f"table={table},row={n}", scope, row["origin_system"],
                                        category, record, meta["captured_at"]))
                    elif row["collection_name"] == "retained_order_records":
                        out.append(_context(meta, f"table={table},row={n}", record))
                continue
            base = re.sub(r"_(primary|regional_replica|reporting_replica|failover_replica|read_replica)$", "", table)
            if base not in TABLE_SYSTEM and base != "search_documents":
                raise Rejected("Unsupported SQL table schema: " + table)
            system = TABLE_SYSTEM.get(base, "search_service")
            category = CATEGORIES.get(base, "SEARCH_INDEX_ENTRY")
            at = scope_times.get(system, meta["captured_at"])
            scope = f"{meta['file_id']}:{table}"
            scopes.add((scope, system, base, at))
            if inventories is not None:
                inventories.append({"evidence_id": meta["file_id"], "system_id": system, "category": category,
                    "table": table, "captured_at": at, "meta": meta,
                    "resources": {(system, r["resource_id"]) for r in records}})
            for n, row in enumerate(records):
                if row.get("updated_at") and not eligible(row["updated_at"], at):
                    raise Rejected("Row update is later than snapshot capture")
                out.append(_obs(meta, f"table={table},row={n}", scope, system, category, row, at))
        return out, scopes
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        raise Rejected("SQL extraction failed: " + str(exc)) from exc
    finally:
        db.close()


def _log_rows(text, meta, link_records=None):
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
        # Supplied syslog, bracketed application, and pipe-delimited envelopes
        # carry the service/event outside the key-value payload.
        envelope = re.match(r"^\S+\s+<\d+>1\s+\S+\s+(\w+)\s+((?:tr|rb)-[\w-]+)", line)
        bracket = re.match(r"^\S+\s+\[\w+\]\s+\[(\w+)\]\s+\[((?:tr|rb)-[\w-]+)\]\s+(\w+):", line)
        pipe = line.split(" | ")
        if envelope or bracket:
            match_env = envelope or bracket
            payload.setdefault("service", match_env[1])
            trace = trace or match_env[2]
            if bracket: payload.setdefault("event", bracket[3])
        elif len(pipe) >= 6:
            payload.setdefault("service", pipe[2].strip())
            payload.setdefault("event", pipe[4].strip())
            trace = trace or pipe[3].strip()
        payload = {key: None if isinstance(value, str) and value in {"null", "None", "NULL"} else value
                   for key, value in payload.items()}
        traces[trace or f"line-{n}"].append((n, match[1], payload, line))
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
            link_values = defaultdict(set)
            for _, link_at, payload, _ in lines:
                if eligible(link_at, at):
                    for key in IDENTIFIER_KEYS:
                        if payload.get(key) not in {None, "null", "None"}:
                            link_values[key].add(str(payload[key]).casefold())
            if any(len(values) > 1 for values in link_values.values()):
                joined["_ambiguous_identity_trace"] = True
            trace_proof = [{"evidence_id": meta["file_id"], "captured_at": meta["captured_at"],
                            "observed_at": link_at, "source_location": meta["file_path"] + f"#line={line_no},trace={trace}",
                            "event": payload.get("event", ""), "fields": payload}
                           for line_no, link_at, payload, _ in lines if eligible(link_at, at)]
            system = row.get("system", row.get("service", ""))
            category = row.get("record_type") or {
                "account_service": "USER_PROFILE", "profile_service": "USER_PROFILE",
                "search_service": "SEARCH_INDEX_ENTRY", "analytics_platform": "ANALYTICS_PROFILE",

                "integration_service": "DATA_FLOW", "backup_service": "BACKUP_ARCHIVE",
                "security_service": "SECURITY_AUDIT_LOG", "export_service": "USER_EXPORT",
            }.get(system)
            if not row.get("record_type"):
                source_labels = {str(p["fields"].get("source", "")).casefold() for p in trace_proof}
                if event in {"contact_query_completed", "contact_lookup_completed"} and (
                        system == "analytics_platform" or any("contact_index" in label for label in source_labels)):
                    category = "SECONDARY_IDENTIFIER"
                elif system in {"support_platform", "support_replica"} and (event in {
                        "message_read", "message_pii_scan"} or any(k in row for k in ("message_text", "message_excerpt", "body"))):
                    category = "SUPPORT_MESSAGE"
                elif system in {"support_platform", "support_replica"} and event == "attachment_pii_scan":
                    category = "SUPPORT_ATTACHMENT"
            source_system = system
            # The manifest identifies the supplying service; replica identity is kept as scope.
            if system == "support_replica" and meta.get("origin") == "support_platform":
                system = meta["origin"]
            if link_records is not None:
                link_records.append({"evidence_id": meta["file_id"], "capture_at": meta["captured_at"],
                    "observed_at": at, "source_location": meta["file_path"] + f"#line={n},trace={trace}",
                    "system_id": system, "resource_id": str(joined.get("resource_id") or ""),
                    "category": category, "record": joined, "trace_proof": trace_proof})
            if not category:
                continue
            if category == "SEARCH_INDEX_ENTRY" and row.get("result") in {"hit", "hits"}:
                state = "PRESENT"
            elif category == "SEARCH_INDEX_ENTRY" and row.get("result") in {"miss", "no_hit"}:
                state = "ABSENT"
            else: state = None
            scope = f"{meta['file_id']}:log:{system}:{trace or n}"
            observation = _obs(meta, f"line={n},trace={trace}", scope, system, category, joined, at, state)
            observation["trace_proof"] = trace_proof
            observation["source_system_label"] = source_system
            out.append(observation)
    return out, set()


def _visual_rows(index, meta):
    """Only parse labelled resource facts; mere OCR search hits are not state proof."""
    segments = index.visual_observations.get(meta["file_id"], [])
    text = "\n".join(s["text"] for s in segments)
    if not text: return [], set()
    # A signed journal extract supplies a record-specific retention requirement.
    # Label structure, not a filename or an identifier prefix, selects this adapter.
    refs = re.findall(r"\bEvent reference\s+(\S+)", text, re.I)
    subjects = re.findall(r"\bsubject reference\s+(\S+)", text, re.I)
    date_pattern = r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s+(\d{2})[\s:]+(\d{2})\s+UTC"
    recorded = re.search(r"^recorded\s+" + date_pattern, text, re.I | re.M)
    until = re.search(r"^retain until\s+" + date_pattern, text, re.I | re.M)
    if len(refs) == len(subjects) == 1 and recorded and until and \
            "journal entry" in text.casefold() and re.search(r"integrity seal\s+valid\b", text, re.I):
        from datetime import datetime, timezone
        def date_value(match):
            day, month, year, hour, minute = match.groups()
            return datetime.strptime(f"{day} {month} {year} {hour}:{minute}", "%d %b %Y %H:%M").replace(
                tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        record = {"resource_id": refs[0], "subject_reference": subjects[0],
                  "event_recorded_at": date_value(recorded), "retention_until": date_value(until)}
        locations = [s["source_location"].split("#", 1)[-1] for s in segments
                     if re.search(r"Event reference|subject reference|^recorded|^retain until", s["text"], re.I)]
        return [_obs(meta, "retention-extract:" + ";".join(locations),
                     f"{meta['file_id']}:journal-extract", "security_service", "SECURITY_AUDIT_LOG", record)], set()
    if "disputed order entries" in text.casefold() or "tax records register" in text.casefold():
        out = []
        for segment in segments:
            match = re.search(r"^\d+\s+(\S+)\s*\|\s*(\S+)\s*\|\s*([^|]+)\|.*?Retain until\s+([^|]+)",
                              segment["text"], re.I)
            if not match: continue
            record = {"order_reference": match[1], "subject_reference": match[2],
                      "financial_retain_until_text": match[4].strip(),
                      "reason_text": match[3].strip(), "excerpt": segment["text"]}
            out.append(_context(meta, segment["source_location"].split("#")[-1], record))
        return out, set()
    # OCR is often noisy. A missing explicit status stays an investigation gap.
    system, category = None, None
    lower = text.casefold()
    for word, pair in {
        "customer details": ("account_service", "USER_PROFILE"),
        "raw document": ("search_service", "SEARCH_INDEX_ENTRY"),
        "search connectors": ("integration_service", "DATA_FLOW"),
        "profile attributes": ("analytics_platform", "ANALYTICS_PROFILE"),
        "data exports": ("export_service", "USER_EXPORT"),
        "conversation": ("support_platform", "SUPPORT_MESSAGE"),
        "recovery manager": ("backup_service", "BACKUP_ARCHIVE"),
        "raw event": ("security_service", "SECURITY_AUDIT_LOG"),
        "retained reference": ("identity_service", "ACCOUNT_TOMBSTONE"),
        "content type": ("object_storage", "SUPPORT_ATTACHMENT"),
        "audience operations": ("marketing_platform", "MARKETING_PROFILE"),
    }.items():
        if word not in lower: continue
        if word == "conversation" and not (
                re.search(r"\bconversation\s+updated[^\n]*\b\d+\s+records\b", text, re.I)
                and re.search(r"\b\d{2}:\d{2}\s+\S+", text)):
            # Shared order prose and support references are contextual, not a message table.
            continue
        system, category = pair
        break
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
    def __init__(self, dataset, visual_cache=None, image_model="local-ocr"):
        super().__init__(dataset, visual_cache, image_model)
        self._normalize()

    @classmethod
    def from_index(cls, index):
        if isinstance(index, cls): return index
        result = cls.__new__(cls)
        result.__dict__ = dict(index.__dict__)
        result._normalize()
        return result

    def _normalize(self):
        self.observations, self.scopes, self.adapter_gaps, self.inventories = [], set(), [], []
        self.contexts = []
        self.link_records = []
        self.source_assessments = {}
        for fid, meta in sorted(self.manifest.items()):
            suffix = Path(meta["file_path"]).suffix.lower()
            try:
                if suffix == ".json": found, scopes = _json_rows(json.loads(self.contents[fid]), meta)
                elif suffix == ".sql": found, scopes = _sql_rows(self.contents[fid], meta, self.inventories)
                elif suffix == ".log": found, scopes = _log_rows(self.contents[fid], meta, self.link_records)
                elif suffix == ".txt": found, scopes = _handover_rows(self.contents[fid], meta)
                elif suffix in {".png", ".pdf"}: found, scopes = _visual_rows(self, meta)
                else:
                    self.adapter_gaps.append(f"Unsupported format: {fid}:{suffix}")
                    self.source_assessments[fid] = {"status": "UNSUPPORTED", "adapter": suffix}
                    continue
                self.observations.extend(o for o in found if o.get("evidence_role") != "CONTEXT")
                self.contexts.extend(o for o in found if o.get("evidence_role") == "CONTEXT")
                self.scopes.update(scopes)
                if suffix in {".png", ".pdf"} and not found:
                    self.adapter_gaps.append("Visual assessment unresolved: " + fid)
                    self.source_assessments[fid] = {"status": "UNEXTRACTED" if fid in self.opaque else "PARTIAL",
                        "adapter": suffix, "reason": "No supported visual resource assessment"}
                else:
                    self.source_assessments[fid] = {"status": "LINK_SEARCH_SUPPORTED", "adapter": suffix,
                                                   "normalized_records": len(found)}
            except (Rejected, ValueError, KeyError, TypeError) as exc:
                self.adapter_gaps.append(f"Adapter rejected {fid}: {exc}")
                self.source_assessments[fid] = {"status": "ADAPTER_FAILURE", "adapter": suffix, "reason": str(exc)}
        self.by_resource = defaultdict(list)
        for obs in self.observations:
            if obs["resource_id"]: self.by_resource[obs["resource_id"]].append(obs)


def identity_conflict(record, identity):
    # Stable references in lookup/correlation fields are typed by their values.
    if record.get("_ambiguous_identity_trace"): return True
    for key, value in record.items():
        if isinstance(value, dict) and key in {"document", "profile", "subject_selector"}:
            if identity_conflict(value, identity): return True
        if not isinstance(value, str) or value in {"null", "None", "NULL"}: continue
        if key in {"user_id", "customer_reference"} or key in DIRECT_KEYS | IDENTIFIER_KEYS and value.startswith("user_"):
            if value and value != identity["user_id"]: return True
    return False


def linked(record, identity):
    """Exact typed aliases, including stable references in generic lookup fields."""
    if identity_conflict(record, identity): return False
    aliases = {(a["field"], a["value"].casefold()) for a in identity["aliases"]}
    for key, value in record.items():
        if key in {"document", "profile", "subject_selector"} and isinstance(value, dict):
            if linked(value, identity): return True
        if not isinstance(value, str) or not value or value in {"null", "None"}: continue
        if key not in DIRECT_KEYS | IDENTIFIER_KEYS | {"subject_selector"} and not any(
                field in key for field in ("email", "phone", "hash")): continue
        if value == identity["user_id"]: return True
        field = ("email_hash" if "hash" in key or re.fullmatch(r"[0-9a-fA-F]{64}", value)
                 else "phone" if "phone" in key else "email")
        if field == "phone":
            digits = re.sub(r"\D", "", value)
            if any(f == "phone" and re.sub(r"\D", "", alias) == digits for f, alias in aliases): return True
        elif (field, value.casefold()) in aliases: return True
    return False


def case_view(index, identity, cutoff, return_search=False):
    """Shared historical graph, followed by exact-ID complete-table checks."""
    from .linking import link_subject, resource
    import copy
    # Normalized evidence is immutable; include mutable CSV inputs in the key so
    # tests and callers that update activity/history cannot reuse stale links.
    key = (json.dumps(identity, sort_keys=True), cutoff,
           hash(tuple(tuple(sorted(e.items())) for e in index.activity)),
           hash(tuple(tuple(sorted(e.items())) for e in index.history)),
           len(index.observations), len(index.link_records))
    cache = index.__dict__.setdefault("_link_cache", {})
    if key not in cache:
        if len(cache) >= 4: cache.pop(next(iter(cache)))
        cache[key] = link_subject(index, identity, cutoff)
    selected, candidates, known, edges, audit, catalog_claims = copy.deepcopy(cache[key])
    for inventory in index.inventories:
        fid = inventory["evidence_id"]
        if fid not in candidates or not eligible(inventory["captured_at"], cutoff): continue
        for (system, rid), category in known.items():
            if not category or inventory["system_id"] not in {"*", system} or inventory["category"] not in {"*", category}: continue
            if (system, rid) in inventory["resources"]: continue
            observation = _obs(inventory["meta"], "table=" + inventory["table"] + ",lookup=" + rid,
                fid + ":" + inventory["table"], system, category, {"resource_id": rid},
                inventory["captured_at"], "ABSENT")
            selected.append(observation)
            edges.append({"from": resource(system, rid), "to": {"kind": "OBSERVATION", "evidence_id": fid,
                "source_location": observation["source_location"]}, "direction": "FROM_TO",
                "link_type": "SAME_RESOURCE_OBSERVATION", "absence_basis": "Exact grounded ID in complete SQL table",
                "proof": [{"evidence_id": fid, "source_location": observation["source_location"],
                           "captured_at": observation["capture_at"], "observed_at": observation["observed_at"]}]})
    audit["links"] = edges
    value = selected, candidates, known, catalog_claims
    return (*value, audit) if return_search else value

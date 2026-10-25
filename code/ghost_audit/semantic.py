"""Narrow, source-quoted semantic assessments inside the existing case validator."""
import re
import json

from .core import Rejected, eligible, tokens


def resource_in(text, rid):
    return bool(rid and re.search(r"(?<!\w)" + re.escape(rid) + r"(?!\w)", text, re.I))


def evidence_units(session, fid):
    if not session.identity or fid not in session.ledger["candidates"] or fid not in session.inspected:
        raise Rejected("Inspect an eligible subject-linked candidate first")
    meta = session.index.manifest[fid]
    if not eligible(meta["captured_at"], session.request["audit_at"]):
        raise Rejected("Evidence captured after audit_at")
    if fid in session.index.visual_observations:
        return [{"source_location": row["source_location"], "text": row["text"]}
                for row in session.index.visual_observations[fid]]
    observations = [o for o in session.observations if o["evidence_id"] == fid]
    if meta["file_path"].lower().endswith(".json"):
        return [{"source_location": o["source_location"], "text": json.dumps(o["record"], ensure_ascii=False)}
                for o in observations]
    traces = {p["source_location"].split("trace=", 1)[1] for o in observations
              for p in o.get("trace_proof", []) if "trace=" in p["source_location"]}
    identifiers = {a["value"].casefold() for a in session.identity["aliases"]} | {
        o["resource_id"].casefold() for o in observations}
    return [{"source_location": meta["file_path"] + f"#line={n}", "text": line}
            for n, line in enumerate(session.index.contents[fid].splitlines(), 1)
            if identifiers & tokens(line) or any(resource_in(line, o["resource_id"]) for o in observations)
            or any(t in tokens(line) for t in traces)]


def validate_assessment(session, proposal):
    expected = {"kind", "evidence_id", "system_id", "resource_id", "conclusion", "supporting_quotes", "explanation"}
    if set(proposal) - {"context_type"} != expected or proposal["kind"] not in {"SUPPORT_SHARED_CONTEXT", "VISUAL_SUPPORT_RECORD"} \
            or proposal["conclusion"] not in {"CONFIRMED", "INSUFFICIENT"}:
        raise Rejected("Invalid semantic assessment schema")
    if any(not isinstance(proposal[k], str) for k in expected - {"supporting_quotes"}):
        raise Rejected("Semantic fields must be strings")
    fid, rid, system = proposal["evidence_id"], proposal["resource_id"], proposal["system_id"]
    units = evidence_units(session, fid)
    by_location = {u["source_location"]: u["text"] for u in units}
    quotes = proposal["supporting_quotes"]
    if not isinstance(quotes, list) or not quotes:
        raise Rejected("A semantic assessment requires exact source quotes")
    for quote in quotes:
        if not isinstance(quote, dict) or set(quote) != {"source_location", "quote", "role"} or \
                not isinstance(quote["source_location"], str) or not isinstance(quote["role"], str) or \
                quote["role"] not in {"RESOURCE", "SUBJECT", "CONTEXT", "STATE", "TYPE", "OWNERSHIP"} or \
                not isinstance(quote["quote"], str) or not quote["quote"].strip() or \
                quote["quote"] not in by_location.get(quote["source_location"], ""):
            raise Rejected("Semantic quote or source location is not supported by inspected evidence")
    grounded = [o for o in session.observations if o["system_id"] == system and o["resource_id"] == rid
                and o["evidence_id"] == fid]
    catalog_grounded = any(e["target_system"] == system and e["resource_id"] == rid
                           for e in session.ledger.get("identity_links", []))
    literal_resource = any(resource_in(q["quote"], rid) for q in quotes if q["role"] == "RESOURCE")
    if not grounded and not catalog_grounded and not literal_resource:
        raise Rejected("Resource identity is not grounded")
    review = {**proposal, "accepted_scope": "SEMANTIC_ASSESSMENT_ONLY", "observation": None}
    if proposal["conclusion"] == "INSUFFICIENT":
        return review
    context = [q for q in quotes if q["role"] == "CONTEXT"]
    if not context:
        raise Rejected("Confirmed shared context requires a context-content quote")
    meta = session.index.manifest[fid]
    if proposal["kind"] == "SUPPORT_SHARED_CONTEXT":
        if not grounded or any(o["category"] != "SUPPORT_MESSAGE" for o in grounded):
            raise Rejected("Support context requires an existing subject-linked support observation")
        from .proof import message_contents, substantive_context_quote
        if proposal.get("context_type") not in {"SHARED_CUSTOMER", "SHARED_AGENT", "SHARED_ORDER"}:
            raise Rejected("Confirmed context requires an explicit policy-context interpretation")
        if not proposal["explanation"].strip():
            raise Rejected("Semantic context interpretation requires an explanation")
        original = max(grounded, key=lambda o: o["observed_at"])
        contents = message_contents(original["record"])
        if fid in session.index.visual_observations:
            contents += [original["record"].get("visual_text", "")]
        if not any(content in q["quote"] or q["quote"] in content for content in contents for q in context):
            raise Rejected("Operational lookup metadata is not proof of shared support context")
        quoted_content = [content if content in q["quote"] else q["quote"]
                          for content in contents for q in context
                          if content in q["quote"] or q["quote"] in content]
        if not any(substantive_context_quote(text) for text in quoted_content):
            raise Rejected("A greeting or isolated keyword is not substantive shared-context proof")
        traces = {p["source_location"].split("trace=", 1)[1] for o in grounded for p in o.get("trace_proof", [])
                  if "trace=" in p["source_location"]}
        bound = all(q["source_location"] == original["source_location"] or
                    resource_in(by_location[q["source_location"]], rid) or
                    traces & tokens(by_location[q["source_location"]]) for q in context)
        if fid in session.index.visual_observations:
            # Interpret only the already grounded support resource. A page/image
            # needs explicit resource and subject anchors; a global caption is insufficient.
            resource_quotes = [q for q in quotes if q["role"] == "RESOURCE" and resource_in(q["quote"], rid)]
            subject_quotes = [q for q in quotes if q["role"] == "SUBJECT" and any(
                a["value"].casefold() in tokens(q["quote"]) for a in session.identity["aliases"])]
            def scope(location):
                fragment = location.split("#", 1)[-1]
                return fragment.split(",", 1)[0] if fragment.startswith("page=") else "image"
            scopes = {scope(q["source_location"]) for q in context + resource_quotes + subject_quotes}
            bound = bool(resource_quotes and subject_quotes) and len(scopes) == 1
        if not bound:
            raise Rejected("Context quote is not bound to the grounded resource or its trace")
        original = max(grounded, key=lambda o: o["observed_at"])
        observation = {**original, "record": {**original["record"], "shared_context_verified": True}}
    else:
        if fid not in session.index.visual_observations or meta.get("origin") != system or system != "support_platform":
            raise Rejected("Visual support assessment must use a supplied support-platform artifact")
        resource_quotes = [q for q in quotes if q["role"] == "RESOURCE" and re.search(
            r"\bsupport reference\b[^\n]*/\s*" + re.escape(rid) + r"\b", q["quote"], re.I)]
        subject_quotes = [q for q in quotes if q["role"] == "SUBJECT" and any(
            a["field"] == "email" and a["value"].casefold() in tokens(q["quote"]) for a in session.identity["aliases"])]
        if not resource_quotes or not subject_quotes:
            raise Rejected("Visual resource and subject need explicit support-reference and exact identifier quotes")
        def page(location): return location.split("#", 1)[-1].split(",", 1)[0]
        pages = {page(q["source_location"]) for q in resource_quotes + subject_quotes + context}
        if len(pages) != 1 or not next(iter(pages)).startswith("page="):
            raise Rejected("Visual subject, resource, and context must be in one customer-record page")
        page_text = "\n".join(u["text"] for u in units if page(u["source_location"]) in pages)
        emails = set(re.findall(r"[\w.+%\-]+@[\w.\-]+", page_text.casefold()))
        allowed = {a["value"].casefold() for a in session.identity["aliases"] if a["field"] == "email"}
        if not emails or not emails <= allowed:
            raise Rejected("Visual page contains an unassociated subject identifier")
        if not any(re.search(r"\b(?:order|agent|delivery|product)\b", q["quote"], re.I) for q in context):
            raise Rejected("Visual context quote does not establish shared order or support content")
        # A ticket reference and shared order context do not identify the resource type.
        # Type must be explicitly bound to this resource on the same customer page.
        types = [q for q in quotes if q["role"] == "TYPE" and page(q["source_location"]) in pages
                 and resource_in(q["quote"], rid)]
        messages = [q for q in types if re.search(r"\b(?:conversation|message)\s+record\b", q["quote"], re.I)]
        attachments = [q for q in types if re.search(r"\battachment\s+(?:record|resource)\b", q["quote"], re.I)]
        if bool(messages) == bool(attachments):
            raise Rejected("Visual resource category unproved: support reference and shared context are insufficient")
        category = "SUPPORT_MESSAGE" if messages else "SUPPORT_ATTACHMENT"
        ownership = [q for q in quotes if q["role"] == "OWNERSHIP" and page(q["source_location"]) in pages
                     and resource_in(q["quote"], rid) and any(email in tokens(q["quote"]) for email in emails)
                     and re.search(r"\bbelongs only to\b", q["quote"], re.I)]
        observation = {"evidence_id": fid, "capture_at": meta["captured_at"], "observed_at": meta["captured_at"],
            "source_location": resource_quotes[0]["source_location"], "scope": fid + ":visual-support-record",
            "system_id": system, "category": category, "resource_id": rid, "state": "PRESENT",
            "source_origin": meta["origin"], "record": {"resource_id": rid, "requester_email": sorted(emails)[0],
                "shared_context_verified": bool(messages), "subject_only": bool(ownership)}}
    observation["semantic_proof"] = quotes
    review["observation"] = observation
    return review

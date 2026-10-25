"""Field-level state reconciliation and structural shared-context evidence."""
import re

DIRECT = {"name", "full_name", "email", "phone", "email_hash", "requester_name", "requester_email", "requester_phone",
          "owner_email", "customer_email", "owner_phone"}
STABLE = {"user_id", "customer_reference", "subject_reference", "subject_ref"}
BODY = {"body", "message_text", "message_excerpt", "content", "text"}


def populated_identifiers(record, anonymize=False):
    fields = DIRECT | (STABLE if anonymize else set())
    found = {k: v for k, v in record.items() if k in fields and v not in (None, "")}
    for key in ("document", "profile", "attributes"):
        if isinstance(record.get(key), dict):
            found.update({key+"/"+k: v for k, v in populated_identifiers(record[key], anonymize).items()})
    return found


def state_conflict(record, state):
    if state in {"REDACTED", "ANONYMIZED"}:
        return bool(populated_identifiers(record, state == "ANONYMIZED"))
    return False


def support_context_proof(record):
    """Return concrete contextual fields, never truth from a nonempty body alone."""
    bodies = [str(v) for k, v in record.items() if k in BODY and isinstance(v, str) and v.strip()]
    messages = record.get("messages", [])
    if isinstance(messages, list):
        bodies += [str(v) for m in messages if isinstance(m, dict) for k, v in m.items()
                   if k in BODY and isinstance(v, str) and v.strip()]
    text = "\n".join(bodies)
    if not text: return []
    proof = []
    # A literal business reference in actual content is context, not an identity
    # link or a newly invented resource. Labels and identifier spellings may vary.
    if re.search(r"\b(?:order|commande|pedido|auftrag)\s+(?:(?:reference|number|ref|no)\s*[:#]?\s*)?"
                 r"(?=[\w-]*[\d_-])[\w-]+\b", text, re.I):
        proof.append("business reference in message content")
    # A conversation can preserve order context without disclosing its order ID.
    # Require a relationship (actor/contact action/topic), not a lone keyword.
    actor = r"\b(?:customer|client|buyer|shopper)\b"
    interaction = r"\b(?:asked|inquired|enquired|queried|followed\s+up|contacted|supplied|provided|discussed|requested)\b"
    topic = r"\b(?:order\s+(?:update|status|delivery)|delivery\s+(?:query|question|issue)|shipment\s+(?:status|query))\b"
    if re.search(actor, text, re.I) and re.search(interaction, text, re.I) and re.search(topic, text, re.I):
        proof.append("customer interaction concerning order/delivery context")
    for field in ("order_id", "order_reference", "order_number", "agent_id", "agent_name", "assigned_agent"):
        value = record.get(field)
        if isinstance(value, str) and value.strip() and re.search(r"(?<!\w)"+re.escape(value)+r"(?!\w)", text, re.I):
            proof.append(field)
    if record.get("sender_role", record.get("author_role")) in {"agent", "support_agent"} and re.search(
            r"\b(?:replacement|order|delivery|parcel|shipment|refund|payment|account)\b", text, re.I) and re.search(
            r"\b(?:dispatched|sent|arranged|processed|resolved|approved|reviewed|updated|confirmed)\b", text, re.I):
        proof.append("agent-authored operational context")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict) and support_context_proof(message):
                proof.append("contextual conversation content")
    return proof


def treatment_fields_supported(record, category, state):
    if state == "REDACTED" and category == "ACCOUNT_TOMBSTONE":
        return {"email", "phone", "email_hash"} <= record.keys() and bool({"name", "full_name"} & record.keys())
    if state == "ANONYMIZED" and category in {"ANALYTICS_PROFILE", "PRODUCT_TELEMETRY"}:
        return {"email", "phone", "email_hash"} <= record.keys() and bool(STABLE & record.keys())
    return True


def message_contents(record):
    """Source content across equivalent nested support-message representations."""
    values = []
    for key, value in record.items():
        if key in BODY and isinstance(value, str) and value.strip(): values.append(value)
        elif key in BODY | {"messages", "conversation"}:
            children = value if isinstance(value, list) else [value]
            for child in children:
                if isinstance(child, dict): values.extend(message_contents(child))
    return values


def substantive_context_quote(text):
    """A floor for semantic proposals, not a shared-context classifier."""
    words = re.findall(r"[\w'-]+", text.casefold())
    greeting = {"hello", "hi", "thanks", "thank", "you", "please", "regards", "dear", "good", "morning"}
    return len(words) >= 4 and len(set(words) - greeting) >= 3

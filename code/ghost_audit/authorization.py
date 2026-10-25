"""Conservative clause-scoped authorization checks; ambiguity belongs to the model."""
import re
from enum import Enum

ACT = re.compile(r"\b(?:delet\w*|eras\w*|remov\w*|clos\w*|purge\w*|elimin\w*|supprim\w*|suppress\w*|effac\w*)\b|削除")
MARKETING = re.compile(r"\b(?:marketing|newsletter\w*|mailing\s+list\w*|promotional|advertis\w*|publicit\w*|promotionnel\w*|listes?\s+de\s+diffusion|campaign\w*|subscription\w*)\b")
BROAD = re.compile(r"\b(?:account|profile|personal\s+(?:data|information|details)|all\s+(?:my\s+)?data|cuenta|datos|compte|données)\b|アカウント")
OTHER = re.compile(r"\b(?:export\w*|access|correct\w*|update\w*|marketing|unsubscribe|opt.out|download\w*)\b")
NEG = re.compile(r"\b(?:not(?!\s+only)|no(?!\s+longer)|never|without|avoid|refrain|decline|don't|do\s+not|no\s+(?:quiero|deseo)|ne\b.{0,45}\bpas|pas\s+de)\b")


class Authorization(str, Enum):
    YES = "YES"
    NO = "NO"
    UNCERTAIN = "UNCERTAIN"


def deletion_authorization(text):
    value = text.casefold().replace("’", "'")
    positive, negative, limited = [], [], []
    clauses = re.split(r"[;,\n]|(?<=[.!?])\s+|\b(?:but|however|and|et|mais|cependant)\b", value)
    for clause in clauses:
        acts = list(ACT.finditer(clause))
        for n, act in enumerate(acts):
            before = clause[max(0, act.start()-65):act.start()]
            after = clause[act.end():acts[n+1].start() if n+1 < len(acts) else len(clause)]
            negated = bool(NEG.search(before) or (re.search(r"\bne\b", before) and re.match(r"\s+pas\b", after)) or re.match(r"\s+(?:is|was|has been)\s+not\s+(?:requested|authorized|wanted)", after))
            scope = clause[act.start():acts[n+1].start() if n+1 < len(acts) else len(clause)]
            scope = re.split(r"\band\s+(?:unsubscribe|opt.out|export|correct|update)\b", scope)[0]
            scope = re.split(r"\b(?:keep\w*|preserv\w*|retain\w*|leave)\b", scope)[0]
            before = re.split(r"\b(?:keep\w*|preserv\w*|retain\w*|leave)\b", before)[0]
            # Passive requests put the target before the deletion verb.
            if not BROAD.search(scope) and BROAD.search(before): scope = before + scope
            if negated:
                negative.append(scope)
            elif MARKETING.search(scope) and (re.search(r"\b(?:marketing|promotional|advertising)\s+(?:account|profile|data)\b", scope) or not re.search(r"\baccount\b|\ball\b.{0,25}\b(?:data|information|details)\b", scope) or
                    re.search(r"\b(?:from|in|within|only|just)\b.{0,40}" + MARKETING.pattern, scope)):
                limited.append(scope)
            elif BROAD.search(scope) or not OTHER.search(clause) and not MARKETING.search(clause):
                positive.append(scope)
    if positive:
        return None if any(BROAD.search(s) for s in negative) else True
    if negative or limited: return False
    if re.search(r"\b(?:confirm|verify|check|audit)\b", value) and re.search(
            r"\b(?:profile|account|personal data|remaining records)\b.{0,90}\b(?:gone|removed|cannot identify|no longer identify)\b", value):
        return True
    # An isolated English keyword inside an unrecognized language is not a veto.
    # NO requires a recognized non-deletion request, not a borrowed English
    # word inside otherwise unrecognized language. Other readings stay UNCERTAIN.
    simple_nondelete = (r"(?:(?:please|can you|could you|i (?:only )?(?:want|need|request))\s+)?"
        r"(?:export|download|correct|update|give me access to|unsubscribe|opt(?:\s+me)?\s+out)\s+"
        r"(?:(?:my|the|a|all|copy|of|personal|account|data|information|records|details|email|phone|address|me|from|your|marketing|mailing|lists?|newsletters?|promotional|communications)\s*)+[.!?]?")
    if re.fullmatch(simple_nondelete, value.strip()):
        return False
    return None


def authorization_status(text):
    value = deletion_authorization(text)
    return Authorization.YES if value is True else Authorization.NO if value is False else Authorization.UNCERTAIN

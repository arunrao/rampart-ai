"""
Verdict policy for the prompt-injection detector.

Replaces the old weighted average (0.7*deberta + 0.3*regex) with explicit
rules, per-source profiles and a noisy-or regex score. Thresholds are starting
values and are meant to be fitted against ``backend/eval``.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Optional, Sequence

POLICY_VERSION = "2026.10-rules-v1"


class Verdict(str, Enum):
    ALLOW = "allow"
    MONITOR = "monitor"
    FLAG = "flag"
    BLOCK = "block"
    UNAVAILABLE = "unavailable"


_ORDER = {Verdict.ALLOW: 0, Verdict.MONITOR: 1, Verdict.UNAVAILABLE: 2, Verdict.FLAG: 3, Verdict.BLOCK: 4}


def max_verdict(*verdicts: Verdict) -> Verdict:
    return max(verdicts, key=lambda v: _ORDER[v])


def verdict_at_least(v: Verdict, floor: Verdict) -> bool:
    return _ORDER[v] >= _ORDER[floor]


# Reason codes whose presence alone is strong evidence of an attack.
STRONG_PATTERNS = frozenset({
    "instruction_override",
    "new_instruction",
    "system_prompt_extraction",
    "exfiltration_command",
    "dan_mode",
    "unrestricted_mode",
    "ai_addressed",
    "tool_hijack",
})

# Weak patterns can only ever produce MONITOR on their own.
WEAK_PATTERNS = frozenset({
    "role_change",
    "system_impersonation",
    "unicode_escape",
    "base64_suspicious",
    "delimiter_injection",
    "context_switching",
    "future_instruction",
    "context_marker_manipulation",
    "zero_width_chars",
    "unicode_tag_chars",
    "private_use_chars",
    "homoglyph_chars",
    "encoded_payload",
})

# Convention-shaped / supply-chain instructions. Capped at FLAG in every profile
# so they never break ordinary developer docs, but are never silently allowed.
SUPPLY_CHAIN_PATTERNS = frozenset({
    "pipe_to_shell",
    "disable_review_or_ci",
    "untrusted_dependency_source",
    "new_network_host",
})

MAX_WEAK_SEVERITY = 0.4
MAX_SUPPLY_CHAIN_SEVERITY = 0.6


@dataclass(frozen=True)
class Profile:
    name: str
    block_deberta: float      # BLOCK needs deberta >= this AND a strong pattern
    flag_deberta: float       # FLAG on deberta alone
    monitor_deberta: float    # MONITOR on deberta alone
    strong_alone: Verdict     # verdict for a strong regex hit with low/no deberta
    weak_alone: Verdict       # verdict for a weak hit alone
    supply_chain: Verdict     # verdict cap for supply-chain family


PROFILES: Dict[str, Profile] = {
    # Fetched web pages, uploads, emails, retrieved documents: untrusted by default.
    "third_party_document": Profile(
        name="third_party_document",
        block_deberta=0.90, flag_deberta=0.75, monitor_deberta=0.30,
        strong_alone=Verdict.FLAG, weak_alone=Verdict.MONITOR, supply_chain=Verdict.FLAG,
    ),
    # A user's own brief / spec / notes. Not an attack surface in the same way;
    # DeBERTa saturates on security-flavoured prose, so demand more from it.
    "user_brief": Profile(
        name="user_brief",
        block_deberta=0.97, flag_deberta=0.90, monitor_deberta=0.50,
        strong_alone=Verdict.FLAG, weak_alone=Verdict.ALLOW, supply_chain=Verdict.FLAG,
    ),
    # READMEs, API docs, AGENTS.md, code. Imperative-heavy and full of
    # "ignore the warnings" / "admin access required".
    "code_docs": Profile(
        name="code_docs",
        block_deberta=0.95, flag_deberta=0.85, monitor_deberta=0.40,
        strong_alone=Verdict.FLAG, weak_alone=Verdict.MONITOR, supply_chain=Verdict.FLAG,
    ),
}
DEFAULT_PROFILE = "third_party_document"


def get_profile(name: Optional[str]) -> Profile:
    if not name:
        return PROFILES[DEFAULT_PROFILE]
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError(f"Unknown profile '{name}'. Valid: {sorted(PROFILES)}")


def tier_for(code: str) -> str:
    if code in STRONG_PATTERNS:
        return "strong"
    if code in SUPPLY_CHAIN_PATTERNS:
        return "supply_chain"
    return "weak"


def cap_severity(code: str, severity: float) -> float:
    tier = tier_for(code)
    if tier == "weak":
        return min(severity, MAX_WEAK_SEVERITY)
    if tier == "supply_chain":
        return min(severity, MAX_SUPPLY_CHAIN_SEVERITY)
    return severity


def noisy_or(severities: Iterable[float], cap: float = 0.98) -> float:
    """1 - prod(1 - s_i), capped. Repeated matches should be de-duplicated by code first."""
    p_none = 1.0
    for s in severities:
        p_none *= (1.0 - max(0.0, min(1.0, s)))
    return min(cap, 1.0 - p_none)


def regex_score(reasons: Sequence[Dict]) -> float:
    """Noisy-or of the capped severity of each *distinct* reason code."""
    by_code: Dict[str, float] = {}
    for r in reasons:
        sev = cap_severity(r["code"], float(r.get("severity", 0.0)))
        by_code[r["code"]] = max(by_code.get(r["code"], 0.0), sev)
    return noisy_or(by_code.values())


def decide(
    profile: Profile,
    deberta_max: Optional[float],
    reasons: Sequence[Dict],
    *,
    degraded: bool = False,
) -> Verdict:
    """
    Rule-based verdict.

    - BLOCK: deberta >= block AND an *unquoted* strong pattern
             (strong pattern found in a decoded/hidden channel counts even if quoted)
    - FLAG:  deberta >= flag alone, or an unquoted strong pattern alone
    - MONITOR: weak pattern, quoted/mentioned strong pattern, or deberta in [monitor, flag)
    - ALLOW: otherwise
    - supply-chain family: capped at profile.supply_chain (FLAG)
    - degraded: anything that would be ALLOW/MONITOR becomes UNAVAILABLE
    """
    # Matches in decoded payloads / hidden channels are never marked quoted by the scanner.
    strong_live = [r for r in reasons if tier_for(r["code"]) == "strong" and not r.get("quoted")]
    weak_any = [r for r in reasons if tier_for(r["code"]) == "weak"
                or (tier_for(r["code"]) == "strong" and r.get("quoted"))]
    supply_any = [r for r in reasons if tier_for(r["code"]) == "supply_chain"]
    d = deberta_max if deberta_max is not None else 0.0

    verdict = Verdict.ALLOW
    if strong_live and d >= profile.block_deberta:
        verdict = Verdict.BLOCK
    elif d >= profile.flag_deberta or strong_live:
        verdict = Verdict.FLAG
    elif d >= profile.monitor_deberta:
        verdict = Verdict.MONITOR
    elif weak_any:
        verdict = profile.weak_alone

    if supply_any:
        verdict = max_verdict(verdict, profile.supply_chain)

    if degraded and verdict in (Verdict.ALLOW, Verdict.MONITOR):
        verdict = Verdict.UNAVAILABLE
    return verdict


def legacy_recommendation(verdict: Verdict) -> str:
    """Human-readable string kept for backwards compatibility with old clients."""
    return {
        Verdict.BLOCK: "BLOCK - High-risk injection attempt",
        Verdict.FLAG: "FLAG - Moderate risk, review required",
        Verdict.MONITOR: "MONITOR - Low risk, log for analysis",
        Verdict.ALLOW: "ALLOW - No significant threat",
        Verdict.UNAVAILABLE: "UNAVAILABLE - Detector degraded, treat as unscanned",
    }[verdict]

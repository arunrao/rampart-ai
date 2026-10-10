"""
Prompt Injection Detection

Hybrid detector: normalization -> regex rules (body, hidden channels, decoded
payloads) -> token-chunked DeBERTa -> rule-based verdict -> optional LLM arbiter.

Design notes
- Fail closed: any model failure yields ``degraded: true`` and a verdict that is
  never ALLOW (``unavailable`` at minimum).
- No averaging: verdicts come from ``models.injection_policy.decide``.
- Weak patterns can only ever MONITOR; supply-chain patterns cap at FLAG.
- The legacy keys (``is_injection``, ``confidence``, ``risk_score``,
  ``recommendation``, ``detection_details``) are still emitted for old callers.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple, cast

from models.injection_normalize import (
    HIDDEN_CHANNEL_KINDS,
    Channel,
    DecodedPayload,
    decode_candidates,
    extract_hidden_channels,
    normalize_text,
)
from models.injection_policy import (
    POLICY_VERSION,
    Profile,
    Verdict,
    cap_severity,
    decide,
    get_profile,
    legacy_recommendation,
    noisy_or,
    regex_score,
    tier_for,
)

# Suppress known PyTorch ONNX warnings (harmless compatibility issues)
warnings.filterwarnings("ignore", message=".*scaled_dot_product_attention.*")
warnings.filterwarnings("ignore", category=UserWarning, module="torch.onnx")

logger = logging.getLogger(__name__)


class PromptInjectionDetectorLike(Protocol):
    """Structural type for regex / DeBERTa / hybrid detectors."""

    def detect(self, text: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        ...

    def batch_detect(self, texts: List[str], *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        ...


@dataclass
class InjectionPattern:
    """Pattern for detecting prompt injection"""
    name: str
    pattern: str
    severity: float  # 0.0 to 1.0 (capped by tier in injection_policy)
    description: str
    flags: int = re.IGNORECASE


# ---------------------------------------------------------------------------
# Regex rules
# ---------------------------------------------------------------------------

_W = r"\s+"


def _load_patterns() -> List[InjectionPattern]:
    return [
        # ---- strong -------------------------------------------------------
        InjectionPattern(
            "instruction_override",
            r"\b(?:ignore|disregard|forget|override|bypass|discard)\s+"
            r"(?:"
            # "ignore all [of] [the] [previous] instructions"
            r"(?:all|any|every|everything)(?:\s+of)?(?:\s+(?:the|your|my|these|those))?"
            r"(?:\s+(?:previous|above|prior|earlier|preceding|original|existing|other|system|safety|initial))?"
            r"|"
            # "ignore [the] previous instructions" / "ignore your instructions"
            r"(?:(?:the|my|these|those)\s+)?(?:your(?:\s+(?:previous|above|prior|earlier|preceding|original|existing|other|system|safety|initial))?"
            r"|(?:previous|above|prior|earlier|preceding|original|existing|other|system|safety|initial))"
            r")"
            r"\s+(?:instructions?|prompts?|rules?|commands?|directives?|guidelines?|constraints?|guardrails?|programming|training)\b"
            r"|\b(?:ignore|disregard|forget)\s+(?:all\s+of\s+|everything\s+)?(?:the\s+)?above\b",
            0.9,
            "Attempts to override prior instructions",
        ),
        InjectionPattern(
            "new_instruction",
            # Capitalised at line start ("New instructions:") or any case after a delimiter run.
            # Lower-case at line start is usually a wrapped sentence ("...added\nnew instructions: ...").
            r"(?:(?:^|\n)[ \t]*(?:#+[ \t]*|[-*][ \t]+)?(?:Your[ \t]+)?(?:New|Updated|Revised|Real|Actual|True|NEW|UPDATED|REVISED|REAL|ACTUAL)"
            r"|[\-=#*`]{3,}[ \t]*(?:[Yy]our[ \t]+)?(?:[Nn]ew|[Uu]pdated|[Rr]evised|[Rr]eal|[Aa]ctual|[Tt]rue|NEW|UPDATED|REAL))"
            r"[ \t]+(?:[Ii]nstructions?|[Pp]rompts?|[Rr]ules?|[Tt]ask|[Dd]irectives?|[Ss]ystem[ \t]+[Pp]rompt|INSTRUCTIONS?|PROMPTS?|RULES?|TASK|DIRECTIVES?)[ \t]*:",
            0.85,
            "Introduces replacement instructions",
            0,
        ),
        InjectionPattern(
            "tool_hijack",
            r"\b(?:call|invoke|use|run|execute|trigger)\s+(?:the\s+)?(?:`?[\w.-]+`?\s+)?(?:tool|function|action|skill|plugin|command)\b"
            r"[^.\n]{0,120}?(?:\bto\s*=|\S+@\S+\.\w+|https?://|\brm\s+-rf\b|\bdelete\s+(?:all|every)\b|\boverwrite\b|\.ssh\b|\bid_rsa\b|\bsecrets?\b|\bcredentials?\b|\bapi[_ ]keys?\b|\bconversation\s+history\b|\ball\s+previous\s+messages\b)"
            r"|\b(?:assistant|agent|ai)\s*:\s*ignore\s+the\s+user'?s?\s+(?:request|question|instructions?)\b",
            0.9,
            "Instructs an agent to misuse a tool or function",
        ),
        InjectionPattern(
            "system_prompt_extraction",
            r"\b(?:show|give|send|tell|reveal|share|provide|display|print|output|repeat|leak|dump|paste)"
            r"\s+(?:me\s+)?(?:"
            # "your [full] [system] prompt/instructions"
            r"(?:all\s+of\s+)?your\s+(?:(?:system|initial|original|hidden|secret|full|complete|exact|entire)\s+){0,2}"
            r"(?:prompt|instructions|system\s+message|preamble)"
            r"|"
            # "the [full] system prompt" — bare "the instructions" is ordinary English
            r"the\s+(?:(?:full|complete|exact|entire|hidden|secret)\s+){0,2}"
            r"(?:system\s+(?:prompt|message|instructions)|initial\s+prompt|original\s+(?:prompt|instructions)|preamble)"
            r")\b"
            r"|\bwhat\s+(?:were|are|is)\s+your\s+(?:original|initial|system|hidden)\s+(?:instructions?|prompts?)\b"
            r"|\brepeat\s+(?:everything|the\s+text)\s+above\b",
            0.95,
            "Attempts to extract the system prompt",
        ),
        InjectionPattern(
            "exfiltration_command",
            r"\b(?:send|post|upload|transmit|email|forward|exfiltrate|leak|submit)\s+"
            r"(?:this|the|all|every|any|everything|their|his|her|our|my|user'?s?|users'?|the\s+user'?s?)\b"
            r"[^.\n]{0,80}?\b(?:to|at|via)\s+"
            r"(?:https?://|ftp://|\S+@\S+\.\w+|[a-z0-9-]+(?:\.[a-z0-9-]+)*"
            r"\.(?:com|net|org|io|dev|xyz|ru|cn|co|me|info|biz|app|site|online|top|cc|tk|ml|ga|cf|gq|onion)\b)",
            0.95,
            "Instructs exfiltration of data to an external destination",
        ),
        InjectionPattern(
            "dan_mode",
            r"\bDAN\s+mode\b|\bdo\s+anything\s+now\b|\bjailbreak(?:ed|ing)?\s+(?:mode|prompt)\b",
            0.95,
            "Known jailbreak persona (DAN)",
        ),
        InjectionPattern(
            "unrestricted_mode",
            r"\b(?:enter|enable|activate|switch\s+to|(?:be|being|are|operate|operating|respond|now)\s+in)\s+"
            r"(?:an?\s+)?(?:unrestricted|unlimited|unfiltered|uncensored|no[-\s]limits?)\s+(?:mode|version|model|state)\b",
            0.9,
            "Requests an unrestricted operating mode",
        ),
        InjectionPattern(
            "ai_addressed",
            # "note to any AI", "attention all assistants" — but not "instructions for the model" (docs)
            r"\b(?:note|message|attention|reminder|instructions?)\s+(?:to|for)\s+(?:any|all)\s+"
            r"(?:ai|llm|language\s+model|assistant|agent|model|chatbot|copilot)s?\b"
            r"|\b(?:note|message|attention|reminder)\s+(?:to|for)\s+the\s+(?:ai|llm|assistant|agent|chatbot)\b"
            r"|\bif\s+you(?:'re|\s+are)\s+an?\s+(?:ai|llm|language\s+model|assistant|agent|chatbot)\b"
            r"|\b(?:ai|llm|assistant|agent|model)s?\s+(?:reading|processing|parsing|summarizing|summarising)\s+this\b"
            r"|\bwhen\s+(?:you|the\s+(?:ai|assistant|model|agent))\s+(?:read|see|process|encounter|receive)s?\s+this"
            r"(?=\s*(?:[,:.;!\-]|$)|\s+(?:message|email|document|page|note|text|file|comment|post|content)\b)"
            r"|\bthis\s+is\s+a\s+system\s+message\b",
            0.9,
            "Text addressed to an AI reader (indirect injection marker)",
        ),
        # ---- weak (<= 0.4) ------------------------------------------------
        InjectionPattern(
            "role_change",
            r"\b(?:you\s+are\s+now|you\s+will\s+(?:now\s+)?(?:act|behave|respond|answer)\s+as|"
            r"from\s+now\s+on\s+you\s+are|pretend\s+(?:that\s+)?you\s+are|pretend\s+to\s+be|"
            r"act\s+as\s+if\s+you\s+(?:are|were|have|had))\b",
            0.4,
            "AI-addressed role change",
        ),
        InjectionPattern(
            "system_impersonation",
            r"\b(?:enter|enable|activate|switch\s+to|grant\s+(?:me|yourself)|you\s+(?:now\s+)?have|"
            r"i\s+have|(?:you\s+are\s+)?now\s+in)\s+(?:full\s+)?"
            r"(?:system|admin|administrator|root|developer|god|sudo)\s+(?:mode|access|privileges?|rights?)\b",
            0.4,
            "AI-addressed privilege / mode escalation",
        ),
        InjectionPattern(
            "delimiter_injection",
            r"^\s*(?:-{3,}|={3,}|\*{3,}|`{3,}|#{1,6})\s*"
            r"(?:system|instruction|prompt|end\s+of\s+(?:system|instructions?|prompt|context))"
            r"\s*(?::|$|\s+(?:prompt|message|override))",
            0.35,
            "Delimiter used to fake a system/instruction boundary",
            re.IGNORECASE | re.MULTILINE,
        ),
        InjectionPattern(
            "context_switching",
            r"\b(?:end|start|beginning)\s+of\s+(?:the\s+)?(?:system\s+)?(?:instructions?|prompt|context)\b"
            r"(?!\s+(?:window|length|size|menu|builder|engineering))",
            0.3,
            "Claims a context boundary",
        ),
        InjectionPattern(
            "future_instruction",
            r"\b(?:from\s+now\s+on|in\s+(?:all\s+)?(?:your\s+)?future\s+(?:responses|replies|answers|messages|outputs)|"
            r"for\s+the\s+rest\s+of\s+(?:this\s+)?(?:conversation|session|chat))\b"
            r"[^.\n!?]{0,80}?\b(?:you\s+(?:must|will|should|shall)|always|never|respond|answer|say|reply|include|end|start)\b",
            0.35,
            "Persistent instruction for future turns",
        ),
        InjectionPattern(
            "unicode_escape",
            r"(?:\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2})(?:\s*(?:\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2})){7,}",
            0.3,
            "Long run of escape sequences (obfuscated text)",
            0,
        ),
        # ---- supply-chain / convention-shaped (capped at FLAG) -----------
        # These fire on the *instruction* shape ("must always", "do not review", "agents:"),
        # not on the mere presence of an install one-liner, which every README has.
        InjectionPattern(
            "pipe_to_shell",
            r"\b(?:must|should|always|never\s+skip|required\s+to|need\s+to|have\s+to|agents?\s+(?:must|should|will)|before\s+(?:anything|everything)\s+else)\b"
            r"[^.\n]{0,160}?\b(?:curl|wget|fetch|iwr|invoke-webrequest)\b[^\n|;]{0,200}\|\s*(?:sudo\s+(?:-E\s+)?)?(?:ba|z|da|k|fi)?sh\b"
            r"|\b(?:curl|wget)\b[^\n|;]{0,200}\|\s*(?:sudo\s+(?:-E\s+)?)?(?:ba|z|da|k|fi)?sh\b[^.\n]{0,160}?\b(?:before\s+(?:anything|everything)\s+else|do\s+not\s+(?:review|inspect|read)|without\s+(?:reviewing|inspecting|verifying))\b"
            r"|\biex\s*\(\s*(?:new-object|iwr|invoke-webrequest|\(new-object)",
            0.6,
            "Mandates piping a remote script to a shell",
        ),
        InjectionPattern(
            "disable_review_or_ci",
            r"\b(?:must|should|always|agents?\s+(?:must|should|will)|convention|policy|required\s+to)\b[^.\n]{0,80}?"
            r"\b(?:skip|disable|bypass|turn\s+off|remove|suppress)\s+(?:the\s+|all\s+|any\s+)?"
            r"(?:code\s+)?(?:reviews?|ci|test\s+suite|tests|checks|verification|signature\s+verification|branch\s+protection|"
            r"security\s+scan(?:ning|s)?|pre-?commit\s+hooks?)\b"
            r"|\b(?:do\s+not|don'?t|never|without|no\s+need\s+to)\s+(?:review(?:ing)?|inspect(?:ing)?|read(?:ing)?|verify(?:ing)?|audit(?:ing)?)\s+"
            r"(?:the\s+|this\s+)?(?:script|installer|binary|download|archive)\b"
            r"|\b(?:must|should|always)\s+(?:use|run|commit\s+with)\b[^.\n]{0,40}?--no-verify\b"
            r"|\b(?:add|set|export|put)\b[^.\n]{0,40}?\b(?:GIT_SSL_NO_VERIFY|NODE_TLS_REJECT_UNAUTHORIZED|PIP_TRUSTED_HOST)\b"
            r"|\b(?:merge|push)\s+directly\s+to\s+(?:main|master|production)\b",
            0.5,
            "Mandates disabling review, CI, or verification",
        ),
        InjectionPattern(
            "untrusted_dependency_source",
            r"\b(?:must|should|always|first|agents?\s+(?:must|should)|required|before)\b[^.\n]{0,80}?"
            r"\b(?:pip3?|npm|yarn|pnpm|gem|cargo|go|uv|poetry|bun)\s+(?:install|add|get)\b[^\n]{0,80}?"
            r"(?:--index-url|--extra-index-url|--registry|--find-links|\s+https?://|\s+git\+)"
            r"|\bnpm\s+config\s+set\s+registry\s+https?://(?!registry\.npmjs\.org)"
            r"|\b(?:index-url|extra-index-url)\s*=\s*https?://(?!pypi\.org)",
            0.5,
            "Mandates installing dependencies from a non-default source",
        ),
        InjectionPattern(
            "new_network_host",
            r"\b(?:set|export|add|configure|point|change)\s+(?:the\s+|your\s+)?"
            r"(?:proxy|registry|mirror|remote|webhook(?:\s+endpoint)?|endpoint|callback|telemetry|upstream)\b[^\n.]{0,60}?\bto\s+https?://"
            r"|\b(?:download|fetch)\b[^.\n]{0,60}?\bhttps?://\S+[^.\n]{0,80}?\bwithout\s+(?:verifying|checking|validating)\b",
            0.4,
            "Introduces a new network destination",
        ),
    ]


_BARE_PIPE_TO_SHELL = re.compile(
    r"\b(?:curl|wget|fetch|iwr|invoke-webrequest)\b[^\n|;]{0,200}\|\s*(?:sudo\s+(?:-E\s+)?)?(?:ba|z|da|k|fi)?sh\b", re.I)
_ROLE_MARKER_RE = re.compile(r"^\s*(?:system|user|assistant|human|ai)\s*:", re.IGNORECASE | re.MULTILINE)

# Opening / closing quote detection for "mentioned, not used" demotion.
_SYMMETRIC_QUOTES = ('"', "`")
_SINGLE_OPEN = re.compile(r"(?:^|[\s(\[{:,=])'")
_SINGLE_CLOSE = re.compile(r"'(?=[\s)\]}.,;:!?]|$)")
_CURLY_PAIRS = (("\u201c", "\u201d"), ("\u2018", "\u2019"))


# Descriptive framing immediately before a match marks it as *mentioned* rather
# than *used* ("attempts to reveal the system prompt", "phrases like ...").
_MENTION_FRAMING = re.compile(
    r"(?:\b(?:attempts?|attempting|tries|trying|asks?|asking|told|tells|telling|say|says|saying|"
    r"such\s+as|like|e\.g\.|for\s+example|examples?\s+(?:of|include)|patterns?\s+(?:like|such\s+as)|"
    r"detects?|detecting|catch(?:es)?|flags?|classif(?:y|ies)|block(?:s|ing)?|"
    r"phrases?|strings?|inputs?|prompts?\s+(?:like|such\s+as)|known\s+as|called|"
    r"the\s+(?:phrase|string|pattern|text|input|attack|request)|"
    r"(?:may|might|could|would|will|can)\s+(?:try\s+to\s+|attempt\s+to\s+)?(?:tell|ask|instruct|say|write))"
    r"\s*(?:the\s+(?:model|ai|assistant|agent|llm)\s+)?(?:to\s+)?[\"'`\u201c\u2018]?\s*$)",
    re.IGNORECASE,
)
_MENTION_LOOKBACK = 48
_QUOTE_WINDOW = 160
_JSON_KV_LINE = re.compile(r"""^\s*["'][^"']+["']\s*:\s*["']""")


def _is_quoted(text: str, start: int, end: int) -> bool:
    """
    True when [start, end) is *mentioned* rather than *used*: it sits inside an
    inline quote pair on the same line, or is introduced by descriptive framing.
    """
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    before, after = text[line_start:start], text[end:line_end]
    # Structured data (JSON / YAML values) quotes everything; that is not "mentioning".
    if _JSON_KV_LINE.match(text[line_start:line_end]):
        return bool(_MENTION_FRAMING.search(before[-_MENTION_LOOKBACK:]))
    # Only look at the nearby text: stray quotes far away on a long line are not a pair.
    before, after = before[-_QUOTE_WINDOW:], after[:_QUOTE_WINDOW]
    before, after = before.replace('"""', "").replace("'''", ""), after.replace('"""', "").replace("'''", "")
    for q in _SYMMETRIC_QUOTES:
        if before.count(q) % 2 == 1 and q in after:
            return True
    opens = len(_SINGLE_OPEN.findall(before))
    # A quote immediately before the match is an opener, not a closer.
    closes = sum(1 for m in _SINGLE_CLOSE.finditer(before) if m.end() < len(before.rstrip()))
    if opens > closes and _SINGLE_CLOSE.search(after):
        return True
    for o, c in _CURLY_PAIRS:
        if before.count(o) > before.count(c) and c in after:
            return True
    return bool(_MENTION_FRAMING.search(before[-_MENTION_LOOKBACK:]))


class PromptInjectionDetector:
    """
    Regex-rule detector. Scans the normalized body, hidden channels and decoded
    payloads. Usable standalone (``detector_type="regex"``) or as stage 1 of the
    hybrid detector.
    """

    MAX_MATCHES_PER_PATTERN = 50

    def __init__(self):
        self.patterns = _load_patterns()
        self._compiled = [(p, re.compile(p.pattern, p.flags)) for p in self.patterns]

    # -- scanning ------------------------------------------------------------
    def _scan_text(self, text: str, channel: str, offset: int = 0, check_quotes: bool = True) -> List[Dict]:
        reasons: List[Dict] = []
        for pat, rx in self._compiled:
            for n, m in enumerate(rx.finditer(text)):
                if n >= self.MAX_MATCHES_PER_PATTERN:
                    break
                reasons.append({
                    "code": pat.name,
                    "tier": tier_for(pat.name),
                    "strong": tier_for(pat.name) == "strong",
                    "severity": cap_severity(pat.name, pat.severity),
                    "description": pat.description,
                    "matched_text": m.group()[:120],
                    "position": (m.start() + offset, m.end() + offset),
                    "channel": channel,
                    "quoted": _is_quoted(text, m.start(), m.end()) if check_quotes else False,
                })
        if channel == "body" and len(_ROLE_MARKER_RE.findall(text)) >= 3:
            reasons.append({
                "code": "context_marker_manipulation", "tier": "weak", "strong": False,
                "severity": 0.3, "description": "Multiple chat-role markers in content",
                "matched_text": "", "position": (-1, -1), "channel": "body", "quoted": False,
            })
        return reasons

    def scan(self, text: str) -> Tuple[Any, List[Dict], List[Channel], List[DecodedPayload]]:
        """Normalize and run every regex stage. Returns (normalization, reasons, channels, payloads)."""
        norm = normalize_text(text)
        body = norm.text
        reasons = self._scan_text(body, "body")

        channels = extract_hidden_channels(body)
        for ch in channels:
            hidden = ch.kind in HIDDEN_CHANNEL_KINDS
            if ch.kind == "package_json_script" and _BARE_PIPE_TO_SHELL.search(ch.text):
                # A lifecycle hook that pipes a download into a shell needs no "must": it runs on install.
                reasons.append({
                    "code": "pipe_to_shell", "tier": "supply_chain", "strong": False, "severity": 0.6,
                    "description": "Install hook pipes a remote script to a shell", "matched_text": ch.text[:120],
                    "position": (ch.start, ch.end), "channel": f"channel:{ch.kind}", "quoted": False,
                })
            for r in self._scan_text(ch.text, f"channel:{ch.kind}", ch.start, check_quotes=not hidden):
                dup = next((b for b in reasons if b["code"] == r["code"] and b["channel"] == "body"
                            and ch.start <= b["position"][0] <= ch.end), None)
                if dup is None:
                    reasons.append(r)
                elif hidden:
                    dup["channel"], dup["quoted"] = r["channel"], False
                else:
                    dup["channel"] = r["channel"]

        payloads = decode_candidates(body)
        for p in payloads:
            reasons.append({
                "code": "encoded_payload", "tier": "weak", "strong": False, "severity": 0.3,
                "description": f"Decodable {p.encoding} payload", "matched_text": "",
                "position": (p.start, p.end), "channel": f"decoded:{p.encoding}", "quoted": False,
            })
            reasons.extend(self._scan_text(p.text, f"decoded:{p.encoding}", p.start, check_quotes=False))

        for s in norm.signals:
            reasons.append({
                "code": s["code"], "tier": "weak", "strong": False, "severity": 0.35,
                "description": "Hidden/confusable characters present", "matched_text": "",
                "position": (-1, -1), "channel": "body", "quoted": False, "count": s.get("count"),
            })
        return norm, reasons, channels, payloads

    # -- public --------------------------------------------------------------
    def detect(self, text: str, profile: Optional[str] = None, **_: Any) -> Dict:
        start = time.perf_counter()
        prof = get_profile(profile)
        norm, reasons, channels, payloads = self.scan(text)
        verdict = decide(prof, None, reasons)
        score = regex_score(reasons)
        return _build_result(
            text=text, verdict=verdict, score=score, reasons=reasons, profile=prof,
            degraded=False, degraded_reason=None, detector="regex",
            deberta_max=None, chunks={"total": 0, "scanned": 0, "failed": 0, "flagged": 0, "spans": []},
            signals=norm.signals, payloads=payloads, channels=channels,
            model_version=None, latency_ms=(time.perf_counter() - start) * 1000, arbiter=None,
        )

    def batch_detect(self, texts: List[str], profile: Optional[str] = None, **_: Any) -> List[Dict]:
        return [self.detect(t, profile=profile) for t in texts]


# ---------------------------------------------------------------------------
# DeBERTa
# ---------------------------------------------------------------------------

try:
    from transformers import (  # pyright: ignore[reportMissingImports]
        AutoModelForSequenceClassification,
        AutoTokenizer,
        pipeline,
    )

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    pipeline = cast(Any, None)
    AutoTokenizer = cast(Any, None)
    AutoModelForSequenceClassification = cast(Any, None)
    logger.warning("Transformers not available. DeBERTa detection disabled.")

try:
    from optimum.onnxruntime import (  # pyright: ignore[reportMissingImports]
        ORTModelForSequenceClassification,
    )

    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    ORTModelForSequenceClassification = cast(Any, None)
    logger.info("ONNX optimization not available. Using PyTorch for DeBERTa.")


class ModelUnavailable(RuntimeError):
    """Raised when the classifier cannot be used (not loaded / dependencies missing)."""


class DeBERTaPromptInjectionDetector:
    """
    DeBERTa-based prompt injection classifier (ProtectAI/deberta-v3-base-prompt-injection-v2).

    ``score`` raises on any failure so callers can fail closed; ``detect`` keeps
    the old never-raise contract for legacy callers.
    """

    DEFAULT_MODEL = "protectai/deberta-v3-base-prompt-injection-v2"
    MAX_LENGTH = 512  # model input limit in tokens
    CHUNK_TOKENS = 448  # leaves headroom for special tokens
    CHUNK_OVERLAP_TOKENS = 64
    FALLBACK_CHARS_PER_TOKEN = 2.5  # conservative when no fast tokenizer (CJK/code/base64)

    def __init__(
        self,
        model_name: Optional[str] = None,
        use_onnx: bool = True,
        device: int = -1,
        confidence_threshold: float = 0.75,
    ):
        self.model_name = model_name or self.DEFAULT_MODEL
        self.use_onnx = use_onnx and ONNX_AVAILABLE
        self.device = device
        self.confidence_threshold = confidence_threshold
        self._revision: Optional[str] = None
        self._tokenizer = None
        self._pipeline = None
        self._model_loaded = False
        self._load_error: Optional[str] = None

    # -- loading -------------------------------------------------------------
    @property
    def model(self):
        if not self._model_loaded:
            self._load_model()
            self._model_loaded = True
        return self._pipeline

    @property
    def available(self) -> bool:
        return self.model is not None

    @property
    def model_version(self) -> str:
        rev = (self._revision or "unpinned")[:12]
        return f"{self.model_name}@{rev}"

    def _load_model(self):
        if not TRANSFORMERS_AVAILABLE:
            self._load_error = "transformers_unavailable"
            logger.error("Transformers library not available")
            return
        try:
            logger.info("Loading DeBERTa model: %s", self.model_name)
            from models.pinned_revisions import revision_for

            revision = revision_for(self.model_name)
            self._revision = revision
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, revision=revision)
            try:
                self._tokenizer.deprecation_warnings["sequence-length-is-longer-than-the-specified-maximum"] = True
            except Exception:
                pass

            model = None
            if self.use_onnx:
                try:
                    try:
                        model = ORTModelForSequenceClassification.from_pretrained(
                            self.model_name, export=False, revision=revision)
                    except Exception:
                        model = ORTModelForSequenceClassification.from_pretrained(
                            self.model_name, export=True, revision=revision)
                except Exception as onnx_error:
                    logger.warning("ONNX loading failed (%s); falling back to PyTorch", onnx_error)
            if model is None:
                model = AutoModelForSequenceClassification.from_pretrained(self.model_name, revision=revision)

            self._pipeline = pipeline(
                "text-classification",
                model=cast(Any, model),
                tokenizer=self._tokenizer,
                device=self.device,
                max_length=self.MAX_LENGTH,
                truncation=True,
            )
            logger.info("DeBERTa detector ready (device: %s)", "GPU" if self.device >= 0 else "CPU")
        except Exception as e:
            self._load_error = f"model_load_failed:{type(e).__name__}"
            logger.error("Failed to load DeBERTa model: %s", e)
            self._pipeline = None

    # -- chunking ------------------------------------------------------------
    def chunk_spans(self, text: str) -> List[Tuple[int, int]]:
        """
        Split *text* into overlapping windows of <= CHUNK_TOKENS tokens, returned
        as character spans. Falls back to a conservative character window when
        no fast tokenizer with offset mapping is available.
        """
        if not text:
            return [(0, 0)]
        tok = self._tokenizer if self._model_loaded else None
        if tok is None:
            self.model  # trigger load
            tok = self._tokenizer
        offsets: Optional[List[Tuple[int, int]]] = None
        if tok is not None and getattr(tok, "is_fast", False):
            try:
                enc = tok(text, add_special_tokens=False, return_offsets_mapping=True,
                          truncation=False, verbose=False)
                offsets = [tuple(o) for o in enc["offset_mapping"] if o[1] > o[0]]  # type: ignore
            except Exception as exc:
                logger.warning("Tokenizer offset mapping failed (%s); using char fallback", type(exc).__name__)
                offsets = None
        if not offsets:
            step = int(self.CHUNK_TOKENS * self.FALLBACK_CHARS_PER_TOKEN)
            overlap = int(self.CHUNK_OVERLAP_TOKENS * self.FALLBACK_CHARS_PER_TOKEN)
            spans, s = [], 0
            while True:
                e = min(len(text), s + step)
                spans.append((s, e))
                if e >= len(text):
                    return spans
                s = e - overlap
        spans = []
        i, n = 0, len(offsets)
        while True:
            j = min(n, i + self.CHUNK_TOKENS)
            spans.append((offsets[i][0], offsets[j - 1][1]))
            if j >= n:
                break
            i = max(i + 1, j - self.CHUNK_OVERLAP_TOKENS)
        # Tokens never cover leading/trailing whitespace; stretch the ends so coverage is total.
        spans[0] = (0, spans[0][1])
        spans[-1] = (spans[-1][0], len(text))
        return spans

    # -- inference -----------------------------------------------------------
    def score(self, text: str) -> float:
        """P(INJECTION) for a single chunk. Raises ModelUnavailable / RuntimeError on failure."""
        if not self.model:
            raise ModelUnavailable(self._load_error or "model_not_loaded")
        result = self.model(text, top_k=None)
        scores = {item["label"]: float(item["score"]) for item in result}
        if "INJECTION" not in scores and "SAFE" not in scores:
            raise RuntimeError(f"unexpected labels: {sorted(scores)}")
        return scores.get("INJECTION", 1.0 - scores.get("SAFE", 1.0))

    def detect(self, text: str, return_all_scores: bool = False) -> Dict:
        """Legacy single-text API (never raises)."""
        try:
            s = self.score(text)
        except Exception as e:
            logger.error("DeBERTa inference failed: %s", type(e).__name__)
            return {"is_injection": False, "confidence": 0.0, "label": "ERROR", "error": str(e), "degraded": True}
        is_inj = s >= self.confidence_threshold
        return {
            "is_injection": is_inj, "confidence": s, "label": "INJECTION" if is_inj else "SAFE",
            "all_scores": {"INJECTION": s, "SAFE": 1.0 - s} if return_all_scores else None,
            "model": "deberta-v3-base", "model_version": self.model_version, "threshold": self.confidence_threshold,
        }

    def batch_detect(self, texts: List[str]) -> List[Dict]:
        return [self.detect(t) for t in texts]


# ---------------------------------------------------------------------------
# Hybrid
# ---------------------------------------------------------------------------

class HybridPromptInjectionDetector:
    """
    normalization -> regex (body/channels/decoded) -> token-chunked DeBERTa
    -> rule-based verdict -> optional arbiter.
    """

    MAX_CHUNK_WORKERS = 8
    MIN_EXTRA_CHUNK_CHARS = 20
    MAX_EXTRA_CHUNKS = 32
    FOCUS_WINDOW_CHARS = 240
    MAX_FOCUS_WINDOWS = 8

    def __init__(
        self,
        use_deberta: bool = True,
        use_onnx: bool = True,
        deberta_threshold: float = 0.75,
        regex_threshold: float = 0.3,  # kept for signature compatibility
        arbiter: Optional[Any] = None,
    ):
        self.regex_detector = PromptInjectionDetector()
        self.deberta_detector: Optional[DeBERTaPromptInjectionDetector] = None
        self.use_deberta = use_deberta and TRANSFORMERS_AVAILABLE
        self.regex_threshold = regex_threshold
        self.arbiter = arbiter
        self._init_error: Optional[str] = None
        if use_deberta and not TRANSFORMERS_AVAILABLE:
            self._init_error = "transformers_unavailable"
        if self.use_deberta:
            try:
                self.deberta_detector = DeBERTaPromptInjectionDetector(
                    use_onnx=use_onnx, confidence_threshold=deberta_threshold)
                logger.info("Hybrid detector initialized with DeBERTa")
            except Exception as e:
                logger.error("Failed to initialize DeBERTa: %s", e)
                self.use_deberta = False
                self._init_error = f"deberta_init_failed:{type(e).__name__}"
        else:
            logger.info("Hybrid detector running in regex-only mode")

    # -- deberta stage -------------------------------------------------------
    def _run_deberta(self, body: str, extras: Sequence[Tuple[str, str, int]], profile: Profile) -> Dict:
        """
        Score every token chunk of *body* plus every extra (source, text, base_offset) item.
        Returns per-chunk spans, max score and failure accounting. Never raises.
        """
        assert self.deberta_detector is not None
        det = self.deberta_detector
        jobs: List[Tuple[str, int, int, str]] = []  # (source, start, end, text)
        try:
            for s, e in det.chunk_spans(body):
                jobs.append(("body", s, e, body[s:e]))
            for source, text, base in extras[: self.MAX_EXTRA_CHUNKS]:
                for s, e in det.chunk_spans(text):
                    jobs.append((source, base + s, base + e, text[s:e]))
        except Exception as exc:
            return {"spans": [], "max": None, "total": 0, "scanned": 0, "failed": 0,
                    "error": f"chunking_failed:{type(exc).__name__}"}

        if not det.available:
            return {"spans": [], "max": None, "total": len(jobs), "scanned": 0, "failed": len(jobs),
                    "error": det._load_error or "model_not_loaded"}

        spans: List[Dict] = []
        failed = 0
        error: Optional[str] = None

        def _one(idx: int) -> Tuple[int, float]:
            return idx, det.score(jobs[idx][3])

        if len(jobs) == 1:
            try:
                spans.append({"source": jobs[0][0], "start": jobs[0][1], "end": jobs[0][2], "score": det.score(jobs[0][3])})
            except Exception as exc:
                failed, error = 1, f"{type(exc).__name__}"
        else:
            with ThreadPoolExecutor(max_workers=min(len(jobs), self.MAX_CHUNK_WORKERS)) as ex:
                futures = [ex.submit(_one, i) for i in range(len(jobs))]
                for fut in as_completed(futures):
                    try:
                        idx, sc = fut.result()
                        spans.append({"source": jobs[idx][0], "start": jobs[idx][1], "end": jobs[idx][2], "score": sc})
                    except Exception as exc:
                        failed += 1
                        error = error or type(exc).__name__
            spans.sort(key=lambda d: (d["source"] != "body", d["start"]))

        mx = max((d["score"] for d in spans), default=None)
        if failed:
            error = f"chunk_failures:{failed}/{len(jobs)}:{error}"
        return {"spans": spans, "max": mx, "total": len(jobs), "scanned": len(spans), "failed": failed, "error": error}

    # -- public --------------------------------------------------------------
    def detect(
        self,
        text: str,
        fast_mode: bool = False,
        force_deberta: bool = False,
        profile: Optional[str] = None,
        arbiter: Optional[Any] = None,
    ) -> Dict:
        start = time.perf_counter()
        prof = get_profile(profile)
        norm, reasons, channels, payloads = self.regex_detector.scan(text)

        degraded = False
        degraded_reason: Optional[str] = None
        deberta_max: Optional[float] = None
        chunks = {"total": 0, "scanned": 0, "failed": 0, "flagged": 0, "spans": []}
        detector = "regex"

        if fast_mode and not force_deberta:
            pass  # caller explicitly asked for regex only; not degraded
        elif not self.use_deberta or self.deberta_detector is None:
            degraded, degraded_reason = True, self._init_error or "deberta_unavailable"
        else:
            detector = "hybrid"
            # Body chunks already contain visible comments/docstrings; only text a human
            # would not see (hidden channels) or could not read (decoded) is scored separately.
            extras: List[Tuple[str, str, int]] = []  # (source, text, absolute base offset)
            extras += [(f"decoded:{p.encoding}", p.text, p.start) for p in payloads if len(p.text) >= self.MIN_EXTRA_CHUNK_CHARS]
            extras += [(f"channel:{c.kind}", c.text, c.start) for c in channels
                       if c.kind in HIDDEN_CHANNEL_KINDS and len(c.text) >= self.MIN_EXTRA_CHUNK_CHARS]
            # A one-sentence injection inside a 448-token chunk of ordinary prose dilutes the
            # classifier. Score a focused window around each unquoted strong rule hit as well.
            seen: set = set()
            for r in reasons:
                if r["strong"] and not r["quoted"] and r["channel"] == "body" and r["position"][0] >= 0:
                    s = max(0, r["position"][0] - self.FOCUS_WINDOW_CHARS)
                    e = min(len(norm.text), r["position"][1] + self.FOCUS_WINDOW_CHARS)
                    if (s, e) not in seen and len(seen) < self.MAX_FOCUS_WINDOWS:
                        seen.add((s, e))
                        extras.append((f"focus:{r['code']}", norm.text[s:e], s))
            db = self._run_deberta(norm.text, extras, prof)
            deberta_max = db["max"]
            chunks = {
                "total": db["total"], "scanned": db["scanned"], "failed": db["failed"],
                # coverage-style count over body chunks only; focus/hidden/decoded spans are listed but
                # would otherwise double-count the same passage
                "flagged": sum(1 for s in db["spans"] if s["source"] == "body" and s["score"] >= prof.flag_deberta),
                "spans": db["spans"],
            }
            if db["failed"] or db["scanned"] == 0 or db.get("error"):
                degraded, degraded_reason = True, db.get("error") or "no_chunks_scanned"

        verdict = decide(prof, deberta_max, reasons, degraded=degraded)

        arbiter_record = None
        arb = arbiter or self.arbiter
        if arb is not None and verdict == Verdict.BLOCK:
            verdict, arbiter_record = arb.adjust(verdict, norm.text)

        score = noisy_or([deberta_max or 0.0, regex_score(reasons)])
        model_version = self.deberta_detector.model_version if self.deberta_detector else None
        return _build_result(
            text=text, verdict=verdict, score=score, reasons=reasons, profile=prof,
            degraded=degraded, degraded_reason=degraded_reason, detector=detector,
            deberta_max=deberta_max, chunks=chunks, signals=norm.signals, payloads=payloads,
            channels=channels, model_version=model_version,
            latency_ms=(time.perf_counter() - start) * 1000, arbiter=arbiter_record,
        )

    def batch_detect(self, texts: List[str], fast_mode: bool = False, profile: Optional[str] = None) -> List[Dict]:
        return [self.detect(t, fast_mode=fast_mode, profile=profile) for t in texts]


# ---------------------------------------------------------------------------
# Result assembly
# ---------------------------------------------------------------------------

def _build_result(
    *,
    text: str,
    verdict: Verdict,
    score: float,
    reasons: List[Dict],
    profile: Profile,
    degraded: bool,
    degraded_reason: Optional[str],
    detector: str,
    deberta_max: Optional[float],
    chunks: Dict,
    signals: List[Dict],
    payloads: List[DecodedPayload],
    channels: List[Channel],
    model_version: Optional[str],
    latency_ms: float,
    arbiter: Optional[Dict],
) -> Dict:
    rscore = regex_score(reasons)
    is_injection = verdict in (Verdict.FLAG, Verdict.BLOCK)
    public_reasons = [
        {k: r[k] for k in ("code", "strong", "tier", "severity", "channel", "quoted", "position")}
        for r in reasons
    ]
    return {
        # -- stable contract --------------------------------------------------
        "verdict": verdict.value,
        "score": round(score, 6),
        "degraded": degraded,
        "degraded_reason": degraded_reason,
        "reasons": public_reasons,
        "chunks": chunks,
        "signals": {
            "normalization": signals,
            "decoded_payloads": [{"encoding": p.encoding, "start": p.start, "end": p.end, "chars": len(p.text)} for p in payloads],
            "hidden_channels": [{"kind": c.kind, "start": c.start, "end": c.end} for c in channels],
        },
        "model_version": model_version,
        "policy_version": POLICY_VERSION,
        "profile": profile.name,
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "detector": detector,
        "latency_ms": round(latency_ms, 2),
        "arbiter": arbiter,
        # -- legacy fields ----------------------------------------------------
        "is_injection": is_injection,
        "confidence": round(score, 6),
        "risk_score": round(score, 6),
        "recommendation": legacy_recommendation(verdict),
        "detection_details": {
            "regex": {"risk_score": rscore, "detected_patterns": reasons, "pattern_count": len(reasons)},
            "deberta": {
                "confidence": deberta_max if deberta_max is not None else 0.0,
                "label": ("INJECTION" if (deberta_max or 0.0) >= profile.flag_deberta else "SAFE") if deberta_max is not None else "UNAVAILABLE",
                "model": "deberta-v3-base" if deberta_max is not None else "unavailable",
                "chunks_scanned": chunks.get("scanned", 0),
                "chunks_total": chunks.get("total", 0),
            },
        },
        "regex_result": {"risk_score": rscore, "detected_patterns": reasons, "is_injection": rscore > 0.5},
        "deberta_result": {
            "is_injection": (deberta_max or 0.0) >= profile.flag_deberta if deberta_max is not None else False,
            "confidence": deberta_max if deberta_max is not None else 0.0,
            "label": "INJECTION" if deberta_max is not None and deberta_max >= profile.flag_deberta else ("SAFE" if deberta_max is not None else "UNAVAILABLE"),
            "degraded": degraded,
        },
    }


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_regex_detector_instance: Optional[PromptInjectionDetector] = None
_deberta_detector_instance: Optional[DeBERTaPromptInjectionDetector] = None
_hybrid_detector_instance: Optional[HybridPromptInjectionDetector] = None


def get_prompt_injection_detector(
    detector_type: str = "hybrid",
    use_onnx: bool = True,
    **kwargs,
) -> PromptInjectionDetectorLike:
    """Get or create a detector singleton: "regex", "deberta", or "hybrid" (recommended)."""
    global _regex_detector_instance, _deberta_detector_instance, _hybrid_detector_instance

    if detector_type == "regex":
        if _regex_detector_instance is None:
            _regex_detector_instance = PromptInjectionDetector()
        return _regex_detector_instance
    if detector_type == "deberta":
        if _deberta_detector_instance is None:
            _deberta_detector_instance = DeBERTaPromptInjectionDetector(use_onnx=use_onnx, **kwargs)
        return _deberta_detector_instance
    if _hybrid_detector_instance is None:
        _hybrid_detector_instance = HybridPromptInjectionDetector(use_deberta=True, use_onnx=use_onnx, **kwargs)
    return _hybrid_detector_instance

"""
Pre-scan normalization, hidden-channel extraction and decode-and-rescan helpers
for the prompt-injection detector.

Everything here is pure text processing (no ML) and is safe to run on untrusted
input of arbitrary length.
"""
from __future__ import annotations

import base64
import binascii
import codecs
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

# Zero-width / invisible formatting characters frequently used to hide text
# from humans while remaining visible to tokenizers.
_ZERO_WIDTH = {
    "\u200b",  # ZERO WIDTH SPACE
    "\u200c",  # ZERO WIDTH NON-JOINER
    "\u200d",  # ZERO WIDTH JOINER
    "\u200e",  # LEFT-TO-RIGHT MARK
    "\u200f",  # RIGHT-TO-LEFT MARK
    "\u2060",  # WORD JOINER
    "\u2061", "\u2062", "\u2063", "\u2064",
    "\u2066", "\u2067", "\u2068", "\u2069",  # bidi isolates
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",  # bidi embeddings/overrides
    "\ufeff",  # BOM / ZWNBSP
    "\u00ad",  # SOFT HYPHEN
    "\u180e",  # MONGOLIAN VOWEL SEPARATOR
}
_TAG_RANGE = (0xE0000, 0xE007F)  # Unicode "Tags" block (ASCII smuggling)
_PUA_RANGES = ((0xE000, 0xF8FF), (0xF0000, 0xFFFFD), (0x100000, 0x10FFFD))

# Common confusable (homoglyph) substitutions that NFKC does not fold.
_HOMOGLYPHS = str.maketrans({
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c",
    "\u0443": "y", "\u0445": "x", "\u0456": "i", "\u0458": "j", "\u04bb": "h",
    "\u0406": "I", "\u0407": "I", "\u0408": "J", "\u0405": "S",
    "\u0410": "A", "\u0412": "B", "\u0415": "E", "\u041a": "K", "\u041c": "M",
    "\u041d": "H", "\u041e": "O", "\u0420": "P", "\u0421": "C", "\u0422": "T",
    "\u0425": "X", "\u03bf": "o", "\u03b1": "a", "\u03b5": "e", "\u03b9": "i",
    "\u03ba": "k", "\u03bd": "v", "\u03c1": "p", "\u03c4": "t", "\u03c5": "u",
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0397": "H", "\u0399": "I",
    "\u039a": "K", "\u039c": "M", "\u039d": "N", "\u039f": "O", "\u03a1": "P",
    "\u03a4": "T", "\u03a7": "X", "\u0417": "3", "\u0455": "s", "\u1e9f": "d",
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u00a0": " ",
})


@dataclass
class NormalizationResult:
    text: str
    signals: List[Dict] = field(default_factory=list)

    @property
    def has_hidden_chars(self) -> bool:
        return any(s["code"] in ("zero_width_chars", "unicode_tag_chars") for s in self.signals)


def _is_tag_or_pua(ch: str) -> Tuple[bool, bool]:
    cp = ord(ch)
    if _TAG_RANGE[0] <= cp <= _TAG_RANGE[1]:
        return True, False
    for lo, hi in _PUA_RANGES:
        if lo <= cp <= hi:
            return False, True
    return False, False


def normalize_text(text: str) -> NormalizationResult:
    """
    NFKC-normalize *text*, strip zero-width / Unicode-tag / private-use characters,
    fold common homoglyphs and report every class of hidden character found.

    Unicode tag characters (U+E0000-E007F) are *decoded* to their ASCII
    counterparts rather than dropped, because that is exactly how "ASCII
    smuggling" hides an instruction: the attacker wants the model to see it.
    """
    signals: List[Dict] = []
    zero_width = tag_chars = pua_chars = 0
    out: List[str] = []
    smuggled: List[str] = []
    for ch in text:
        if ch in _ZERO_WIDTH:
            zero_width += 1
            continue
        is_tag, is_pua = _is_tag_or_pua(ch)
        if is_tag:
            tag_chars += 1
            cp = ord(ch) - 0xE0000
            if 0x20 <= cp < 0x7F:
                decoded = chr(cp)
                out.append(decoded)
                smuggled.append(decoded)
            continue
        if is_pua:
            pua_chars += 1
            continue
        out.append(ch)

    normalized = unicodedata.normalize("NFKC", "".join(out)).translate(_HOMOGLYPHS)
    homoglyph_count = sum(1 for ch in text if ord(ch) in _HOMOGLYPHS)

    if zero_width:
        signals.append({"code": "zero_width_chars", "count": zero_width})
    if tag_chars:
        signals.append({"code": "unicode_tag_chars", "count": tag_chars,
                        "decoded_preview_len": len(smuggled)})
    if pua_chars:
        signals.append({"code": "private_use_chars", "count": pua_chars})
    if homoglyph_count >= 3:
        signals.append({"code": "homoglyph_chars", "count": homoglyph_count})
    return NormalizationResult(text=normalized, signals=signals)


# ---------------------------------------------------------------------------
# Hidden channels
# ---------------------------------------------------------------------------

@dataclass
class Channel:
    kind: str
    text: str
    start: int
    end: int


_CHANNEL_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("html_comment", re.compile(r"<!--(.*?)-->", re.S)),
    ("html_alt_or_title", re.compile(r"""\b(?:alt|title|aria-label|placeholder)\s*=\s*(?:"([^"]{8,})"|'([^']{8,})')""", re.I)),
    ("html_hidden_element", re.compile(
        r"""<(?:span|div|p|font)[^>]*(?:display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|opacity\s*:\s*0|color\s*:\s*(?:white|#fff(?:fff)?|transparent)|hidden)[^>]*>(.*?)</(?:span|div|p|font)>""",
        re.I | re.S)),
    ("markdown_link_title", re.compile(r"""\]\([^)\s]+\s+"([^"]{8,})"\)""")),
    ("markdown_image_alt", re.compile(r"!\[([^\]]{8,})\]\(")),
    ("markdown_reference_comment", re.compile(r"^\s*\[//\]:\s*#\s*\((.*?)\)\s*$", re.M)),
    ("code_block_comment", re.compile(r"/\*(.*?)\*/", re.S)),
    ("code_line_comment", re.compile(r"(?:^|[^:\w\"'])(?://|#(?!!)|--\s|;;|%)\s?([^\n]{8,})", re.M)),
    ("python_docstring", re.compile(r'(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', re.S)),
    ("yaml_or_toml_comment", re.compile(r"^\s*#\s?([^\n]{8,})$", re.M)),
]

_PKG_JSON_KEYS = ("scripts", "preinstall", "postinstall", "prepare", "install")


_SCRIPTS_BLOCK_RE = re.compile(r'"scripts"\s*:\s*(\{[^{}]*\})')


def _package_json_scripts(text: str) -> List[Channel]:
    """Pull `scripts` (lifecycle hooks) out of any package.json-like object embedded in *text*."""
    channels: List[Channel] = []
    for m in _SCRIPTS_BLOCK_RE.finditer(text):
        try:
            scripts = json.loads(m.group(1))
        except ValueError:
            continue
        if not isinstance(scripts, dict):
            continue
        for name, cmd in scripts.items():
            if isinstance(cmd, str) and cmd.strip():
                idx = text.find(cmd, m.start())
                s = idx if idx >= 0 else m.start()
                channels.append(Channel("package_json_script", f"{name}: {cmd}", s, s + len(cmd)))
    return channels


def extract_hidden_channels(text: str, max_channels: int = 200) -> List[Channel]:
    """
    Extract text that a human reader is unlikely to see but a model will:
    HTML comments / alt text / hidden elements, markdown link titles and image
    alt text, code comments and docstrings, package.json scripts.
    """
    found: List[Channel] = []
    for kind, pattern in _CHANNEL_PATTERNS:
        for m in pattern.finditer(text):
            body = next((g for g in m.groups() if g), None)
            if body and len(body.strip()) >= 8:
                found.append(Channel(kind, body.strip(), m.start(), m.end()))
            if len(found) >= max_channels * 2:
                break
    # Drop channels that start inside an earlier one (e.g. "--" inside "<!-- -->")
    found.sort(key=lambda c: (c.start, -(c.end - c.start)))
    channels: List[Channel] = []
    for c in found:
        if channels and c.start < channels[-1].end:
            continue
        channels.append(c)
    channels.extend(_package_json_scripts(text))
    return channels[:max_channels]


# Channel kinds a human reader genuinely does not see. Matches found here are
# never treated as "mentioned, not used". Visible code comments are excluded.
HIDDEN_CHANNEL_KINDS = frozenset({
    "html_comment", "html_alt_or_title", "html_hidden_element", "markdown_link_title",
    "markdown_image_alt", "markdown_reference_comment", "package_json_script",
})


# ---------------------------------------------------------------------------
# Decode-and-rescan
# ---------------------------------------------------------------------------

@dataclass
class DecodedPayload:
    encoding: str
    text: str
    start: int
    end: int


_B64_RE = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{24,}={0,2}(?![A-Za-z0-9+/=])")
_B64URL_RE = re.compile(r"(?<![A-Za-z0-9_\-=])[A-Za-z0-9_\-]{24,}={0,2}(?![A-Za-z0-9_\-=])")
_HEX_RE = re.compile(r"(?<![0-9a-fA-F])(?:[0-9a-fA-F]{2}){16,}(?![0-9a-fA-F])")
_ESC_RE = re.compile(r"(?:\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}|%[0-9a-fA-F]{2}){6,}")
_ALPHA_RE = re.compile(r"[A-Za-z]")


def _mostly_printable_text(s: str, min_alpha_ratio: float = 0.5) -> bool:
    if not s or len(s) < 12:
        return False
    printable = sum(1 for ch in s if ch.isprintable() or ch in "\n\t")
    if printable / len(s) < 0.95:
        return False
    alpha = len(_ALPHA_RE.findall(s))
    return alpha / len(s) >= min_alpha_ratio and " " in s


def _try_b64(blob: str, urlsafe: bool) -> Optional[str]:
    padded = blob + "=" * (-len(blob) % 4)
    try:
        raw = (base64.urlsafe_b64decode if urlsafe else base64.b64decode)(padded)
        return raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def decode_candidates(text: str, max_payloads: int = 32) -> List[DecodedPayload]:
    """
    Find base64 / hex / escaped / rot13 substrings that decode to natural text.
    Returned payloads should be scanned with the same rules as the plain text.
    """
    payloads: List[DecodedPayload] = []
    seen_spans: set = set()

    def _add(enc: str, decoded: str, start: int, end: int) -> None:
        if (start, end) in seen_spans or not _mostly_printable_text(decoded):
            return
        seen_spans.add((start, end))
        payloads.append(DecodedPayload(enc, decoded, start, end))

    for m in _B64_RE.finditer(text):
        decoded = _try_b64(m.group(), urlsafe=False)
        if decoded:
            _add("base64", decoded, m.start(), m.end())
        if len(payloads) >= max_payloads:
            return payloads
    for m in _B64URL_RE.finditer(text):
        if "-" in m.group() or "_" in m.group():
            decoded = _try_b64(m.group(), urlsafe=True)
            if decoded:
                _add("base64url", decoded, m.start(), m.end())
        if len(payloads) >= max_payloads:
            return payloads
    for m in _HEX_RE.finditer(text):
        try:
            decoded = bytes.fromhex(m.group()).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        _add("hex", decoded, m.start(), m.end())
        if len(payloads) >= max_payloads:
            return payloads
    for m in _ESC_RE.finditer(text):
        try:
            decoded = codecs.decode(m.group().replace("%", "\\x"), "unicode_escape")
        except Exception:
            continue
        _add("escape_sequence", decoded, m.start(), m.end())
        if len(payloads) >= max_payloads:
            return payloads

    # rot13: per line, so a single encoded sentence inside an English document is
    # found. A line counts only if its rot13 form has clearly more English
    # stop-words than the original (otherwise every document "decodes").
    pos = 0
    rot_lines: List[Tuple[int, int]] = []
    for line in text.split("\n"):
        if len(line) >= 16 and _stopword_hits(codecs.encode(line, "rot13")) >= max(3, 2 * _stopword_hits(line) + 1):
            rot_lines.append((pos, pos + len(line)))
        pos += len(line) + 1
    if rot_lines and len(rot_lines) <= 50:
        for s, e in rot_lines:
            payloads.append(DecodedPayload("rot13", codecs.encode(text[s:e], "rot13"), s, e))
            if len(payloads) >= max_payloads:
                break
    return payloads


_STOPWORDS = re.compile(r"\b(?:the|and|you|your|all|previous|instructions|ignore|system|prompt|are|now|this|to|of|is)\b", re.I)


def _stopword_hits(s: str) -> int:
    return len(_STOPWORDS.findall(s[:20000]))

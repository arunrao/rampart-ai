"""
Guardrails for caller-supplied regular expressions (custom PII patterns).

User-provided patterns are untrusted: a pattern like ``(a+)+$`` can backtrack
catastrophically (ReDoS) and pin a worker thread. We bound the number and size
of patterns and run them with the ``regex`` module's per-call timeout.
"""
import logging
from typing import Dict, Iterator, Optional

import regex

logger = logging.getLogger(__name__)

MAX_CUSTOM_PATTERNS = 20
MAX_PATTERN_NAME_LENGTH = 64
MAX_PATTERN_LENGTH = 500
PATTERN_TIMEOUT_SECONDS = 0.25


def validate_custom_patterns(patterns: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Pydantic-friendly validator: enforce limits and reject patterns that do not compile."""
    if patterns is None:
        return None
    if len(patterns) > MAX_CUSTOM_PATTERNS:
        raise ValueError(f"At most {MAX_CUSTOM_PATTERNS} custom patterns are allowed")
    for name, pattern in patterns.items():
        if not name or len(name) > MAX_PATTERN_NAME_LENGTH:
            raise ValueError(f"Pattern names must be 1-{MAX_PATTERN_NAME_LENGTH} characters")
        if not pattern or len(pattern) > MAX_PATTERN_LENGTH:
            raise ValueError(f"Pattern '{name}' must be 1-{MAX_PATTERN_LENGTH} characters")
        try:
            regex.compile(pattern)
        except regex.error as e:
            raise ValueError(f"Pattern '{name}' is not a valid regex: {e}")
    return patterns


def safe_finditer(pattern: str, content: str) -> Iterator["regex.Match[str]"]:
    """
    Yield matches of an untrusted pattern, stopping (with a warning) if the pattern
    is invalid or exceeds PATTERN_TIMEOUT_SECONDS.
    """
    try:
        yield from regex.finditer(pattern, content, timeout=PATTERN_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning("Custom PII pattern timed out after %.2fs; skipped", PATTERN_TIMEOUT_SECONDS)
    except regex.error:
        logger.debug("Invalid custom PII pattern skipped")

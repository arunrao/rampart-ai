"""
Pinned Hugging Face Hub revisions for every model Rampart downloads.

`from_pretrained("org/model")` resolves to whatever the repo's `main` branch points at
*right now*. A compromised or force-pushed repo therefore becomes remote code execution
on our workers (transformers has had several deserialization CVEs in exactly this path).
Pinning to a commit SHA makes the download content-addressed and reproducible.

To move a model to a newer revision: run the model smoke tests against the new SHA,
then update it here. Set RAMPART_ALLOW_UNPINNED_MODELS=1 only for local experimentation.
"""
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

PINNED_REVISIONS: Dict[str, str] = {
    # Prompt injection (DeBERTa-v3) — validated revision, 2025
    "protectai/deberta-v3-base-prompt-injection-v2": "e6535ca4ce3ba852083e75ec585d7c8aeb4be4c5",
    # Toxicity (6-label Jigsaw BERT)
    "unitary/toxic-bert": "4d6c22e74ba2fdd26bc4f7238f50766b045a0d94",
    # PII (GLiNER)
    "knowledgator/gliner-pii-edge-v1.0": "9b7f39b0a2da971a5beea78d35f1539d4009c891",
    "knowledgator/gliner-pii-small-v1.0": "d21aad5b4a7ec82b3d0970fd1ac74a12c087d85e",
    "knowledgator/gliner-pii-base-v1.0": "61726e0ad791dcab3e29339bbec3ad42ded65641",
}


def revision_for(model_name: str) -> Optional[str]:
    """
    Return the pinned commit SHA for ``model_name``.

    Unknown models (e.g. a custom DETECTOR_MODEL env override) are allowed through
    unpinned with a warning, unless the name is one we ship, in which case it is pinned.
    Local paths are never pinned.
    """
    if os.path.isdir(model_name):
        return None
    rev = PINNED_REVISIONS.get(model_name)
    if rev:
        return rev
    if os.getenv("RAMPART_ALLOW_UNPINNED_MODELS", "").lower() in ("1", "true", "yes"):
        return None
    logger.warning(
        "Model %s has no pinned revision in models/pinned_revisions.py; loading `main` "
        "(set RAMPART_ALLOW_UNPINNED_MODELS=1 to silence)",
        model_name,
    )
    return None

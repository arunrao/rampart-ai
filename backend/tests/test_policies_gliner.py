"""
Policy evaluation against the real GLiNER PII model.

Opt-in: ``RAMPART_MODEL_TESTS=1 pytest tests/test_policies_gliner.py``
(needs the pinned knowledgator/gliner-pii-small-v1.0 in the HF cache).

These pin what a user-defined ``contains_pii`` / ``contains_phi`` rule actually does in
production, where GLiNER — not the regex fallback — decides. Inputs chosen so that the
regex path would give the *opposite* answer, proving the model is the one deciding.
"""
from __future__ import annotations

import os

import pytest

from api.routes import policies as pol
from api.routes.policies import _evaluate_condition

pytestmark = pytest.mark.skipif(
    os.getenv("RAMPART_MODEL_TESTS", "") not in ("1", "true", "yes"),
    reason="set RAMPART_MODEL_TESTS=1 to run model-backed policy pins",
)

API = "/api/v1/policies"


@pytest.fixture(autouse=True)
def _require_real_gliner():
    assert pol._GLINER_AVAILABLE, "GLiNER must be importable for these tests"
    from models.pii_detector_gliner import get_gliner_detector
    assert get_gliner_detector().model is not None, "GLiNER model failed to load"


# Semantic PII that has no regex signature: only the model can catch these.
GLINER_ONLY_POSITIVES = [
    "Hi, I'm Sarah Connor and I live at 14 Elm Street, Boise",   # street address
    "Born 03/14/1978, lives alone",                               # date of birth, no "dob"/"patient" keyword
]
# Clean text with digits/keywords that must NOT trip the model.
NEGATIVES = [
    "The quarterly revenue grew twelve percent year over year",
    "Please refactor this function to use async/await",
    "Order #12345 shipped on 2024-03-14 via UPS",
]


@pytest.mark.parametrize("content", GLINER_ONLY_POSITIVES)
def test_contains_pii_detects_semantic_pii(content):
    assert _evaluate_condition("contains_pii", content, {}) is True


@pytest.mark.parametrize("content", NEGATIVES)
def test_contains_pii_clean_text(content):
    assert _evaluate_condition("contains_pii", content, {}) is False


def test_contains_pii_ssn_agrees_with_regex():
    assert _evaluate_condition("contains_pii", "My SSN is 123-45-6789", {}) is True


def test_contains_phi_detects_date_of_birth_without_keywords():
    # No PHI keyword present ("patient", "dob", "diagnosis", ...) — model-only detection
    assert _evaluate_condition("contains_phi", GLINER_ONLY_POSITIVES[1], {}) is True


def test_contains_phi_clean_text():
    assert _evaluate_condition("contains_phi", "The meeting was moved to 03/14 next year", {}) is False


def test_user_policy_redacts_address_via_model(client, auth_headers):
    r = client.post(API, json={
        "name": "Redact PII", "policy_type": "data_governance",
        "rules": [{"condition": "contains_pii", "action": "redact"}],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    hit = client.post(f"{API}/evaluate", json={"content": GLINER_ONLY_POSITIVES[0]}, headers=auth_headers).json()
    assert hit["modified_content"] == "[REDACTED]"
    assert [v["reason"] for v in hit["violations"]] == ["Rule condition 'contains_pii' triggered"]

    miss = client.post(f"{API}/evaluate", json={"content": NEGATIVES[0]}, headers=auth_headers).json()
    assert miss["violations"] == [] and miss["modified_content"] is None


def test_hipaa_template_redacts_dob_via_model(client, auth_headers):
    assert client.post(f"{API}/templates/hipaa", headers=auth_headers).status_code == 201
    result = client.post(f"{API}/evaluate", json={"content": "Born 03/14/1978, lives alone"}, headers=auth_headers).json()
    assert result["modified_content"] == "[REDACTED]"
    assert any("contains_phi" in v["reason"] for v in result["violations"])

import json
from typing import Any, Dict, List

from fastapi.testclient import TestClient

from api.main import app
import api.routes.content_filter as cf


client = TestClient(app)


def test_redaction_uses_label_for_custom_pattern():
    content = "Order ID: ORD-ABC-12345"
    body: Dict[str, Any] = {
        "content": content,
        "filters": ["pii"],
        "redact": True,
        "custom_pii_patterns": {"order_id": r"ORD-[A-Z]{3}-\d{5}"},
    }
    r = client.post("/api/v1/filter", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    # Expect label-based token
    assert data["filtered_content"].find("[ORDER_ID_REDACTED]") != -1
    assert any(e.get("label") == "order_id" for e in data["pii_detected"])  # typed label present


def test_defaults_merge_applies_when_request_omits(monkeypatch):
    # Defaults say redact=True; request omits redact
    def fake_get_default(key: str):
        if key == "content_filter_defaults":
            return {"redact": True}
        return None

    monkeypatch.setattr("api.routes.content_filter.get_default", fake_get_default, raising=False)

    content = "Email me at alice@example.com"
    body = {"content": content, "filters": ["pii"]}
    r = client.post("/api/v1/filter", json=body)
    assert r.status_code == 200
    data = r.json()
    # Because defaults force redact, filtered_content should be present
    assert data["filtered_content"] is not None
    assert "[EMAIL_REDACTED]" in data["filtered_content"]


def test_presidio_path_selected_when_flag_true(monkeypatch):
    # Mock presidio path to avoid heavy initialization
    def fake_detect_pii_presidio(text: str):
        # Return one fake entity and a deterministic redaction string
        entity = cf.PIIEntity(
            type=cf.PIIType.NAME,
            value="X",
            start=0,
            end=1,
            confidence=0.9,
            label="person",
        )
        return [entity.dict()], "[REDACTED_PRESIDIO]"

    monkeypatch.setattr(cf, "detect_pii_presidio", lambda t: (  # type: ignore
        [cf.PIIEntity(type=cf.PIIType.NAME, value="X", start=0, end=1, confidence=0.9, label="person")],
        "[REDACTED_PRESIDIO]",
    ))

    body = {
        "content": "Name: Alice",
        "filters": ["pii"],
        "redact": True,
        "use_presidio_pii": True,
    }
    r = client.post("/api/v1/filter", json=body)
    assert r.status_code == 200
    data = r.json()
    # Since we mocked presidio, ensure its redaction is used
    assert data["filtered_content"] == "[REDACTED_PRESIDIO]"
    assert len(data["pii_detected"]) == 1

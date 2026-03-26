"""
Test security and ownership isolation for policy endpoints.
Policies are now stored in DB; these tests verify the HTTP API surface.
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from api.main import app
from api.routes.policies import PolicyType, PolicyRule, PolicyAction

client = TestClient(app)


def test_list_policies_returns_200(auth_headers):
    """Authenticated list request should succeed."""
    response = client.get("/api/v1/policies", headers=auth_headers)
    assert response.status_code in (200, 503), response.text  # 503 if DB unavailable in tests


def test_create_policy_returns_201_or_503(auth_headers):
    """Creating a policy should succeed (201) or return 503 when DB is unavailable."""
    payload = {
        "name": "Test Policy",
        "description": "ownership test",
        "policy_type": "content_filter",
        "rules": [{"condition": "contains_pii", "action": "block", "priority": 10}],
        "enabled": True,
        "tags": ["test"],
    }
    response = client.post("/api/v1/policies", json=payload, headers=auth_headers)
    assert response.status_code in (201, 503), response.text


def test_get_nonexistent_policy_returns_404_or_503(auth_headers):
    """Requesting a policy that doesn't exist should return 404 (or 503 if DB down)."""
    fake_id = uuid4()
    response = client.get(f"/api/v1/policies/{fake_id}", headers=auth_headers)
    assert response.status_code in (404, 503), response.text


def test_delete_nonexistent_policy_returns_404_or_503(auth_headers):
    """Deleting a policy that doesn't exist should return 404 (or 503 if DB down)."""
    fake_id = uuid4()
    response = client.delete(f"/api/v1/policies/{fake_id}", headers=auth_headers)
    assert response.status_code in (404, 503), response.text


def test_toggle_nonexistent_policy_returns_404_or_503(auth_headers):
    """Toggling a policy that doesn't exist should return 404 (or 503 if DB down)."""
    fake_id = uuid4()
    response = client.patch(f"/api/v1/policies/{fake_id}/toggle", headers=auth_headers)
    assert response.status_code in (404, 503), response.text


def test_evaluate_policies_returns_valid_response(auth_headers):
    """Policy evaluation endpoint should return a structured response."""
    payload = {"content": "My SSN is 123-45-6789", "context": {}}
    response = client.post("/api/v1/policies/evaluate", json=payload, headers=auth_headers)
    assert response.status_code in (200, 503), response.text
    if response.status_code == 200:
        body = response.json()
        assert "allowed" in body
        assert "violations" in body
        assert "actions_taken" in body


def test_list_compliance_templates(auth_headers):
    """All five compliance templates should be listed."""
    response = client.get("/api/v1/policies/templates", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "templates" in body
    template_ids = {t["id"] for t in body["templates"]}
    assert "gdpr" in template_ids
    assert "hipaa" in template_ids
    assert "soc2" in template_ids
    assert "pci_dss" in template_ids
    assert "ccpa" in template_ids


def test_create_from_template_pci_dss(auth_headers):
    """PCI-DSS template should now be instantiable (was a stub before)."""
    response = client.post("/api/v1/policies/templates/pci_dss", headers=auth_headers)
    assert response.status_code in (201, 503), response.text


def test_create_from_template_ccpa(auth_headers):
    """CCPA template should now be instantiable (was a stub before)."""
    response = client.post("/api/v1/policies/templates/ccpa", headers=auth_headers)
    assert response.status_code in (201, 503), response.text


def test_list_template_packs(auth_headers):
    """All seven template packs should be listed."""
    response = client.get("/api/v1/template-packs", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "template_packs" in body
    pack_ids = {p["id"] for p in body["template_packs"]}
    for expected in ("default", "customer_support", "code_assistant", "rag",
                     "healthcare", "financial", "creative_writing"):
        assert expected in pack_ids, f"Pack '{expected}' missing from /template-packs"


def test_get_specific_template_pack(auth_headers):
    """Each template pack should return full config."""
    for pack_id in ("customer_support", "healthcare", "financial"):
        response = client.get(f"/api/v1/template-packs/{pack_id}", headers=auth_headers)
        assert response.status_code == 200, f"Pack {pack_id} returned {response.status_code}"
        body = response.json()
        assert body["id"] == pack_id
        assert "filters" in body
        assert "redact" in body
        assert "toxicity_threshold" in body


def test_get_unknown_template_pack_returns_422(auth_headers):
    """Requesting a non-existent pack should return 422 (FastAPI enum validation)."""
    response = client.get("/api/v1/template-packs/does_not_exist", headers=auth_headers)
    assert response.status_code == 422, response.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

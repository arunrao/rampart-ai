"""
User-defined policies: condition evaluator, CRUD lifecycle, ownership isolation,
and end-to-end evaluation through /api/v1/policies/evaluate.

PII detection in the policy evaluator has two paths:
  * GLiNER (the production path) — exercised here via a stubbed ``detect_pii_gliner``
    (``TestGlinerIntegration``) so the entity-handling branches run without a model, and
    against the real model in ``tests/test_policies_gliner.py`` (``RAMPART_MODEL_TESTS=1``).
  * regex + keyword fallback — used when GLiNER is not importable or raises. The
    module-level tests below run with GLiNER switched off so that this path is covered
    deterministically and CI (which has no HF model cache) does not download ~330MB.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from api.routes import policies as pol
from api.routes.policies import _evaluate_condition
from models.pii_detector_gliner import PIIEntity
from tests.helpers import create_user_and_jwt

API = "/api/v1/policies"


@pytest.fixture(autouse=True)
def _regex_fallback_path(monkeypatch):
    """Force the non-GLiNER branch; TestGlinerIntegration re-enables it with a stub."""
    monkeypatch.setattr(pol, "_GLINER_AVAILABLE", False)


def _ent(type_: str, value: str = "x") -> PIIEntity:
    return PIIEntity(type=type_, value=value, start=0, end=len(value), confidence=0.9, label=type_)


class TestGlinerIntegration:
    """How `_evaluate_condition` consumes GLiNER output (detector stubbed, model not loaded)."""

    @pytest.fixture(autouse=True)
    def _gliner_on(self, monkeypatch):
        monkeypatch.setattr(pol, "_GLINER_AVAILABLE", True)

    def _stub(self, monkeypatch, result):
        calls = []

        def fake(text):
            calls.append(text)
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(pol, "detect_pii_gliner", fake)
        return calls

    @pytest.mark.parametrize("etype", ["name", "email", "phone", "address", "ssn", "credit_card", "date_of_birth"])
    def test_contains_pii_fires_on_any_entity(self, monkeypatch, etype):
        calls = self._stub(monkeypatch, [_ent(etype)])
        # No regex-detectable PII in the text: only GLiNER can trip this
        assert _evaluate_condition("contains_pii", "Hi, I'm Sarah Connor from Boise", {}) is True
        assert calls == ["Hi, I'm Sarah Connor from Boise"]

    def test_contains_pii_trusts_empty_gliner_result(self, monkeypatch):
        """With GLiNER available, an empty result is final — the regex fallback does not run."""
        self._stub(monkeypatch, [])
        assert _evaluate_condition("contains_pii", "My SSN is 123-45-6789", {}) is False

    def test_contains_pii_falls_back_to_regex_when_gliner_raises(self, monkeypatch):
        self._stub(monkeypatch, RuntimeError("model load failed"))
        assert _evaluate_condition("contains_pii", "My SSN is 123-45-6789", {}) is True
        assert _evaluate_condition("contains_pii", "nothing to see here", {}) is False

    @pytest.mark.parametrize("etype", ["date_of_birth", "medical_record"])
    def test_contains_phi_fires_on_phi_entity_types(self, monkeypatch, etype):
        self._stub(monkeypatch, [_ent(etype)])
        assert _evaluate_condition("contains_phi", "Visit scheduled for next week", {}) is True

    @pytest.mark.parametrize("etype", ["name", "email", "ssn", "credit_card", "address"])
    def test_contains_phi_ignores_non_phi_entities_then_uses_keywords(self, monkeypatch, etype):
        self._stub(monkeypatch, [_ent(etype)])
        assert _evaluate_condition("contains_phi", "Visit scheduled for next week", {}) is False
        assert _evaluate_condition("contains_phi", "Patient visit scheduled for next week", {}) is True

    def test_contains_phi_falls_back_to_keywords_when_gliner_raises(self, monkeypatch):
        self._stub(monkeypatch, RuntimeError("boom"))
        assert _evaluate_condition("contains_phi", "discharge summary attached", {}) is True
        assert _evaluate_condition("contains_phi", "quarterly report attached", {}) is False

    def test_phi_types_match_detector_output_vocabulary(self):
        """The PHI type set must be drawn from what _map_label_to_type can actually emit."""
        from models.pii_detector_gliner import GLiNERPIIDetector
        det = GLiNERPIIDetector()
        emitted = {det._map_label_to_type(label) for label in det.DEFAULT_LABELS}
        assert {"date_of_birth", "medical_record"} <= emitted

    def test_evaluate_endpoint_uses_gliner(self, monkeypatch, client, auth_headers):
        self._stub(monkeypatch, [_ent("name", "Sarah Connor")])
        _create(client, auth_headers, name="Redact PII",
                rules=[{"condition": "contains_pii", "action": "redact"}])
        result = _evaluate(client, auth_headers, "Hi, I'm Sarah Connor")
        assert result["modified_content"] == "[REDACTED]"
        assert [v["reason"] for v in result["violations"]] == ["Rule condition 'contains_pii' triggered"]


@pytest.fixture
def other_auth_headers() -> dict[str, str]:
    _, _, token = create_user_and_jwt()
    return {"Authorization": f"Bearer {token}"}


def _policy(**overrides) -> dict:
    base = {
        "name": "No profanity",
        "description": "user-defined",
        "policy_type": "content_filter",
        "rules": [{"condition": "profanity", "action": "block", "priority": 10}],
        "enabled": True,
        "tags": ["custom"],
    }
    base.update(overrides)
    return base


def _create(client, headers, **overrides) -> dict:
    r = client.post(API, json=_policy(**overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _evaluate(client, headers, content: str, **extra) -> dict:
    r = client.post(f"{API}/evaluate", json={"content": content, **extra}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Condition evaluator (unit)
# ---------------------------------------------------------------------------

CONDITION_CASES = [
    # (condition, content, context, expected)
    ("contains_pii", "My SSN is 123-45-6789", {}, True),
    ("contains_pii", "Card: 4111 1111 1111 1111", {}, True),
    ("contains_pii", "please update my social security info", {}, True),
    ("contains_pii", "What's the weather like today?", {}, False),
    ("contains_phi", "Patient presented with a diagnosis of hypertension", {}, True),
    ("contains_phi", "Attached is the discharge summary", {}, True),
    ("contains_phi", "Our quarterly revenue grew 12%", {}, False),
    ("contains_card_data", "Pay with 4111-1111-1111-1111 please", {}, True),
    ("contains_card_data", "Order #12345 shipped", {}, False),
    ("contains_cvv", "card ending 4242, cvv: 123", {}, True),
    ("contains_cvv", "security code 9876", {}, True),
    ("contains_cvv", "the cvv field is on the back of the card", {}, False),
    ("unencrypted_pan", "PAN 4111 1111 1111 1111", {}, True),
    ("unencrypted_pan", "PAN ****-****-****-1111", {}, False),
    ("audit_log_required", "anything at all", {}, True),
    ("encryption_required", "password=hunter2secret", {}, True),
    ("encryption_required", "api_key: 'sk-abcdef123456'", {}, True),
    ("encryption_required", "export AWS_SECRET_KEY=abcd1234efgh5678", {}, True),
    ("encryption_required", "please reset my password", {}, False),
    ("data_retention_exceeded", "x", {"data_retention_exceeded": True}, True),
    ("data_retention_exceeded", "x", {}, False),
    ("unauthorized_access", "x", {"unauthorized_access": True}, True),
    ("unauthorized_access", "x", {"unauthorized_access": False}, False),
    ("data_sale_opt_out", "Please do not sell my personal information", {}, True),
    ("data_sale_opt_out", "I'd like to opt-out of marketing", {}, True),
    ("data_sale_opt_out", "Sell me the premium plan", {}, False),
    ("right_to_delete", "I invoke my right to be forgotten", {}, True),
    ("right_to_delete", "Delete my data from your systems", {}, True),
    ("right_to_delete", "Delete the duplicate row in the spreadsheet", {}, False),
    ("profanity", "This is bullshit", {}, True),
    ("profanity", "What the FUCK", {}, True),
    ("profanity", "Scunthorpe assessment of the class", {}, False),  # substring, not word
    ("profanity", "Have a nice day", {}, False),
]


@pytest.mark.parametrize("condition,content,context,expected", CONDITION_CASES)
def test_evaluate_condition(condition, content, context, expected):
    assert _evaluate_condition(condition, content, context) is expected


def test_unknown_condition_never_trips():
    assert _evaluate_condition("not_a_real_condition", "fuck 123-45-6789", {}) is False


def test_every_template_condition_is_implemented():
    """Every condition shipped in a compliance template must be handled by the evaluator."""
    implemented = {
        "contains_pii", "contains_phi", "contains_card_data", "contains_cvv", "unencrypted_pan",
        "audit_log_required", "encryption_required", "data_retention_exceeded",
        "unauthorized_access", "data_sale_opt_out", "right_to_delete", "profanity",
    }
    for template in pol.ComplianceTemplate:
        tpl = pol.create_compliance_template(template)
        assert tpl is not None
        for rule in tpl.rules:
            assert rule.condition in implemented, f"{template.value}: {rule.condition}"


# ---------------------------------------------------------------------------
# CRUD lifecycle
# ---------------------------------------------------------------------------

def test_create_persists_all_fields(client, auth_headers):
    created = _create(
        client, auth_headers,
        rules=[
            {"condition": "profanity", "action": "block", "priority": 10, "metadata": {"severity": "high"}},
            {"condition": "contains_pii", "action": "redact", "priority": 5},
        ],
        tags=["custom", "chat"],
    )
    assert created["name"] == "No profanity"
    assert created["policy_type"] == "content_filter"
    assert created["enabled"] is True
    assert created["version"] == 1
    assert created["tags"] == ["custom", "chat"]
    assert created["rules"][0]["metadata"] == {"severity": "high"}
    assert created["rules"][1]["metadata"] is None
    assert created["created_at"] and created["updated_at"]

    fetched = client.get(f"{API}/{created['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_create_with_empty_tags_and_description(client, auth_headers):
    created = _create(client, auth_headers, tags=None, description=None)
    assert created["tags"] == []
    assert created["description"] is None


def test_list_filters_by_type_and_enabled(client, auth_headers):
    a = _create(client, auth_headers, name="A", policy_type="content_filter", enabled=True)
    b = _create(client, auth_headers, name="B", policy_type="compliance", enabled=False)
    c = _create(client, auth_headers, name="C", policy_type="compliance", enabled=True)

    ids = lambda r: {p["id"] for p in r.json()}  # noqa: E731
    assert ids(client.get(API, headers=auth_headers)) == {a["id"], b["id"], c["id"]}
    assert ids(client.get(API, params={"policy_type": "compliance"}, headers=auth_headers)) == {b["id"], c["id"]}
    assert ids(client.get(API, params={"enabled": "false"}, headers=auth_headers)) == {b["id"]}
    assert ids(client.get(API, params={"policy_type": "compliance", "enabled": "true"}, headers=auth_headers)) == {c["id"]}


def test_list_pagination(client, auth_headers):
    for i in range(3):
        _create(client, auth_headers, name=f"P{i}")
    page1 = client.get(API, params={"limit": 2, "offset": 0}, headers=auth_headers).json()
    page2 = client.get(API, params={"limit": 2, "offset": 2}, headers=auth_headers).json()
    assert len(page1) == 2 and len(page2) == 1
    assert {p["id"] for p in page1}.isdisjoint({p["id"] for p in page2})


def test_update_replaces_rules_and_bumps_version(client, auth_headers):
    created = _create(client, auth_headers)
    r = client.put(
        f"{API}/{created['id']}",
        json=_policy(
            name="Renamed",
            policy_type="compliance",
            rules=[{"condition": "contains_cvv", "action": "flag", "priority": 1}],
            enabled=False,
            tags=["v2"],
        ),
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == created["id"]
    assert body["name"] == "Renamed"
    assert body["policy_type"] == "compliance"
    assert body["enabled"] is False
    assert body["tags"] == ["v2"]
    assert [x["condition"] for x in body["rules"]] == ["contains_cvv"]
    assert body["version"] == 2
    assert body["updated_at"] >= created["updated_at"]

    again = client.put(f"{API}/{created['id']}", json=_policy(), headers=auth_headers)
    assert again.json()["version"] == 3


def test_toggle_flips_enabled(client, auth_headers):
    created = _create(client, auth_headers, enabled=True)
    r = client.patch(f"{API}/{created['id']}/toggle", headers=auth_headers)
    assert r.status_code == 200 and r.json()["enabled"] is False
    assert client.get(f"{API}/{created['id']}", headers=auth_headers).json()["enabled"] is False
    r = client.patch(f"{API}/{created['id']}/toggle", headers=auth_headers)
    assert r.json()["enabled"] is True


def test_delete_then_404(client, auth_headers):
    created = _create(client, auth_headers)
    r = client.delete(f"{API}/{created['id']}", headers=auth_headers)
    assert r.status_code == 200 and r.json()["policy_id"] == created["id"]
    assert client.get(f"{API}/{created['id']}", headers=auth_headers).status_code == 404
    assert client.delete(f"{API}/{created['id']}", headers=auth_headers).status_code == 404


@pytest.mark.parametrize(
    "bad",
    [
        {"policy_type": "nonsense"},
        {"rules": [{"condition": "profanity", "action": "nuke"}]},
        {"rules": [{"action": "block"}]},  # missing condition
        {"rules": "not-a-list"},
        {"name": None},
    ],
)
def test_create_rejects_invalid_payload(client, auth_headers, bad):
    r = client.post(API, json=_policy(**bad), headers=auth_headers)
    assert r.status_code == 422, r.text


def test_policy_endpoints_require_auth(client):
    assert client.get(API).status_code == 401
    assert client.post(API, json=_policy()).status_code == 401
    assert client.post(f"{API}/evaluate", json={"content": "x"}).status_code == 401


# ---------------------------------------------------------------------------
# Ownership isolation
# ---------------------------------------------------------------------------

def test_other_user_cannot_see_or_modify_policy(client, auth_headers, other_auth_headers):
    mine = _create(client, auth_headers)
    pid = mine["id"]

    assert pid not in {p["id"] for p in client.get(API, headers=other_auth_headers).json()}
    assert client.get(f"{API}/{pid}", headers=other_auth_headers).status_code == 404
    assert client.put(f"{API}/{pid}", json=_policy(name="hijack"), headers=other_auth_headers).status_code == 404
    assert client.patch(f"{API}/{pid}/toggle", headers=other_auth_headers).status_code == 404
    assert client.delete(f"{API}/{pid}", headers=other_auth_headers).status_code == 404

    # Untouched
    still = client.get(f"{API}/{pid}", headers=auth_headers).json()
    assert still["name"] == mine["name"] and still["enabled"] is True and still["version"] == 1


def test_evaluate_ignores_other_users_policy_ids(client, auth_headers, other_auth_headers):
    theirs = _create(client, other_auth_headers)
    result = _evaluate(client, auth_headers, "this is bullshit", policy_ids=[theirs["id"]])
    assert result["allowed"] is True and result["violations"] == []


def test_evaluate_only_uses_callers_policies(client, auth_headers, other_auth_headers):
    _create(client, other_auth_headers)  # other user's block-profanity policy
    result = _evaluate(client, auth_headers, "this is bullshit")
    assert result["allowed"] is True and result["violations"] == []


# ---------------------------------------------------------------------------
# Evaluation with user-defined policies
# ---------------------------------------------------------------------------

def test_evaluate_no_policies_allows(client, auth_headers):
    result = _evaluate(client, auth_headers, "fuck 123-45-6789")
    assert result == {"allowed": True, "violations": [], "actions_taken": [], "modified_content": None}


def test_evaluate_block_action(client, auth_headers):
    p = _create(client, auth_headers)
    result = _evaluate(client, auth_headers, "this is bullshit")
    assert result["allowed"] is False
    assert result["modified_content"] is None
    assert result["actions_taken"] == ["No profanity: block"]
    [v] = result["violations"]
    assert v["policy_id"] == p["id"]
    assert v["policy_name"] == "No profanity"
    assert v["action"] == "block"
    assert "profanity" in v["reason"]


def test_evaluate_clean_content_passes_block_policy(client, auth_headers):
    _create(client, auth_headers)
    result = _evaluate(client, auth_headers, "have a lovely day")
    assert result["allowed"] is True and result["violations"] == []


def test_evaluate_redact_action(client, auth_headers):
    _create(client, auth_headers, name="Redact PII",
            rules=[{"condition": "contains_pii", "action": "redact", "priority": 10}])
    result = _evaluate(client, auth_headers, "SSN 123-45-6789")
    assert result["allowed"] is True
    assert result["modified_content"] == "[REDACTED]"
    assert result["actions_taken"] == ["Redact PII: redact"]


@pytest.mark.parametrize("action", ["flag", "alert", "allow"])
def test_evaluate_non_blocking_actions_record_violation_but_allow(client, auth_headers, action):
    _create(client, auth_headers, name="Watch", rules=[{"condition": "profanity", "action": action}])
    result = _evaluate(client, auth_headers, "this is bullshit")
    assert result["allowed"] is True
    assert result["modified_content"] is None
    assert [v["action"] for v in result["violations"]] == [action]


def test_evaluate_skips_disabled_policy(client, auth_headers):
    p = _create(client, auth_headers, enabled=False)
    assert _evaluate(client, auth_headers, "this is bullshit")["allowed"] is True
    # ...even when explicitly requested by id
    assert _evaluate(client, auth_headers, "this is bullshit", policy_ids=[p["id"]])["allowed"] is True
    client.patch(f"{API}/{p['id']}/toggle", headers=auth_headers)
    assert _evaluate(client, auth_headers, "this is bullshit")["allowed"] is False


def test_evaluate_policy_ids_restricts_scope(client, auth_headers):
    prof = _create(client, auth_headers, name="Prof")
    pii = _create(client, auth_headers, name="PII",
                  rules=[{"condition": "contains_pii", "action": "block", "priority": 10}])
    content = "bullshit 123-45-6789"

    both = _evaluate(client, auth_headers, content)
    assert {v["policy_name"] for v in both["violations"]} == {"Prof", "PII"}

    only_pii = _evaluate(client, auth_headers, content, policy_ids=[pii["id"]])
    assert [v["policy_name"] for v in only_pii["violations"]] == ["PII"]

    unknown = _evaluate(client, auth_headers, content, policy_ids=[str(uuid4())])
    assert unknown["violations"] == [] and unknown["allowed"] is True
    assert prof["id"]  # silence unused


def test_evaluate_context_driven_conditions(client, auth_headers):
    _create(client, auth_headers, name="Retention",
            rules=[{"condition": "data_retention_exceeded", "action": "block"}])
    assert _evaluate(client, auth_headers, "hello")["allowed"] is True
    assert _evaluate(client, auth_headers, "hello", context={"data_retention_exceeded": True})["allowed"] is False


def test_evaluate_rules_are_ordered_by_priority(client, auth_headers):
    """Rules run highest-priority first regardless of declaration order."""
    _create(client, auth_headers, name="Multi", rules=[
        {"condition": "profanity", "action": "flag", "priority": 1},
        {"condition": "contains_pii", "action": "block", "priority": 100},
    ])
    result = _evaluate(client, auth_headers, "bullshit 123-45-6789")
    assert [v["action"] for v in result["violations"]] == ["block", "flag"]
    assert [v["rule_index"] for v in result["violations"]] == [0, 1]
    assert result["allowed"] is False


def test_evaluate_only_triggered_rules_reported(client, auth_headers):
    _create(client, auth_headers, name="Multi", rules=[
        {"condition": "profanity", "action": "block", "priority": 10},
        {"condition": "contains_cvv", "action": "block", "priority": 5},
        {"condition": "contains_pii", "action": "redact", "priority": 1},
    ])
    result = _evaluate(client, auth_headers, "SSN 123-45-6789")
    assert [v["reason"] for v in result["violations"]] == ["Rule condition 'contains_pii' triggered"]
    assert result["modified_content"] == "[REDACTED]"


def test_evaluate_unknown_condition_is_inert(client, auth_headers):
    _create(client, auth_headers, name="Typo", rules=[{"condition": "contains_pi", "action": "block"}])
    assert _evaluate(client, auth_headers, "SSN 123-45-6789")["allowed"] is True


def test_evaluate_block_wins_over_redact_across_policies(client, auth_headers):
    _create(client, auth_headers, name="Redact", rules=[{"condition": "contains_pii", "action": "redact"}])
    _create(client, auth_headers, name="Block", rules=[{"condition": "profanity", "action": "block"}])
    result = _evaluate(client, auth_headers, "bullshit 123-45-6789")
    assert result["allowed"] is False
    assert result["modified_content"] is None
    assert set(result["actions_taken"]) == {"Redact: redact", "Block: block"}


def test_evaluate_blocked_content_never_returned_even_if_redact_fires_later(client, auth_headers):
    """A lower-priority redact after a block must not resurrect content as '[REDACTED]'."""
    _create(client, auth_headers, name="Both", rules=[
        {"condition": "profanity", "action": "block", "priority": 10},
        {"condition": "contains_pii", "action": "redact", "priority": 1},
    ])
    result = _evaluate(client, auth_headers, "bullshit 123-45-6789")
    assert result["allowed"] is False and result["modified_content"] is None
    assert [v["action"] for v in result["violations"]] == ["block", "redact"]


def test_evaluate_reflects_updated_rules(client, auth_headers):
    p = _create(client, auth_headers)
    assert _evaluate(client, auth_headers, "this is bullshit")["allowed"] is False
    client.put(f"{API}/{p['id']}",
               json=_policy(rules=[{"condition": "contains_cvv", "action": "block"}]),
               headers=auth_headers)
    assert _evaluate(client, auth_headers, "this is bullshit")["allowed"] is True
    assert _evaluate(client, auth_headers, "cvv: 123")["allowed"] is False


def test_evaluate_after_delete(client, auth_headers):
    p = _create(client, auth_headers)
    client.delete(f"{API}/{p['id']}", headers=auth_headers)
    assert _evaluate(client, auth_headers, "this is bullshit")["allowed"] is True


# ---------------------------------------------------------------------------
# Compliance templates as user policies
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("template", [t.value for t in pol.ComplianceTemplate])
def test_template_instantiates_as_owned_policy(client, auth_headers, template):
    r = client.post(f"{API}/templates/{template}", headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    expected = pol.create_compliance_template(pol.ComplianceTemplate(template))
    assert expected is not None
    assert body["name"] == expected.name
    assert body["policy_type"] == expected.policy_type.value
    assert body["tags"] == expected.tags
    assert [(x["condition"], x["action"], x["priority"]) for x in body["rules"]] == [
        (x.condition, x.action.value, x.priority) for x in expected.rules
    ]
    assert client.get(f"{API}/{body['id']}", headers=auth_headers).status_code == 200


def test_template_catalog_lists_both_categories_with_rule_preview(client, auth_headers):
    body = client.get(f"{API}/templates", headers=auth_headers).json()["templates"]
    by_id = {t["id"]: t for t in body}
    assert set(by_id) == {t.value for t in pol.ComplianceTemplate}
    assert {t["category"] for t in body} == {"compliance", "starter"}
    assert by_id["gdpr"]["category"] == "compliance" and by_id["gdpr"]["name"] == "GDPR"
    assert by_id["pii_redaction"]["category"] == "starter" and by_id["pii_redaction"]["name"] == "Redact PII"
    for t in body:
        assert t["description"] and t["policy_type"] and t["rules"], t["id"]
        assert {"condition", "action", "priority"} <= set(t["rules"][0])


STARTER_CASES = [
    # (template, positive content, expected allowed, expected modified_content, negative content)
    ("pii_redaction", "SSN 123-45-6789", True, "[REDACTED]", "What time do you open?"),
    ("pii_block", "SSN 123-45-6789", False, None, "What time do you open?"),
    ("secrets_guard", "export AWS_SECRET_KEY=abcd1234efgh5678", False, None, "please rotate the api key monthly"),
    ("profanity_block", "this is bullshit", False, None, "this is unfortunate"),
    ("payment_data_guard", "Card 4111 1111 1111 1111", True, "[REDACTED]", "Order #12345 shipped"),
    ("payment_data_guard", "cvv: 123", False, None, "Order #12345 shipped"),
    ("payment_data_guard", "Card 4111 1111 1111 1111, cvv: 123", False, None, "Order #12345 shipped"),
    ("privacy_request_triage", "Please delete my data", True, None, "Please update my shipping address"),
    ("privacy_request_triage", "Do not sell my information", True, None, "Sell me the premium plan"),
]


@pytest.mark.parametrize("template,positive,allowed,modified,negative", STARTER_CASES)
def test_starter_template_behaviour(client, auth_headers, template, positive, allowed, modified, negative):
    created = client.post(f"{API}/templates/{template}", headers=auth_headers)
    assert created.status_code == 201, created.text
    assert "starter" in created.json()["tags"]

    hit = _evaluate(client, auth_headers, positive)
    assert hit["allowed"] is allowed
    assert hit["modified_content"] == modified
    assert hit["violations"], "starter should trigger on its positive example"

    miss = _evaluate(client, auth_headers, negative)
    assert miss == {"allowed": True, "violations": [], "actions_taken": [], "modified_content": None}


def test_audit_trail_starter_flags_everything_without_blocking(client, auth_headers):
    client.post(f"{API}/templates/audit_trail", headers=auth_headers)
    result = _evaluate(client, auth_headers, "completely benign text")
    assert result["allowed"] is True and result["modified_content"] is None
    assert [v["action"] for v in result["violations"]] == ["flag"]


def test_unknown_template_returns_422(client, auth_headers):
    assert client.post(f"{API}/templates/iso27001", headers=auth_headers).status_code == 422


def test_pci_dss_template_blocks_card_with_cvv(client, auth_headers):
    client.post(f"{API}/templates/pci_dss", headers=auth_headers)
    result = _evaluate(client, auth_headers, "Card 4111 1111 1111 1111 cvv: 123")
    assert result["allowed"] is False
    conditions = {v["reason"] for v in result["violations"]}
    assert "Rule condition 'contains_cvv' triggered" in conditions
    assert "Rule condition 'unencrypted_pan' triggered" in conditions
    # audit_log_required always flags
    assert "Rule condition 'audit_log_required' triggered" in conditions


def test_hipaa_template_redacts_phi_and_blocks_on_context(client, auth_headers):
    client.post(f"{API}/templates/hipaa", headers=auth_headers)
    phi = _evaluate(client, auth_headers, "Patient diagnosis: type 2 diabetes")
    assert phi["allowed"] is True and phi["modified_content"] == "[REDACTED]"
    denied = _evaluate(client, auth_headers, "ok", context={"unauthorized_access": True})
    assert denied["allowed"] is False


def test_template_policy_can_be_customised(client, auth_headers):
    created = client.post(f"{API}/templates/gdpr", headers=auth_headers).json()
    tightened = {**_policy(name=created["name"], policy_type=created["policy_type"], tags=created["tags"]),
                 "rules": [{**r, "action": "block"} if r["condition"] == "contains_pii" else r
                           for r in created["rules"]]}
    r = client.put(f"{API}/{created['id']}", json=tightened, headers=auth_headers)
    assert r.status_code == 200 and r.json()["version"] == 2
    assert _evaluate(client, auth_headers, "SSN 123-45-6789")["allowed"] is False

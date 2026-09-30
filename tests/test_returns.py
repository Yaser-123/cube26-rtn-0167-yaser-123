"""Offline tests: the model call is mocked, so these cost nothing. Run: python -m pytest tests -q"""
import os
import tempfile

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ["RTN_CACHE_DIR"] = tempfile.mkdtemp()
os.environ["RTN_ACCOUNTS_FILE"] = os.path.join(tempfile.mkdtemp(), "accounts.json")
os.environ["RTN_API_KEYS"] = "k-alpha:org_demo_alpha,k-bravo:org_demo_bravo"

import pytest
from fastapi.testclient import TestClient
from src import main
from src import agent as agent_module
from src.agent import decide_disposition
from src.models import compute_content_hash

IMAGE = "test_images/test_used_bottle_1790418109421.jpg"

GOOD_RESULT = {
    "observed": "A steel bottle with lid, light scuffs.", "observed_state": "signs_of_use",
    "identity_verdict": "PASS", "identity_confidence": 0.9, "identity_detail": "Bottle matches SKU.",
    "completeness_verdict": "PASS", "parts_missing": [], "completeness_confidence": 0.9, "completeness_detail": "Bottle and lid present.",
    "condition_verdict": "PASS", "condition_grade": "Used - Good", "condition_confidence": 0.8, "condition_detail": "Light scuffs.",
}


def payload(org, unit="UNIT-0018", image=IMAGE):
    return {"unit_id": unit, "organization_id": org, "operator_label": "op_test", "order_id": "ORD-1",
            "ordered_sku": "SKU-BOTTLE-750", "parts_list": "bottle;lid", "photo_refs": [image]}


@pytest.fixture
def client(monkeypatch):
    main.records_db.clear()
    for f in agent_module.CACHE_DIR.glob("*.json"):
        f.unlink()
    calls = []

    def fake_call(images, request):
        calls.append(request.unit_id)
        return dict(GOOD_RESULT), {"model": "mock", "input_tokens": 1000, "output_tokens": 200, "cost_usd": 0.008, "cached": False}

    monkeypatch.setattr(main.agent, "_call_model", fake_call)
    c = TestClient(main.app)
    c.calls = calls
    return c


def test_process_produces_contract_record(client):
    r = client.post("/api/v1/returns/process", json=payload("org_demo_alpha"), headers={"x-org-id": "org_demo_alpha"})
    assert r.status_code == 200
    rec = r.json()
    for field in ("record_id", "schema_version", "organization_id", "client_id", "agent", "subject", "captured_at",
                  "operator_label", "images", "checks", "outcome", "overrides", "status", "content_hash"):
        assert field in rec
    assert [c["check_key"] for c in rec["checks"]] == ["identity", "completeness", "condition"]
    assert rec["outcome"] == "refurbish"


def test_tenant_mismatch_rejected(client):
    r = client.post("/api/v1/returns/process", json=payload("org_demo_alpha"), headers={"x-org-id": "org_demo_bravo"})
    assert r.status_code == 403


def test_second_org_sees_zero_rows_and_cannot_guess_ids(client):
    rec = client.post("/api/v1/returns/process", json=payload("org_demo_alpha"), headers={"x-org-id": "org_demo_alpha"}).json()
    assert client.get("/api/v1/returns", headers={"x-org-id": "org_demo_bravo"}).json() == []
    assert client.get(f"/api/v1/returns/{rec['record_id']}", headers={"x-org-id": "org_demo_bravo"}).status_code == 404
    override = {"revised_verdict": "dispose", "reason": "cross-tenant attempt"}
    assert client.post(f"/api/v1/returns/{rec['record_id']}/override", json=override,
                       headers={"x-org-id": "org_demo_bravo"}).status_code == 404
    assert len(client.get("/api/v1/returns", headers={"x-org-id": "org_demo_alpha"}).json()) == 1


def test_uploaded_images_not_stored_raw(client):
    import base64
    with open(IMAGE, "rb") as f:
        data_url = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    rec = client.post("/api/v1/returns/process", json=payload("org_demo_alpha", image=data_url),
                      headers={"x-org-id": "org_demo_alpha"}).json()
    assert rec["images"][0].startswith("upload:sha256:")


def test_fail_open_on_model_error(client, monkeypatch):
    def boom(images, request):
        raise RuntimeError("upstream down")
    monkeypatch.setattr(main.agent, "_call_model", boom)
    r = client.post("/api/v1/returns/process", json=payload("org_demo_alpha", unit="UNIT-FAIL"), headers={"x-org-id": "org_demo_alpha"})
    assert r.status_code == 200
    rec = r.json()
    assert rec["outcome"] == "pending_review" and rec["status"] == "pending"
    assert all(c["verdict"] == "UNCERTAIN" for c in rec["checks"])
    # The capture is kept, not discarded
    assert client.get(f"/api/v1/returns/{rec['record_id']}", headers={"x-org-id": "org_demo_alpha"}).status_code == 200


def test_unreadable_image_skips_model(client):
    rec = client.post("/api/v1/returns/process", json=payload("org_demo_alpha", image="missing/nope.jpg"),
                      headers={"x-org-id": "org_demo_alpha"}).json()
    assert rec["outcome"] == "pending_review"
    assert client.calls == []


def test_identical_resubmission_hits_cache(client):
    for _ in range(3):
        client.post("/api/v1/returns/process", json=payload("org_demo_alpha", unit="UNIT-CACHE"), headers={"x-org-id": "org_demo_alpha"})
    assert client.calls.count("UNIT-CACHE") == 1


def test_override_appends_and_rehashes(client):
    rec = client.post("/api/v1/returns/process", json=payload("org_demo_alpha", unit="UNIT-OVR"), headers={"x-org-id": "org_demo_alpha"}).json()
    r = client.post(f"/api/v1/returns/{rec['record_id']}/override",
                    json={"revised_verdict": "restock", "reason": "Scuff wipes off"}, headers={"x-org-id": "org_demo_alpha"})
    new = r.json()
    assert new["overrides"][0]["original_verdict"] == rec["outcome"]
    assert new["overrides"][0]["revised_verdict"] == "restock"
    assert new["checks"] == rec["checks"]
    assert new["content_hash"] != rec["content_hash"]
    assert new["content_hash"] == compute_content_hash(main.records_db["org_demo_alpha"][rec["record_id"]])


def test_batch_endpoint(client):
    body = {"requests": [payload("org_demo_alpha", unit=f"UNIT-B{i}") for i in range(3)]}
    r = client.post("/api/v1/returns/process-batch", json=body, headers={"x-org-id": "org_demo_alpha"})
    assert r.status_code == 200 and len(r.json()) == 3
    body["requests"].append(payload("org_demo_bravo", unit="UNIT-X"))
    assert client.post("/api/v1/returns/process-batch", json=body, headers={"x-org-id": "org_demo_alpha"}).status_code == 403


@pytest.mark.parametrize("identity,completeness,condition,grade,expected", [
    ("PASS", "PASS", "PASS", "New", "restock"),
    ("PASS", "PASS", "PASS", "Used - Like New", "restock"),
    ("PASS", "PASS", "PASS", "Used - Good", "refurbish"),
    ("PASS", "PASS", "PASS", "Used - Acceptable", "liquidate"),
    ("PASS", "PASS", "FAIL", "Unacceptable", "dispose"),
    ("PASS", "FAIL", "PASS", "Used - Very Good", "refurbish"),
    ("PASS", "FAIL", "PASS", "Used - Acceptable", "liquidate"),
    ("FAIL", "PASS", "PASS", "New", "pending_review"),
    ("UNCERTAIN", "UNCERTAIN", "UNCERTAIN", "Not gradable", "pending_review"),
    ("PASS", "UNCERTAIN", "PASS", "New", "pending_review"),
])
def test_disposition_policy(identity, completeness, condition, grade, expected):
    assert decide_disposition(identity, completeness, condition, grade) == expected


def test_agent_alias_endpoint(client):
    r = client.post("/agent", json=payload("org_demo_alpha", unit="UNIT-AGENT"), headers={"x-org-id": "org_demo_alpha"})
    assert r.status_code == 200 and r.json()["subject"] == "UNIT-AGENT"


@pytest.mark.parametrize("field,value", [("unit_id", ""), ("unit_id", "../etc"), ("ordered_sku", "  "), ("parts_list", "")])
def test_invalid_identifiers_rejected(client, field, value):
    body = payload("org_demo_alpha")
    body[field] = value
    assert client.post("/api/v1/returns/process", json=body, headers={"x-org-id": "org_demo_alpha"}).status_code == 422


def test_unknown_sku_cannot_pass_identity(client):
    body = payload("org_demo_alpha", unit="UNIT-UNK")
    body["ordered_sku"] = "SKU-NOT-IN-CATALOGUE"
    rec = client.post("/api/v1/returns/process", json=body, headers={"x-org-id": "org_demo_alpha"}).json()
    assert rec["checks"][0]["verdict"] == "UNCERTAIN"
    assert rec["outcome"] == "pending_review"


def test_labelling_keeps_labellers_independent(client, tmp_path, monkeypatch):
    import base64
    from src import eval_api
    monkeypatch.setattr(eval_api, "LABELS", tmp_path / "labels.csv")
    monkeypatch.setattr(eval_api, "IMAGES", tmp_path / "images")
    with open(IMAGE, "rb") as f:
        data_url = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    unit_id = client.post("/api/v1/eval/units", json={"ordered_sku": "SKU-BOTTLE-750", "parts_list": "bottle;lid",
                                                       "images": [data_url]}).json()["unit_id"]
    labels = {"identity": "PASS", "completeness": "PASS", "condition": "PASS", "disposition": "refurbish"}
    assert client.put(f"/api/v1/eval/units/{unit_id}/labels", json={"labeller": "a", **labels}).status_code == 200
    a_view = client.get("/api/v1/eval/units?labeller=a").json()[0]["labels"]
    b_view = client.get("/api/v1/eval/units?labeller=b").json()[0]["labels"]
    assert a_view["disposition"] == "refurbish"
    assert all(v == "" for v in b_view.values())


def test_eval_image_endpoint_refuses_paths_outside_fixtures(client, tmp_path, monkeypatch):
    from src import eval_api
    labels = tmp_path / "labels.csv"
    labels.write_text("unit_id,org_id,ordered_sku,parts_list,photo_refs\nEVAL-900,org_demo_alpha,SKU-X,x,.env\n")
    monkeypatch.setattr(eval_api, "LABELS", labels)
    assert client.get("/api/v1/eval/units/EVAL-900/images/0").status_code == 404


def _files(n=1, content_type="image/jpeg"):
    data = open(IMAGE, "rb").read()
    return [("images", (f"p{i}.jpg", data, content_type)) for i in range(n)]


def test_public_api_requires_key(client):
    assert client.post("/api/v1/inspect", data={"sku": "SKU-BOTTLE-750"}, files=_files()).status_code == 401
    assert client.post("/api/v1/inspect", data={"sku": "SKU-BOTTLE-750"}, files=_files(),
                       headers={"x-api-key": "wrong"}).status_code == 401


def test_public_api_inspects_and_scopes_to_key_tenant(client):
    r = client.post("/api/v1/inspect", data={"sku": "sku-bottle-750"}, files=_files(2), headers={"x-api-key": "k-alpha"})
    assert r.status_code == 200
    rec = r.json()
    assert rec["organization_id"] == "org_demo_alpha" and rec["outcome"] == "refurbish"
    assert rec["subject"].startswith("API-")
    assert len(client.get("/api/v1/returns", headers={"x-org-id": "org_demo_alpha"}).json()) == 1
    assert client.get("/api/v1/returns", headers={"x-org-id": "org_demo_bravo"}).json() == []


def test_public_api_validates_uploads(client):
    h = {"x-api-key": "k-alpha"}
    assert client.post("/api/v1/inspect", data={"sku": "SKU-BOTTLE-750"}, files=_files(4), headers=h).status_code == 400
    assert client.post("/api/v1/inspect", data={"sku": "SKU-BOTTLE-750"}, files=_files(1, "text/plain"), headers=h).status_code == 415
    # Unknown SKU needs explicit parts
    assert client.post("/api/v1/inspect", data={"sku": "SKU-NEW"}, files=_files(), headers=h).status_code == 400


def test_public_api_rate_limit(client, monkeypatch):
    from src import public_api
    monkeypatch.setattr(public_api, "RATE_LIMIT_PER_HOUR", 2)
    main.public_api.api._hits.clear()
    h = {"x-api-key": "k-bravo"}
    codes = [client.post("/api/v1/inspect", data={"sku": "SKU-BOTTLE-750"}, files=_files(), headers=h).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_daily_budget_cap_fails_open(client, monkeypatch):
    monkeypatch.setattr(agent_module, "DAILY_CALL_CAP", 0)
    main.agent._budget_day = None
    rec = client.post("/api/v1/returns/process", json=payload("org_demo_alpha", unit="UNIT-CAP"), headers={"x-org-id": "org_demo_alpha"}).json()
    assert rec["outcome"] == "pending_review"
    assert "Daily limit" in rec["checks"][0]["detail"]
    assert client.calls == []


def test_catalog_endpoint(client):
    items = client.get("/api/v1/catalog").json()
    assert any(i["sku"] == "SKU-BOTTLE-750" and i["parts"] == "bottle;lid" for i in items)


def test_unknown_account_rejected(client):
    assert client.get("/api/v1/returns", headers={"x-org-id": "org_made_up"}).status_code == 403
    assert client.post("/api/v1/returns/process", json=payload("org_made_up"), headers={"x-org-id": "org_made_up"}).status_code == 403


def test_order_lookup_is_scoped_to_account(client):
    r = client.get("/api/v1/orders/unit-0018", headers={"x-org-id": "org_demo_bravo"})
    assert r.status_code == 200 and r.json()["ordered_sku"] == "SKU-BOTTLE-750" and r.json()["parts_list"] == "bottle;lid"
    # UNIT-0018 belongs to bravo: alpha gets the same 404 as a unit that doesn't exist
    assert client.get("/api/v1/orders/UNIT-0018", headers={"x-org-id": "org_demo_alpha"}).status_code == 404
    assert client.get("/api/v1/orders/UNIT-9999", headers={"x-org-id": "org_demo_alpha"}).status_code == 404


def test_new_account_is_isolated_and_gets_working_api_key(client):
    acct = client.post("/api/v1/accounts", json={"name": "Sunrise Home"}).json()
    assert acct["org_id"].startswith("org_sunrise_home_") and acct["api_key"].startswith("rtn_")
    listed = client.get("/api/v1/accounts").json()
    assert any(a["org_id"] == acct["org_id"] for a in listed)
    assert all("api_key" not in a for a in listed)
    r = client.post("/api/v1/inspect", data={"sku": "SKU-BOTTLE-750"}, files=_files(), headers={"x-api-key": acct["api_key"]})
    assert r.status_code == 200 and r.json()["organization_id"] == acct["org_id"]
    assert len(client.get("/api/v1/returns", headers={"x-org-id": acct["org_id"]}).json()) == 1
    assert client.get("/api/v1/returns", headers={"x-org-id": "org_demo_alpha"}).json() == []

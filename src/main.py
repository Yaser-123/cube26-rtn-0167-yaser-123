from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict
from collections import defaultdict
from datetime import datetime, timezone
from .models import ReturnCaptureRequest, EvidenceRecord, OverrideRequest, compute_content_hash
from .agent import ReturnsAgent
from .eval_api import router as eval_router
from .public_api import build_public_api
from . import accounts

app = FastAPI(title="Returns Manager API")
agent = ReturnsAgent()
app.include_router(eval_router)

# In-memory store partitioned by tenant: records_db[org_id][record_id].
# A lookup can only ever reach the caller's own partition.
records_db: Dict[str, Dict[str, EvidenceRecord]] = defaultdict(dict)
public_api = build_public_api(agent, records_db)
app.include_router(public_api)

app.mount("/static", StaticFiles(directory="src/static"), name="static")


@app.get("/")
def serve_ui():
    return FileResponse("src/static/index.html")


@app.get("/label")
def serve_labelling_ui():
    return FileResponse("src/static/label.html")


@app.get("/developers")
def serve_developer_docs():
    return FileResponse("src/static/developers.html")


class ProcessBatchRequest(BaseModel):
    requests: List[ReturnCaptureRequest]


def _require_account(x_org_id: str):
    if not accounts.account_exists(x_org_id):
        raise HTTPException(status_code=403, detail="Unknown client account")


def _check_tenant(request: ReturnCaptureRequest, x_org_id: str):
    _require_account(x_org_id)
    if request.organization_id != x_org_id:
        raise HTTPException(status_code=403, detail="Tenant ID mismatch")


class NewAccount(BaseModel):
    name: str = Field(min_length=2, max_length=60)


@app.get("/api/v1/accounts")
def list_accounts():
    return accounts.list_accounts()


@app.post("/api/v1/accounts")
def create_account(body: NewAccount):
    # Returns the account's API key once; it is not shown again
    return accounts.create_account(body.name.strip())


@app.get("/api/v1/orders/{unit_id}")
def lookup_order(unit_id: str, x_org_id: str = Header(...)):
    """Original order for a returned unit, so the operator doesn't retype SKU and parts."""
    _require_account(x_org_id)
    order = accounts.find_order(x_org_id, unit_id)
    if order is None:
        # Same 404 whether the unit is unknown or belongs to another account
        raise HTTPException(status_code=404, detail="No order found for this unit in this account")
    return order


@app.get("/api/v1/orders")
def example_orders(x_org_id: str = Header(...)):
    _require_account(x_org_id)
    return {"examples": accounts.example_units(x_org_id)}


def _get_owned_record(record_id: str, x_org_id: str) -> EvidenceRecord:
    _require_account(x_org_id)
    record = records_db[x_org_id].get(record_id)
    if record is None:
        # Same 404 whether the record doesn't exist or belongs to another tenant
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@app.post("/agent", response_model=EvidenceRecord)
@app.post("/api/v1/returns/process", response_model=EvidenceRecord)
def process_return(request: ReturnCaptureRequest, x_org_id: str = Header(...)):
    _check_tenant(request, x_org_id)
    # agent.process never raises on model failure: it fails open to a pending_review record
    record = agent.process(request)
    records_db[x_org_id][record.record_id] = record
    return record


@app.post("/api/v1/returns/process-batch", response_model=List[EvidenceRecord])
def process_return_batch(batch: ProcessBatchRequest, x_org_id: str = Header(...)):
    for req in batch.requests:
        _check_tenant(req, x_org_id)
    records = agent.process_many(batch.requests)
    for record in records:
        records_db[x_org_id][record.record_id] = record
    return records


@app.get("/api/v1/returns", response_model=List[EvidenceRecord])
def list_returns(x_org_id: str = Header(...)):
    _require_account(x_org_id)
    return list(records_db[x_org_id].values())


@app.get("/api/v1/returns/{record_id}", response_model=EvidenceRecord)
def get_return(record_id: str, x_org_id: str = Header(...)):
    return _get_owned_record(record_id, x_org_id)


@app.post("/api/v1/returns/{record_id}/override", response_model=EvidenceRecord)
def override_decision(record_id: str, request: OverrideRequest, x_org_id: str = Header(...)):
    record = _get_owned_record(record_id, x_org_id)

    # Overrides are appended, never replace history; the agent's checks stay as they were
    record.overrides.append({
        "original_verdict": record.outcome,
        "revised_verdict": request.revised_verdict,
        "reason": request.reason,
        "operator": request.operator,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    record.outcome = request.revised_verdict
    record.status = "overridden"
    record.content_hash = compute_content_hash(record)
    return record


@app.get("/health")
def health():
    return {"status": "ok"}

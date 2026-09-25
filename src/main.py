from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional
from .models import ReturnCaptureRequest, EvidenceRecord
from .agent import ReturnsAgent

app = FastAPI(title="Returns Manager API")
agent = ReturnsAgent()

class ProcessBatchRequest(BaseModel):
    requests: List[ReturnCaptureRequest]

@app.post("/api/v1/returns/process", response_model=EvidenceRecord)
def process_return(request: ReturnCaptureRequest, x_org_id: str = Header(...)):
    # Enforce Tenancy Isolation
    if request.organization_id != x_org_id:
        raise HTTPException(status_code=403, detail="Tenant ID mismatch")
    
    try:
        record = agent.process(request)
        return record
    except Exception as e:
        # Fail Open Logic - Return pending review case
        return dict(
            status="pending", 
            error=str(e), 
            outcome="pending_review", 
            organization_id=request.organization_id,
            subject=request.unit_id
        )

@app.post("/api/v1/returns/process-batch", response_model=List[EvidenceRecord])
def process_return_batch(batch: ProcessBatchRequest, x_org_id: str = Header(...)):
    # Batch Model Calls
    results = []
    for req in batch.requests:
        if req.organization_id != x_org_id:
            # Skip invalid tenant requests or raise error depending on policy
            continue
        record = agent.process(req)
        results.append(record)
    return results

@app.get("/health")
def health():
    return {"status": "ok"}

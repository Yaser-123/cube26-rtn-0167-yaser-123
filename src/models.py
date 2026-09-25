from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict
from datetime import datetime

class ReturnCaptureRequest(BaseModel):
    unit_id: str
    organization_id: str
    operator_label: str
    order_id: str
    ordered_sku: str
    parts_list: str
    photo_refs: List[str]

class Check(BaseModel):
    check_key: str
    verdict: Literal["PASS", "FAIL", "UNCERTAIN"]
    confidence: float
    detail: str
    model_version: str = "returns-vision-v1"
    latency_ms: int

class EvidenceRecord(BaseModel):
    record_id: str
    schema_version: str = "1.0"
    organization_id: str
    client_id: str = "returns-manager-agent"
    agent: str = "Returns Manager Agent"
    subject: str # e.g. unit_id
    captured_at: str
    operator_label: str
    images: List[str]
    checks: List[Check]
    outcome: str # The disposition: restock, refurbish, liquidate, dispose, pending_review
    overrides: List[Dict] = []
    status: str = "completed"
    content_hash: str

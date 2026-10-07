import hashlib
import json
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict


class ReturnCaptureRequest(BaseModel):
    model_config = {"str_strip_whitespace": True}

    unit_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    organization_id: str = Field(min_length=1, max_length=64)
    operator_label: str = Field(min_length=1, max_length=64)
    order_id: str = Field(min_length=1, max_length=64)
    ordered_sku: str = Field(min_length=1, max_length=64)
    ordered_asin: Optional[str] = None
    parts_list: str = Field(min_length=1)
    # Local file paths or data: URLs (browser uploads). Empty is accepted and fails open to review.
    photo_refs: List[str] = Field(max_length=10)
    operator_observations: Optional[str] = None


class OverrideRequest(BaseModel):
    revised_verdict: Literal["restock", "refurbish", "liquidate", "dispose", "pending_review"]
    reason: str = Field(min_length=3)
    operator: str = "op_demo"


class Check(BaseModel):
    model_config = {"protected_namespaces": ()}

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
    subject: str  # unit_id
    captured_at: str
    operator_label: str
    images: List[str]
    checks: List[Check]
    outcome: str  # restock, refurbish, liquidate, dispose, pending_review
    overrides: List[Dict] = []
    status: str = "completed"
    content_hash: str


def compute_content_hash(record: EvidenceRecord) -> str:
    """SHA-256 over the canonical JSON of every field except content_hash itself.

    Lets a consumer detect that a record changed; it is not signed or anchored anywhere,
    so it does not by itself make records tamper-proof.
    """
    body = record.model_dump(exclude={"content_hash"})
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

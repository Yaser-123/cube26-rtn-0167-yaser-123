import hashlib
import time
import uuid
import random
from datetime import datetime, timezone
from .models import ReturnCaptureRequest, EvidenceRecord, Check

class ReturnsAgent:
    def __init__(self):
        # We simulate visual checks here
        pass

    def _generate_record_id(self):
        return f"RTN-{uuid.uuid4().hex[:8].upper()}"

    def process(self, request: ReturnCaptureRequest) -> EvidenceRecord:
        start_time = time.time()
        
        # Simulate Identity Check
        identity_pass = random.choices([True, False], weights=[0.9, 0.1])[0]
        identity_check = Check(
            check_key="identity",
            verdict="PASS" if identity_pass else "FAIL",
            confidence=round(random.uniform(0.85, 0.99), 2),
            detail="Item matches SKU" if identity_pass else "Mismatch between ordered SKU and item",
            latency_ms=random.randint(150, 400)
        )

        # Simulate Completeness Check
        completeness_pass = random.choices([True, False], weights=[0.8, 0.2])[0]
        completeness_check = Check(
            check_key="completeness",
            verdict="PASS" if completeness_pass else "FAIL",
            confidence=round(random.uniform(0.75, 0.95), 2),
            detail="All expected parts present" if completeness_pass else "Missing manual",
            latency_ms=random.randint(200, 500)
        )

        # Simulate Condition Check (Amazon scale)
        condition_scale = ["New", "Used - Like New", "Used - Very Good", "Used - Good", "Used - Acceptable", "Unacceptable"]
        condition_val = random.choice(condition_scale)
        condition_check = Check(
            check_key="condition",
            verdict="PASS" if condition_val != "Unacceptable" else "FAIL",
            confidence=round(random.uniform(0.70, 0.99), 2),
            detail=f"Condition graded as {condition_val}",
            latency_ms=random.randint(300, 600)
        )

        # Introduce fail open/uncertain logic
        uncertain = random.random() < 0.05
        if uncertain:
            disposition = "pending_review"
            condition_check.verdict = "UNCERTAIN"
            condition_check.detail = "Image too blurry to determine condition"
            status = "pending"
        else:
            status = "completed"
            if condition_val == "New" and identity_pass and completeness_pass:
                disposition = "restock"
            elif condition_val in ["Used - Like New", "Used - Very Good"] and identity_pass:
                disposition = "refurbish"
            elif condition_val == "Unacceptable" or not identity_pass:
                disposition = "dispose"
            else:
                disposition = "liquidate"

        checks = [identity_check, completeness_check, condition_check]
        
        # Generate Content Hash
        hash_input = request.unit_id + disposition + "".join([c.verdict for c in checks])
        content_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        record = EvidenceRecord(
            record_id=self._generate_record_id(),
            organization_id=request.organization_id,
            subject=request.unit_id,
            captured_at=datetime.now(timezone.utc).isoformat(),
            operator_label=request.operator_label,
            images=request.photo_refs,
            checks=checks,
            outcome=disposition,
            status=status,
            content_hash=content_hash
        )

        return record

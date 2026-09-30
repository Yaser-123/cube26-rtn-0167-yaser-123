import hashlib
import time
import uuid
import os
import json
import base64
import threading
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from dotenv import load_dotenv
import anthropic
from datetime import datetime, timezone
from .models import ReturnCaptureRequest, EvidenceRecord, Check, compute_content_hash
from .catalog import CATALOG

load_dotenv()

MODEL = os.getenv("RTN_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("RTN_EFFORT", "low")
# Longest image edge sent to the model. ~1024px keeps seals/scuffs legible at roughly
# 1,000-1,400 input tokens per image (vs ~2,400 at 1568px).
MAX_IMAGE_EDGE = int(os.getenv("RTN_MAX_IMAGE_EDGE", "1024"))
MAX_IMAGES = 3
CACHE_DIR = Path(os.getenv("RTN_CACHE_DIR", ".cache/vision"))
PROMPT_VERSION = "v4"
# Max billed model calls per UTC day across the whole service (cache hits are free and not counted)
DAILY_CALL_CAP = int(os.getenv("RTN_DAILY_CALL_CAP", "300"))

# USD per million tokens (input, output), from Anthropic's published pricing
PRICING = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# Amazon's published condition scale (Seller Central > Condition Guidelines).
# "Unacceptable" is the guideline's not-sellable bucket, not a listing condition.
CONDITIONS = ["New", "Used - Like New", "Used - Very Good", "Used - Good", "Used - Acceptable", "Unacceptable"]
OBSERVED_STATES = ["factory_sealed", "opened_unused", "signs_of_use", "damaged", "empty_box", "uncertain"]
VERDICTS = ["PASS", "FAIL", "UNCERTAIN"]

SYSTEM_PROMPT = """You are a returns inspector at a warehouse. You grade returned items strictly from photo evidence, answering three checks in one pass.

Each check gets its own verdict:
- PASS: the photos show the requirement is met.
- FAIL: the photos show the requirement is not met.
- UNCERTAIN: the photos do not let you tell. This is a normal, correct answer - never turn a guess into PASS or FAIL.

Identity: is this the product in the seller's catalogue description? Returned items are often unbranded or out of their packaging, so do not require a logo or label.
- PASS: the visible item's product type and features match the description and nothing contradicts it.
- FAIL: it is clearly a different product (wrong type, size, colour or model stated in the description).
- UNCERTAIN: the item itself cannot be seen (closed plain shipping carton, blurry, dark, cropped).

Completeness: are all expected parts present? If the item is clearly visible and a part is evidently missing (empty slot, exposed threads where a lid belongs), FAIL and list it. If parts could be hidden inside closed packaging, UNCERTAIN - unless it is visibly factory sealed retail packaging, which counts as complete.

Condition: grade on Amazon's condition scale.
- New: unopened, factory seal visibly intact.
- Used - Like New: opened, no visible wear.
- Used - Very Good: very minor signs of use.
- Used - Good: visible use such as light scratches or dirt.
- Used - Acceptable: heavy wear but functional.
- Unacceptable: broken, crushed, or heavily damaged.
Condition verdict is FAIL only for Unacceptable, UNCERTAIN if you cannot see the item well enough to grade it. Assume hidden sides of a clearly visible item are fine.

Confidences are 0-1 and reflect how clearly the photos support each verdict. Details are one short sentence citing what you saw."""

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "observed": {"type": "string", "description": "What is literally visible in the photos"},
        "observed_state": {"type": "string", "enum": OBSERVED_STATES},
        "identity_verdict": {"type": "string", "enum": VERDICTS},
        "identity_confidence": {"type": "number"},
        "identity_detail": {"type": "string"},
        "completeness_verdict": {"type": "string", "enum": VERDICTS},
        "parts_missing": {"type": "array", "items": {"type": "string"}},
        "completeness_confidence": {"type": "number"},
        "completeness_detail": {"type": "string"},
        "condition_verdict": {"type": "string", "enum": VERDICTS},
        "condition_grade": {"type": "string", "enum": CONDITIONS + ["Not gradable"]},
        "condition_confidence": {"type": "number"},
        "condition_detail": {"type": "string"},
    },
    "required": [
        "observed", "observed_state",
        "identity_verdict", "identity_confidence", "identity_detail",
        "completeness_verdict", "parts_missing", "completeness_confidence", "completeness_detail",
        "condition_verdict", "condition_grade", "condition_confidence", "condition_detail",
    ],
    "additionalProperties": False,
}

CHECK_KEYS = ("identity", "completeness", "condition")


class BudgetExceeded(Exception):
    pass


def decide_disposition(identity, completeness, condition, grade):
    """Deterministic disposition policy. The model grades; this code decides."""
    if "UNCERTAIN" in (identity, completeness, condition):
        return "pending_review"
    if identity == "FAIL":
        # Wrong item came back: a human (and Recovery Manager) must handle it, never auto-dispose
        return "pending_review"
    if grade == "Unacceptable":
        return "dispose"
    if completeness == "FAIL":
        # Sound item missing a part: replace the part and resell
        return "refurbish" if grade != "Used - Acceptable" else "liquidate"
    if grade in ("New", "Used - Like New"):
        return "restock"
    if grade in ("Used - Very Good", "Used - Good"):
        return "refurbish"
    return "liquidate"


class ReturnsAgent:
    def __init__(self):
        headers = {}
        # Keys not scoped to a workspace must name one on every request
        if os.getenv("ANTHROPIC_WORKSPACE_ID"):
            headers["anthropic-workspace-id"] = os.getenv("ANTHROPIC_WORKSPACE_ID")
        self.client = anthropic.Anthropic(default_headers=headers, max_retries=2, timeout=90.0)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._budget_lock = threading.Lock()
        self._budget_day = None
        self._calls_today = 0

    def _generate_record_id(self):
        return f"RTN-{uuid.uuid4().hex[:8].upper()}"

    def _encode_image(self, image_ref):
        # Accepts either a data URL uploaded from the browser or a local file path
        try:
            if image_ref.startswith("data:"):
                source = BytesIO(base64.b64decode(image_ref.split(",", 1)[1]))
            else:
                source = image_ref
            with Image.open(source) as img:
                img.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                return base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            print(f"Error encoding image {image_ref[:80]}: {e}")
            return None

    def _cache_key(self, images, request):
        h = hashlib.sha256()
        for part in (request.organization_id, MODEL, EFFORT, PROMPT_VERSION, request.ordered_sku,
                     request.ordered_asin or "", request.parts_list, *images):
            h.update(part.encode())
            h.update(b"\0")
        return h.hexdigest()

    def _call_model(self, images, request):
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}
            for data in images
        ]
        asin = f" (ASIN {request.ordered_asin})" if request.ordered_asin else ""
        description = CATALOG.get(request.ordered_sku, "not in catalogue; judge from the SKU name")
        content.append({
            "type": "text",
            "text": f"Ordered SKU: {request.ordered_sku}{asin}\nCatalogue description: {description}\n"
                    f"Expected parts: {request.parts_list}\n\nInspect this return.",
        })
        response = self.client.beta.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": RESULT_SCHEMA},
            },
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Model declined to analyze these images")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("Model response was cut off")
        text = next(b.text for b in response.content if b.type == "text")
        price_in, price_out = PRICING.get(MODEL, (0.0, 0.0))
        usage = {
            "model": response.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cost_usd": round((response.usage.input_tokens * price_in + response.usage.output_tokens * price_out) / 1e6, 5),
            "cached": False,
        }
        return json.loads(text), usage

    def _get_result(self, images, request):
        """One batched model call for all three checks, memoised on disk so identical re-submissions cost nothing."""
        cache_file = CACHE_DIR / f"{self._cache_key(images, request)}.json"
        if cache_file.exists():
            cached = json.loads(cache_file.read_text())
            return cached["result"], {**cached["usage"], "cost_usd": 0.0, "cached": True}
        self._reserve_budget()
        result, usage = self._call_model(images, request)
        cache_file.write_text(json.dumps({"result": result, "usage": usage}))
        return result, usage

    def _reserve_budget(self):
        # Hard cap on billed model calls per UTC day, so a public deployment can't drain the account
        with self._budget_lock:
            today = datetime.now(timezone.utc).date()
            if self._budget_day != today:
                self._budget_day, self._calls_today = today, 0
            if self._calls_today >= DAILY_CALL_CAP:
                raise BudgetExceeded(f"Daily limit of {DAILY_CALL_CAP} model calls reached")
            self._calls_today += 1

    def analyze(self, request: ReturnCaptureRequest):
        """Returns (EvidenceRecord, usage dict)."""
        start_time = time.time()

        images = [d for d in (self._encode_image(ref) for ref in request.photo_refs[:MAX_IMAGES]) if d]

        result = None
        usage = {"model": MODEL, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "cached": False}
        failure_reason = None
        if not images:
            failure_reason = "No readable images were received, so nothing could be verified."
        else:
            try:
                result, usage = self._get_result(images, request)
            except BudgetExceeded as e:
                failure_reason = f"{e}; case kept for human review."
            except Exception as e:
                print(f"Vision model error: {e}")
                failure_reason = f"Vision model unavailable ({type(e).__name__}); case kept for human review."

        latency_ms = int((time.time() - start_time) * 1000)
        usage["latency_ms"] = latency_ms

        if result is None:
            # Fail open: keep the capture, verify nothing, route to a human
            checks = [
                Check(check_key=key, verdict="UNCERTAIN", confidence=0.0, detail=failure_reason,
                      model_version=MODEL, latency_ms=latency_ms)
                for key in CHECK_KEYS
            ]
            disposition = "pending_review"
            status = "pending"
        else:
            def clamp(x):
                return round(min(max(float(x), 0.0), 1.0), 2)

            result = dict(result)
            if request.ordered_sku not in CATALOG and result["identity_verdict"] == "PASS":
                # Identity is checked against the seller's catalogue; without an entry it cannot be confirmed
                result["identity_verdict"] = "UNCERTAIN"
                result["identity_detail"] = (f"{request.ordered_sku} is not in the seller catalogue, so identity cannot be "
                                             f"confirmed. Model saw: {result['identity_detail']}")

            completeness_detail = result["completeness_detail"]
            if result["parts_missing"]:
                completeness_detail += f" Missing: {', '.join(result['parts_missing'])}."
            condition_detail = f"{result['condition_grade']} (observed: {result['observed_state']}). {result['condition_detail']}"
            details = {
                "identity": result["identity_detail"],
                "completeness": completeness_detail,
                "condition": condition_detail,
            }
            checks = [
                Check(check_key=key, verdict=result[f"{key}_verdict"], confidence=clamp(result[f"{key}_confidence"]),
                      detail=details[key], model_version=MODEL, latency_ms=latency_ms)
                for key in CHECK_KEYS
            ]
            disposition = decide_disposition(
                result["identity_verdict"], result["completeness_verdict"],
                result["condition_verdict"], result["condition_grade"],
            )
            status = "pending" if disposition == "pending_review" else "completed"

        record = EvidenceRecord(
            record_id=self._generate_record_id(),
            organization_id=request.organization_id,
            subject=request.unit_id,
            captured_at=datetime.now(timezone.utc).isoformat(),
            operator_label=request.operator_label,
            # Keep base64 uploads out of the stored record; reference them by content hash instead
            images=[
                f"upload:sha256:{hashlib.sha256(ref.encode()).hexdigest()[:16]}" if ref.startswith("data:") else ref
                for ref in request.photo_refs
            ],
            checks=checks,
            outcome=disposition,
            status=status,
            content_hash="",
        )
        record.content_hash = compute_content_hash(record)
        return record, usage

    def process(self, request: ReturnCaptureRequest) -> EvidenceRecord:
        return self.analyze(request)[0]

    def process_many(self, requests):
        # Independent units run concurrently; each unit is already a single batched call
        with ThreadPoolExecutor(max_workers=4) as pool:
            return list(pool.map(self.process, requests))

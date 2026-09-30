"""Public inspection API: upload 1-3 photos + a SKU as multipart form data, get an Evidence Record back.

Authenticated with an API key that maps to one tenant, so callers never choose their own org.
Keys come from RTN_API_KEYS ("key1:org_demo_alpha,key2:org_demo_bravo").
"""
import base64
import os
import time
import uuid
import threading
from collections import defaultdict, deque
from typing import List, Optional
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from .catalog import CATALOG, PARTS
from . import accounts
from .models import EvidenceRecord, ReturnCaptureRequest

MAX_FILES = 3
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
# Per-key request limit per rolling hour
RATE_LIMIT_PER_HOUR = int(os.getenv("RTN_RATE_LIMIT_PER_HOUR", "30"))


def _load_keys():
    raw = os.getenv("RTN_API_KEYS", "")
    keys = {}
    for pair in raw.split(","):
        if ":" in pair:
            key, org = pair.split(":", 1)
            if key.strip() and org.strip():
                keys[key.strip()] = org.strip()
    return keys


class PublicAPI:
    def __init__(self, agent, records_db):
        self.agent = agent
        self.records_db = records_db
        self.keys = _load_keys()
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def _authenticate(self, api_key: Optional[str]) -> str:
        # Keys from .env plus keys of accounts created in the app (read per request so new ones work at once)
        org = {**self.keys, **accounts.api_keys()}.get(api_key or "")
        if org is None:
            raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key")
        return org

    def _rate_limit(self, api_key: str):
        now = time.time()
        with self._lock:
            hits = self._hits[api_key]
            while hits and now - hits[0] > 3600:
                hits.popleft()
            if len(hits) >= RATE_LIMIT_PER_HOUR:
                raise HTTPException(status_code=429, detail=f"Rate limit of {RATE_LIMIT_PER_HOUR} requests per hour reached",
                                    headers={"Retry-After": str(int(3600 - (now - hits[0])) + 1)})
            hits.append(now)

    def catalog(self):
        return [{"sku": sku, "description": desc, "parts": PARTS.get(sku, "")} for sku, desc in CATALOG.items()]


def build_public_api(agent, records_db) -> APIRouter:
    api = PublicAPI(agent, records_db)

    async def inspect(
        images: List[UploadFile] = File(..., description="1-3 photos of the returned item"),
        sku: str = Form(..., description="Ordered SKU, e.g. SKU-BOTTLE-750"),
        parts: Optional[str] = Form(None, description="Expected parts, ;-separated. Defaults to the catalogue entry."),
        unit_id: Optional[str] = Form(None, description="Your unit ID. Generated if omitted."),
        order_id: Optional[str] = Form(None),
        asin: Optional[str] = Form(None),
        x_api_key: Optional[str] = Header(None, description="Your API key"),
    ):
        org = api._authenticate(x_api_key)
        if not 1 <= len(images) <= MAX_FILES:
            raise HTTPException(status_code=400, detail=f"Send between 1 and {MAX_FILES} images")
        sku = sku.strip().upper()
        parts = (parts or PARTS.get(sku, "")).strip()
        if not parts:
            raise HTTPException(status_code=400, detail=f"{sku} is not in the catalogue, so 'parts' is required")

        photo_refs = []
        for f in images:
            if f.content_type not in ALLOWED_TYPES:
                raise HTTPException(status_code=415, detail=f"{f.filename}: only JPEG, PNG, WebP or GIF images are accepted")
            data = await f.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise HTTPException(status_code=413, detail=f"{f.filename}: images must be under 10 MB")
            photo_refs.append(f"data:{f.content_type};base64,{base64.b64encode(data).decode()}")

        # Only count requests that passed validation against the rate limit
        api._rate_limit(x_api_key)
        try:
            request = ReturnCaptureRequest(
                unit_id=unit_id or f"API-{uuid.uuid4().hex[:8].upper()}",
                organization_id=org,
                operator_label="api",
                order_id=order_id or "N/A",
                ordered_sku=sku,
                ordered_asin=asin,
                parts_list=parts,
                photo_refs=photo_refs,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        # The agent call is blocking; run it off the event loop
        record = await run_in_threadpool(api.agent.process, request)
        api.records_db[org][record.record_id] = record
        return record

    router = APIRouter(prefix="/api/v1", tags=["Public API"])
    router.add_api_route("/inspect", inspect, methods=["POST"], response_model=EvidenceRecord,
                         summary="Inspect a returned item from photos")
    router.add_api_route("/catalog", api.catalog, methods=["GET"], summary="List known SKUs and their expected parts")
    router.api = api
    return router

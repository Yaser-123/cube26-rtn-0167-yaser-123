"""Labelling API for the held-out eval set (eval/labels.csv + eval/images/).

Each labeller only ever sees and writes their own columns, so the two label sets stay independent.
Eval fixtures are internal test data, not tenant data.
"""
import base64
import csv
import re
import threading
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .catalog import CATALOG

LABELS = Path("eval/labels.csv")
IMAGES = Path("eval/images")
FIELDS = ["unit_id", "org_id", "ordered_sku", "parts_list", "photo_refs",
          "identity_a", "completeness_a", "condition_a", "disposition_a",
          "identity_b", "completeness_b", "condition_b", "disposition_b"]
LABEL_KEYS = ("identity", "completeness", "condition", "disposition")

router = APIRouter(prefix="/api/v1/eval")
_lock = threading.Lock()

Verdict = Literal["PASS", "FAIL", "UNCERTAIN"]
Disposition = Literal["restock", "refurbish", "liquidate", "dispose", "pending_review"]


def _read():
    if not LABELS.exists():
        return []
    with LABELS.open(newline="", encoding="utf-8") as f:
        return [{k: r.get(k, "") or "" for k in FIELDS} for r in csv.DictReader(f) if r.get("unit_id")]


def _write(rows):
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    with LABELS.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


class NewUnit(BaseModel):
    ordered_sku: str = Field(min_length=1)
    parts_list: str = Field(min_length=1)
    org_id: Literal["org_demo_alpha", "org_demo_bravo"] = "org_demo_alpha"
    images: list[str] = Field(min_length=1, max_length=3)  # data URLs


class Labels(BaseModel):
    labeller: Literal["a", "b"]
    identity: Verdict
    completeness: Verdict
    condition: Verdict
    disposition: Disposition


@router.get("/units")
def list_units(labeller: Literal["a", "b"]):
    return [
        {"unit_id": r["unit_id"], "ordered_sku": r["ordered_sku"], "parts_list": r["parts_list"],
         "description": CATALOG.get(r["ordered_sku"], "not in catalogue"),
         "images": len([p for p in r["photo_refs"].split(";") if p]),
         "labels": {k: r[f"{k}_{labeller}"] for k in LABEL_KEYS}}
        for r in _read()
    ]


@router.post("/units")
def add_unit(unit: NewUnit):
    with _lock:
        rows = _read()
        n = max([int(m.group(1)) for r in rows if (m := re.match(r"EVAL-(\d+)$", r["unit_id"]))] + [0]) + 1
        unit_id = f"EVAL-{n:03d}"
        IMAGES.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, data_url in enumerate(unit.images, 1):
            try:
                raw = base64.b64decode(data_url.split(",", 1)[1])
            except Exception:
                raise HTTPException(status_code=400, detail="Images must be data URLs")
            path = IMAGES / f"{unit_id}_{i}.jpg"
            path.write_bytes(raw)
            paths.append(path.as_posix())
        rows.append({**{k: "" for k in FIELDS}, "unit_id": unit_id, "org_id": unit.org_id,
                     "ordered_sku": unit.ordered_sku, "parts_list": unit.parts_list, "photo_refs": ";".join(paths)})
        _write(rows)
    return {"unit_id": unit_id}


@router.put("/units/{unit_id}/labels")
def save_labels(unit_id: str, labels: Labels):
    with _lock:
        rows = _read()
        row = next((r for r in rows if r["unit_id"] == unit_id), None)
        if row is None:
            raise HTTPException(status_code=404, detail="Unit not found")
        for k in LABEL_KEYS:
            row[f"{k}_{labels.labeller}"] = getattr(labels, k)
        _write(rows)
    return {"ok": True}


@router.get("/units/{unit_id}/images/{index}")
def unit_image(unit_id: str, index: int):
    row = next((r for r in _read() if r["unit_id"] == unit_id), None)
    refs = [p for p in (row["photo_refs"].split(";") if row else []) if p]
    if not (0 <= index < len(refs)):
        raise HTTPException(status_code=404, detail="Image not found")
    path = Path(refs[index]).resolve()
    # Only serve files from the fixture folders, never arbitrary paths from the CSV
    if not any(path.is_relative_to(Path(d).resolve()) for d in ("eval/images", "test_images")) or not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)

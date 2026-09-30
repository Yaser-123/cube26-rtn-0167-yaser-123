"""Client accounts (tenants) and the orders each one expects returns for.

Two demo accounts come from the sample data. New accounts are saved to .data/accounts.json
(git-ignored) together with their API key. Account creation is open in this demo; in production
it would sit behind operator login.
"""
import csv
import json
import os
import re
import secrets
import threading
from pathlib import Path
from typing import Dict, Optional

ACCOUNTS_FILE = Path(os.getenv("RTN_ACCOUNTS_FILE", ".data/accounts.json"))
ORDERS_FILE = Path("data/returns_sample.csv")
DEMO_ACCOUNTS = {
    "org_demo_alpha": "Alpha Retail (demo)",
    "org_demo_bravo": "Bravo Goods (demo)",
}

_lock = threading.Lock()


def _load_saved() -> Dict[str, dict]:
    if not ACCOUNTS_FILE.exists():
        return {}
    return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))


def list_accounts():
    accounts = [{"org_id": org, "name": name, "demo": True} for org, name in DEMO_ACCOUNTS.items()]
    accounts += [{"org_id": org, "name": a["name"], "demo": False} for org, a in _load_saved().items()]
    return accounts


def account_exists(org_id: str) -> bool:
    return org_id in DEMO_ACCOUNTS or org_id in _load_saved()


def create_account(name: str) -> dict:
    """Returns the new account including its API key, which is only ever shown here."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:24] or "client"
    with _lock:
        saved = _load_saved()
        org_id = f"org_{slug}_{secrets.token_hex(3)}"
        api_key = f"rtn_{secrets.token_urlsafe(24)}"
        saved[org_id] = {"name": name, "api_key": api_key}
        ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ACCOUNTS_FILE.write_text(json.dumps(saved, indent=2), encoding="utf-8")
    return {"org_id": org_id, "name": name, "api_key": api_key}


def api_keys() -> Dict[str, str]:
    """API key -> org_id for accounts created in the app."""
    return {a["api_key"]: org for org, a in _load_saved().items()}


def find_order(org_id: str, unit_id: str) -> Optional[dict]:
    """Look up the original order for a returned unit, only within the caller's own account."""
    if not ORDERS_FILE.exists():
        return None
    with ORDERS_FILE.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["unit_id"].upper() == unit_id.upper() and row["org_id"] == org_id:
                return {
                    "unit_id": row["unit_id"],
                    "order_id": row["order_id"],
                    "ordered_sku": row["ordered_sku"],
                    "ordered_asin": row["ordered_asin"],
                    "parts_list": row["parts_list"],
                }
    return None


def example_units(org_id: str, limit: int = 4):
    if not ORDERS_FILE.exists():
        return []
    with ORDERS_FILE.open(newline="", encoding="utf-8") as f:
        return [r["unit_id"] for r in csv.DictReader(f) if r["org_id"] == org_id][:limit]

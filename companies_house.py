"""
Companies House API layer for Goal #3.

Purpose: the "any UK company" front door — resolve a company (by name or number)
to its SIC code(s), even when it has NO trademarks and so isn't in Temmy.
The sector intelligence itself still comes from Temmy (by SIC).

Auth: HTTP Basic, API key as username, empty password.
Key: COMPANIES_HOUSE_API_KEY in ../temmy-access/secrets.env (free key from
https://developer.company-information.service.gov.uk/).

All functions degrade gracefully (return [] / None) when no key is set.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from config import get_secret

BASE = "https://api.company-information.service.gov.uk"


def _key() -> str:
    return get_secret("COMPANIES_HOUSE_API_KEY", "")


def ready() -> bool:
    return bool(_key())


def _get(path: str, params: dict | None = None):
    key = _key()
    if not key:
        return None
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    auth = base64.b64encode(f"{key}:".encode()).decode()
    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {auth}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_detail": e.read().decode("utf-8", "replace")[:200]}
    except Exception as e:
        return {"_error": "network", "_detail": str(e)[:200]}


def search(name: str, *, limit: int = 10):
    """Search companies by name. Returns [{company_number, title, status, ...}]."""
    d = _get("/search/companies", {"q": name, "items_per_page": limit})
    if not isinstance(d, dict) or "_error" in d:
        return []
    out = []
    for it in d.get("items", []):
        out.append({
            "company_number": it.get("company_number"),
            "title": it.get("title"),
            "status": it.get("company_status"),
            "address": it.get("address_snippet"),
        })
    return out


def profile(company_number: str):
    """Full company profile incl. sic_codes."""
    cn = "".join(ch for ch in str(company_number) if ch.isalnum())
    d = _get(f"/company/{cn}")
    if not isinstance(d, dict) or "_error" in d:
        return None
    return {
        "name": d.get("company_name"),
        "number": d.get("company_number"),
        "status": d.get("company_status"),
        "sic_codes": d.get("sic_codes") or [],
        "incorporated": d.get("date_of_creation"),
        "type": d.get("type"),
    }


def resolve_sic(company_number: str):
    """Just the SIC code list for a company number (or [])."""
    p = profile(company_number)
    return (p or {}).get("sic_codes", [])

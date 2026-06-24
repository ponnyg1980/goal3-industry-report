"""
Goal #3 — Industry Trademark Report: data-access layer.  (LIVE)

Verified against live TemmyDB on 24 Jun 2026:
  • Registry holds ~2.98M trademarks, 484,940 matched companies,
    470,631 (97%) carrying Companies-House SIC codes — so SIC + sector
    aggregation come straight from Temmy (no Companies House API needed
    for companies already in the registry).

Data sources:
  1. Temmy HTTP API  (X-API-Key)         — fast company / mark text lookup.
  2. Temmy Query Runs (X-Query-Runs-Key) — read-only SQL for SIC sector
     aggregation. Request body: {"sql": "..."}; rows return inline in
     a "preview" field (up to 1000), with a "pagination" block.

Credentials are read from ../temmy-access/secrets.env (never from chat).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from config import get_secret

DEFAULT_BASE = "https://temmy-api-prod-zfxujusd3q-nw.a.run.app"

BASE = get_secret("TEMMY_API_BASE_URL", DEFAULT_BASE)
API_KEY = get_secret("TEMMY_API_KEY", "")
QR_KEY = get_secret("TEMMY_QUERY_RUNS_API_KEY", "")
TIMEOUT = float(get_secret("TEMMY_API_TIMEOUT_SECONDS", "30"))


class QueryRunsUnavailable(Exception):
    pass


# ── HTTP ─────────────────────────────────────────────────────────────
def _request(method, path, *, key_header=None, key_value=None, params=None,
             body=None, timeout=None):
    url = BASE.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json"}
    if key_header and key_value:
        headers[key_header] = key_value
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = raw
        return e.code, payload


# ── 1) API-backed company lookup (fast) ──────────────────────────────
def api_ready() -> bool:
    return bool(API_KEY)


def health() -> bool:
    try:
        s, p = _request("GET", "/health")
        return s == 200 and isinstance(p, dict) and p.get("status") == "ok"
    except Exception:
        return False


def search_company(name: str, *, exact: bool = False, limit: int = 50):
    """Find applicants whose marks match `name` via the fast trademarks/search
    endpoint, grouped by applicant. Each item:
    {applicant:{name, ipo_identifier}, trademarks:[...]}."""
    s, p = _request("GET", "/api/v1/trademarks/search",
                    key_header="X-API-Key", key_value=API_KEY,
                    params={"text": name, "limit": limit, "page": 1})
    if s != 200 or not isinstance(p, dict):
        return []
    grouped: dict = {}
    for it in p.get("items", []):
        for a in (it.get("applicants") or [{"name": "(unknown)"}]):
            key = a.get("ipo_identifier") or a.get("name")
            g = grouped.setdefault(key, {"applicant": a, "trademarks": []})
            g["trademarks"].append({
                "application_number": it.get("application_number"),
                "mark": {"verbal_element_text": it.get("verbal_element_text")},
                "status": it.get("status"),
                "expiry_date": it.get("expiry_date"),
            })
    return sorted(grouped.values(), key=lambda g: -len(g["trademarks"]))


# ── 2) Query Runs (read-only SQL) ────────────────────────────────────
def query_runs_ready() -> bool:
    if not QR_KEY:
        return False
    s, _ = _request("POST", "/api/v2/query-runs",
                    key_header="X-Query-Runs-Key", key_value=QR_KEY,
                    body={"sql": "SELECT 1 AS ok"}, timeout=20)
    return s == 200


def run_sql(sql: str, *, max_rows: int = 5000):
    """Execute one read-only SELECT via Query Runs; return list[dict].
    Rows arrive inline in 'preview'; we page only if there are more."""
    if not QR_KEY:
        raise QueryRunsUnavailable("No TEMMY_QUERY_RUNS_API_KEY set.")
    s, payload = _request("POST", "/api/v2/query-runs",
                          key_header="X-Query-Runs-Key", key_value=QR_KEY,
                          body={"sql": sql}, timeout=60)
    if s == 401:
        raise QueryRunsUnavailable("Query Runs key rejected (401).")
    if s >= 400 or not isinstance(payload, dict):
        raise RuntimeError(f"Query Runs error {s}: {payload}")
    rows = list(payload.get("preview") or [])
    pag = payload.get("pagination") or {}
    run_id = payload.get("query_id")
    total = pag.get("total", len(rows))
    page = 2
    while run_id and len(rows) < min(total, max_rows) and page <= (pag.get("total_pages") or 1):
        s2, pg = _request("GET", f"/api/v2/query-runs/{run_id}/pages/{page}",
                          key_header="X-Query-Runs-Key", key_value=QR_KEY)
        if s2 != 200 or not isinstance(pg, dict):
            break
        more = pg.get("preview") or pg.get("items") or pg.get("rows") or []
        if not more:
            break
        rows.extend(more)
        page += 1
    return rows


def _safe_sic(sic: str) -> str:
    """SIC codes are short alphanumerics; reject anything else (no injection)."""
    sic = str(sic).strip()
    if not re.fullmatch(r"[0-9A-Za-z]{1,12}", sic):
        raise ValueError(f"Invalid SIC code: {sic!r}")
    return sic


# Live, validated sector SQL. SIC inlined after _safe_sic() validation
# (Query Runs takes a raw SQL string; no server-side param binding).
def _sector_sql(sic: str) -> dict:
    s = _safe_sic(sic)
    base_join = (f"FROM companies c "
                 f"JOIN applicants a ON a.company_id = c.id "
                 f"JOIN applicant_trademarks at ON at.applicant_id = a.id AND at.active "
                 f"WHERE '{s}' = ANY(c.sic_codes)")
    return {
        "size": f"SELECT count(DISTINCT at.trademark_id) trademarks, "
                f"count(DISTINCT c.id) companies {base_join}",
        "first_filed": f"SELECT EXTRACT(YEAR FROM min(t.application_date_time))::int yr "
                       f"FROM companies c JOIN applicants a ON a.company_id=c.id "
                       f"JOIN applicant_trademarks at ON at.applicant_id=a.id AND at.active "
                       f"JOIN trademarks t ON t.id=at.trademark_id WHERE '{s}'=ANY(c.sic_codes)",
        "top_companies": f"SELECT c.name, c.number company_number, "
                         f"count(DISTINCT at.trademark_id) trademarks {base_join} "
                         f"GROUP BY c.name, c.number ORDER BY trademarks DESC LIMIT 3",
        "class_distribution": f"SELECT nc.number nice_class, "
                              f"count(DISTINCT nct.trademark_id) trademarks "
                              f"FROM companies c JOIN applicants a ON a.company_id=c.id "
                              f"JOIN applicant_trademarks at ON at.applicant_id=a.id AND at.active "
                              f"JOIN nice_class_trademarks nct ON nct.trademark_id=at.trademark_id AND nct.active "
                              f"JOIN nice_classes nc ON nc.id=nct.nice_class_id "
                              f"WHERE '{s}'=ANY(c.sic_codes) GROUP BY nc.number ORDER BY trademarks DESC",
    }


def company_sic(company_number: str):
    """Resolve a company's SIC codes from Temmy (97% coverage)."""
    n = re.sub(r"[^0-9A-Za-z]", "", str(company_number))
    rows = run_sql(f"SELECT name, number, sic_codes FROM companies "
                   f"WHERE number = '{n}' LIMIT 1")
    return rows[0] if rows else None


def applicant_sic(ipo_identifier):
    """Bridge a looked-up applicant (from company search) to its company
    record + SIC codes, so the app can go name → sector in one hop."""
    iid = int(ipo_identifier)
    rows = run_sql(
        "SELECT c.name, c.number, c.sic_codes "
        "FROM applicants a JOIN companies c ON c.id = a.company_id "
        f"WHERE a.ipo_identifier = {iid} LIMIT 1")
    return rows[0] if rows else None


def sector_report(sic: str) -> dict:
    if not query_runs_ready():
        return {"available": False,
                "reason": "Query Runs key not authorised."}
    sql = _sector_sql(sic)
    out = {"available": True, "sic": _safe_sic(sic)}
    size = run_sql(sql["size"]);            out["size"] = size[0] if size else {}
    ff = run_sql(sql["first_filed"]);       out["first_filed_year"] = ff[0].get("yr") if ff else None
    out["top_companies"] = run_sql(sql["top_companies"])
    out["class_distribution"] = run_sql(sql["class_distribution"])
    return out

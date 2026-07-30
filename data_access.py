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
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from config import get_secret

HERE = os.path.dirname(os.path.abspath(__file__))
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


def run_sql(sql: str, *, max_pages: int = 20):
    """Execute one read-only SELECT via Query Runs; return list[dict].

    NOTE: the POST response's `preview` is only a ~25-row sample. The full
    result set must be read from /pages/{n} (keyed as `items`), 1000 rows/page.
    """
    if not QR_KEY:
        raise QueryRunsUnavailable("No TEMMY_QUERY_RUNS_API_KEY set.")
    s, payload = _request("POST", "/api/v2/query-runs",
                          key_header="X-Query-Runs-Key", key_value=QR_KEY,
                          body={"sql": sql}, timeout=60)
    if s == 401:
        raise QueryRunsUnavailable("Query Runs key rejected (401).")
    if s >= 400 or not isinstance(payload, dict):
        raise RuntimeError(f"Query Runs error {s}: {payload}")
    run_id = payload.get("query_id")
    total_pages = (payload.get("pagination") or {}).get("total_pages", 1) or 1
    rows = []
    for page in range(1, min(total_pages, max_pages) + 1):
        s2, pg = _request("GET", f"/api/v2/query-runs/{run_id}/pages/{page}",
                          key_header="X-Query-Runs-Key", key_value=QR_KEY)
        if s2 != 200 or not isinstance(pg, dict):
            break
        more = pg.get("items") or pg.get("preview") or pg.get("rows") or []
        if not more:
            break
        rows.extend(more)
    return rows


def run_scalar(sql: str) -> dict:
    """Convenience: return the first row of a Query Run as a dict (or {})."""
    rows = run_sql(sql)
    return rows[0] if rows else {}


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


def _sanitise_phrase(s: str) -> str:
    """Safe chars only, then SQL-escape quotes (only ever used inside an
    ILIKE literal) — same approach as freesearch/queryruns.py."""
    s = re.sub(r"[^A-Za-z0-9 \-]", "", str(s or "")).strip()
    return s.replace("'", "''")


def similar_marks(brand: str, *, limit: int = 300):
    """Candidate register marks whose verbal element could conflict with
    `brand`: contains-match plus a prefix stem for fuzzy variants
    (MOMENT% catches MOMENTUM/MOMENTOUS). Scored/banded by risk.py."""
    b = _sanitise_phrase(brand)
    if not b:
        return []
    stem = b[:5] if len(b) >= 5 else b
    conds = f"m.verbal_element_text ILIKE '%{b}%' OR m.verbal_element_text ILIKE '{stem}%'"
    sql = f"""
SELECT t.application_number, t.status, m.verbal_element_text,
       m.feature AS mark_type,
       array_agg(DISTINCT nc.number) FILTER (WHERE nc.number IS NOT NULL) AS classes,
       (array_agg(DISTINCT a.name))[1] AS applicant_name
FROM marks m
JOIN trademarks t ON t.id = m.trademark_id
LEFT JOIN nice_class_trademarks nct ON nct.trademark_id = t.id
LEFT JOIN nice_classes nc ON nc.id = nct.nice_class_id
LEFT JOIN applicant_trademarks apt ON apt.trademark_id = t.id
LEFT JOIN applicants a ON a.id = apt.applicant_id
WHERE ({conds})
GROUP BY t.application_number, t.status, m.verbal_element_text, m.feature
LIMIT {int(limit)}
""".strip()
    return run_sql(sql)


def company_marks(company_number: str, *, limit: int = 10):
    """Marks held by a company (by CH number) — used for the report's
    'what the sector leaders protect' appendix. REST applicant search
    misses many legal names; the SQL join by company_number doesn't."""
    n = re.sub(r"[^0-9A-Za-z]", "", str(company_number))
    if not n:
        return []
    return run_sql(
        "SELECT mk.verbal_element_text AS mark, t.status "
        "FROM applicants a "
        "JOIN applicant_trademarks apt ON apt.applicant_id = a.id AND apt.active "
        "JOIN trademarks t ON t.id = apt.trademark_id "
        "JOIN marks mk ON mk.trademark_id = t.id "
        f"WHERE a.company_number = '{n}' "
        f"ORDER BY t.status LIMIT {int(limit)}")


def company_sic(company_number: str):
    """Resolve a company's SIC codes from Temmy (97% coverage)."""
    n = re.sub(r"[^0-9A-Za-z]", "", str(company_number))
    rows = run_sql(f"SELECT name, number, sic_codes FROM companies "
                   f"WHERE number = '{n}' LIMIT 1")
    return rows[0] if rows else None


def company_sics_bulk(numbers):
    """SIC codes for many company numbers in ONE query — used to enrich the
    Companies House search list (CH search doesn't return SICs). Returns
    {company_number: [sic, ...]}."""
    nums = []
    for x in (numbers or []):
        n = re.sub(r"[^0-9A-Za-z]", "", str(x or ""))
        if n:
            nums.append(n)
    nums = list(dict.fromkeys(nums))            # dedupe, keep order
    if not nums:
        return {}
    inlist = ",".join("'" + n + "'" for n in nums)
    try:
        rows = run_sql(f"SELECT number, sic_codes FROM companies "
                       f"WHERE number IN ({inlist})")
    except Exception:
        return {}
    out = {}
    for r in (rows or []):
        sc = r.get("sic_codes")
        if isinstance(sc, str):
            sc = [p for p in re.split(r"[^0-9]+", sc) if p]
        out[str(r.get("number"))] = sc or []
    return out


def applicant_sic(ipo_identifier):
    """Bridge a looked-up applicant (from company search) to its company
    record + SIC codes, so the app can go name → sector in one hop."""
    iid = int(ipo_identifier)
    rows = run_sql(
        "SELECT c.name, c.number, c.sic_codes "
        "FROM applicants a JOIN companies c ON c.id = a.company_id "
        f"WHERE a.ipo_identifier = {iid} LIMIT 1")
    return rows[0] if rows else None


# ── Benchmarking engine (industry vs overall MEAN vs the company) ────
import csv as _csv

_ASSETS = os.path.join(HERE, "assets")
_REF = {}


def _ref():
    """Lazy-load bundled reference data (per-SIC company totals, per-SIC
    trademark counts, and the precomputed all-industry MEANs)."""
    if _REF:
        return _REF
    try:
        _REF["means"] = json.load(open(os.path.join(_ASSETS, "benchmark_means.json")))
    except Exception:
        _REF["means"] = {}
    try:
        _REF["tm"] = json.load(open(os.path.join(_ASSETS, "sic_tm_counts.json")))
    except Exception:
        _REF["tm"] = {}
    totals = {}
    try:
        for r in _csv.DictReader(open(os.path.join(_ASSETS, "sic_company_totals.csv"))):
            totals[r["sic"]] = {"total": int(r["total_companies"] or 0),
                                "active": int(r["active_companies"] or 0)}
    except Exception:
        pass
    _REF["totals"] = totals
    return _REF


def _sic_pred(sics, col="c.sic_codes"):
    """Build a (sic1=ANY(col) OR sic2=ANY(col) ...) predicate — the Query Runs
    engine rejects the && array-overlap operator, but ANY works."""
    parts = [f"'{_safe_sic(s)}'=ANY({col})" for s in sics]
    return "(" + " OR ".join(parts) + ")"


def sic_penetration(sics):
    """Per-SIC penetration = trademark-holding companies / all companies (CH).
    Returns list of {sic, trademarking, total_companies, penetration_pct}."""
    ref = _ref()
    out = []
    for s in sics:
        s = _safe_sic(s)
        tm = ref["tm"].get(s, {})
        tot = ref["totals"].get(s, {})
        cos = tm.get("cos", 0)
        total = tot.get("total", 0)
        out.append({"sic": s, "trademarking": cos, "total_companies": total,
                    "penetration_pct": round(cos / total * 100, 2) if total else None})
    return out


def industry_benchmark(sics) -> dict:
    """Live metrics for the company's industry = union of its SIC codes."""
    pred = _sic_pred(sics)
    join = (f"FROM companies c JOIN applicants a ON a.company_id=c.id "
            f"JOIN applicant_trademarks at ON at.applicant_id=a.id AND at.active "
            f"WHERE {pred}")
    size = run_scalar(f"SELECT count(distinct at.trademark_id) tms, "
                      f"count(distinct c.id) companies, count(distinct a.id) applicants {join}")
    per_appl = run_scalar(f"SELECT count(distinct at.trademark_id)::float/"
                          f"nullif(count(distinct a.id),0) v {join}")
    journey = run_scalar(
        f"SELECT avg(days)::float avg_days, count(*) n, "
        f"count(*) FILTER (WHERE days>=0)::float/nullif(count(*),0) frac_post "
        f"FROM (SELECT c.id, (min(t.application_date_time)::date - c.incorporation_date) days "
        f"      FROM companies c JOIN applicants a ON a.company_id=c.id "
        f"      JOIN applicant_trademarks at ON at.applicant_id=a.id AND at.active "
        f"      JOIN trademarks t ON t.id=at.trademark_id "
        f"      WHERE {pred} AND c.incorporation_date IS NOT NULL "
        f"      GROUP BY c.id, c.incorporation_date) s")
    pens = [p["penetration_pct"] for p in sic_penetration(sics) if p["penetration_pct"] is not None]
    return {
        "trademarks": size.get("tms", 0),
        "companies_trademarking": size.get("companies", 0),
        "applicants": size.get("applicants", 0),
        "trademarks_per_applicant": round(per_appl.get("v") or 0, 2),
        "penetration_pct": round(sum(pens) / len(pens), 2) if pens else None,
        "avg_years_to_first_filing": round((journey.get("avg_days") or 0) / 365.25, 2),
        "frac_post_incorporation": round(journey.get("frac_post") or 0, 3),
    }


def company_benchmark(company_number: str) -> dict:
    """The selected company's own position: its trademark count and its own
    years from incorporation to first filing."""
    n = re.sub(r"[^0-9A-Za-z]", "", str(company_number))
    row = run_scalar(
        "SELECT c.name, c.number, "
        "count(distinct at.trademark_id) tms, "
        "(min(t.application_date_time)::date - c.incorporation_date) days_to_first "
        "FROM companies c JOIN applicants a ON a.company_id=c.id "
        "JOIN applicant_trademarks at ON at.applicant_id=a.id AND at.active "
        "JOIN trademarks t ON t.id=at.trademark_id "
        f"WHERE c.number='{n}' GROUP BY c.name, c.number, c.incorporation_date")
    days = row.get("days_to_first")
    return {
        "name": row.get("name"),
        "trademarks": row.get("tms", 0),
        "years_to_first_filing": round(days / 365.25, 2) if isinstance(days, (int, float)) else None,
    }


def benchmark(company_number: str, sics) -> dict:
    """Assemble the three reference points (overall MEAN, industry, company)
    for each metric, with an ahead/behind verdict."""
    means = _ref()["means"]
    ind = industry_benchmark(sics)
    co = company_benchmark(company_number)

    def verdict(value, ref, higher_is_more=True):
        if value is None or ref in (None, 0):
            return None
        return "above" if value >= ref else "below"

    return {
        "industry": ind,
        "company": co,
        "means": means,
        "metrics": {
            "penetration_pct": {
                "mean": means.get("mean_penetration_pct"),
                "industry": ind["penetration_pct"],
                "company": None,  # penetration is a sector property
                "industry_vs_mean": verdict(ind["penetration_pct"], means.get("mean_penetration_pct")),
            },
            "trademarks_per_applicant": {
                "mean": means.get("mean_trademarks_per_applicant"),
                "industry": ind["trademarks_per_applicant"],
                "company": co["trademarks"],
                "company_vs_industry": verdict(co["trademarks"], ind["trademarks_per_applicant"]),
                "company_vs_mean": verdict(co["trademarks"], means.get("mean_trademarks_per_applicant")),
            },
            "years_to_first_filing": {
                "mean": means.get("mean_years_to_first_filing"),
                "industry": ind["avg_years_to_first_filing"],
                "company": co["years_to_first_filing"],
                # earlier filing = more proactive; "below" the average years = ahead
                "company_vs_industry": verdict(co["years_to_first_filing"], ind["avg_years_to_first_filing"]),
                "company_vs_mean": verdict(co["years_to_first_filing"], means.get("mean_years_to_first_filing")),
            },
        },
    }


# ── Sector report + its cache ────────────────────────────────────────
# Sector aggregates are the most-read, slowest-moving thing we serve: how
# many marks and companies sit in a SIC barely shifts week to week. They are
# also the ONLY part of the free report that needs Query Runs — industry
# labels come from our own 731-row SIC table and class/term recommendations
# from the local freesearch modules, so neither is at risk here.
#
# Two deliberate choices:
#
#  1. NO query_runs_ready() PROBE. It fired a `SELECT 1` before every report,
#     doubling round-trips and — worse — turning one transient blip into a
#     total failure, because a probe timeout suppressed the whole section
#     even when the real queries would have succeeded.
#
#  2. STALE-WHILE-ERROR. On failure we serve the last good result rather than
#     nothing. A visitor should never be shown a degraded report because the
#     upstream hiccuped for a few seconds. Staleness is marked so the caller
#     can tell, but sector figures a day old are indistinguishable to a
#     reader and infinitely better than a blank panel.
#
# The disk tier matters on Render: the free plan restarts the process when it
# sleeps, which would empty an in-memory cache and expose the cold start to
# the first visitor. /tmp survives for the life of the instance.

_SECTOR_TTL = 24 * 3600                      # aggregates move slowly
_SECTOR_MEM: dict = {}                       # sic -> (fetched_at, payload)
_SECTOR_DIR = os.path.join(tempfile.gettempdir(), "tmh_sector_cache")


def _sector_disk_path(key: str) -> str:
    return os.path.join(_SECTOR_DIR, f"{key}.json")


def _sector_cache_get(key: str):
    """Most recent cached payload for a SIC, or None. Ignores TTL —
    freshness is the caller's decision so it can serve stale on error."""
    hit = _SECTOR_MEM.get(key)
    if hit:
        return hit
    try:
        with open(_sector_disk_path(key), encoding="utf-8") as f:
            blob = json.load(f)
        hit = (blob["fetched_at"], blob["payload"])
        _SECTOR_MEM[key] = hit
        return hit
    except Exception:
        return None


def _sector_cache_put(key: str, payload: dict) -> None:
    now = time.time()
    _SECTOR_MEM[key] = (now, payload)
    try:
        os.makedirs(_SECTOR_DIR, exist_ok=True)
        tmp = _sector_disk_path(key) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"fetched_at": now, "payload": payload}, f)
        os.replace(tmp, _sector_disk_path(key))   # atomic
    except Exception:
        pass                                      # cache is best-effort


def sector_report(sic: str) -> dict:
    key = _safe_sic(sic)
    cached = _sector_cache_get(key)
    if cached and (time.time() - cached[0]) < _SECTOR_TTL:
        return cached[1]

    try:
        sql = _sector_sql(sic)
        out = {"available": True, "sic": key}
        size = run_sql(sql["size"]);        out["size"] = size[0] if size else {}
        ff = run_sql(sql["first_filed"]);   out["first_filed_year"] = ff[0].get("yr") if ff else None
        out["top_companies"] = run_sql(sql["top_companies"])
        out["class_distribution"] = run_sql(sql["class_distribution"])
        # An empty size row means the query "succeeded" but returned nothing —
        # treat as failure so we fall through to the cache instead of caching
        # a hollow report that renders as a broken panel.
        if not out.get("size"):
            raise RuntimeError("sector size query returned no rows")
        _sector_cache_put(key, out)
        return out
    except Exception as exc:
        if cached:
            stale = dict(cached[1])
            stale["stale"] = True
            stale["stale_age_seconds"] = int(time.time() - cached[0])
            return stale
        return {"available": False,
                "reason": f"Sector data temporarily unavailable ({type(exc).__name__})."}


# ── Applicant-name search (the other half of "find my company") ──────
# Companies House answers "does this company exist?". It cannot answer
# "does it own trademarks?" — and the register holds owners that CH does
# not: overseas companies, partnerships, individuals, and companies that
# have since dissolved. Searching only CH therefore misses real clients.
#
# Two wrinkles this has to survive:
#   1. One company appears as SEVERAL applicant records. Technical Fibre
#      Products is "…Limited" (9 marks) and "…Ltd." (8 marks) — two rows,
#      one company, 17 marks. Show them separately and we look wrong.
#   2. applicants.company_number is often NULL; the CH number lives on the
#      joined companies row instead. So we coalesce the two.

_SUFFIXES = (" limited", " ltd", " plc", " llp", " lp", " inc", " incorporated",
             " corporation", " corp", " company", " co", " gmbh", " sa", " nv",
             " bv", " ag", " srl", " spa", " pty", " oy", " ab", " as")


def norm_company_name(name: str) -> str:
    """Comparable form of a company name: lowercase, no punctuation, no
    legal suffix. 'Technical Fibre Products Ltd.' and '…PRODUCTS LIMITED'
    both become 'technical fibre products'."""
    s = re.sub(r"[^0-9a-z ]", " ", str(name or "").lower())
    s = re.sub(r"\s+", " ", s).strip()
    for _ in range(2):                      # "…Holdings Ltd Co" etc.
        for suf in _SUFFIXES:
            if s.endswith(suf):
                s = s[: -len(suf)].strip()
                break
    return s


def search_applicants(name: str, *, limit: int = 25):
    """Trademark owners whose NAME matches — grouped to one row per real
    company. Each item:
      {name, display_name, company_number, ipo_identifiers:[...],
       n_marks, kind, norm}
    Ordered by portfolio size, because the biggest owner of a name is
    almost always the one the visitor means.
    """
    q = _sanitise_phrase(name)
    if len(q) < 3:
        return []
    rows = run_sql(
        "SELECT a.name, a.ipo_identifier, a.kind, "
        "COALESCE(a.company_number, c.number) AS company_number, "
        "c.name AS ch_name, "
        "COUNT(DISTINCT apt.trademark_id) AS n_marks "
        "FROM applicants a "
        "LEFT JOIN companies c ON c.id = a.company_id "
        "LEFT JOIN applicant_trademarks apt "
        "  ON apt.applicant_id = a.id AND apt.active "
        f"WHERE a.name ILIKE '%{q}%' "
        "GROUP BY a.name, a.ipo_identifier, a.kind, "
        "         COALESCE(a.company_number, c.number), c.name "
        f"ORDER BY n_marks DESC LIMIT {int(limit) * 4}")

    grouped: dict = {}
    for r in rows:
        num = (r.get("company_number") or "").strip() or None
        nrm = norm_company_name(r.get("ch_name") or r.get("name"))
        key = num or nrm                    # CH number wins; else the name
        g = grouped.setdefault(key, {
            "name": r.get("ch_name") or r.get("name"),
            "display_name": r.get("ch_name") or r.get("name"),
            "company_number": num, "ipo_identifiers": [], "n_marks": 0,
            "kind": r.get("kind"), "norm": nrm, "variants": []})
        g["ipo_identifiers"].append(r.get("ipo_identifier"))
        g["variants"].append(r.get("name"))
        g["n_marks"] += int(r.get("n_marks") or 0)
        if num and not g["company_number"]:
            g["company_number"] = num
    out = [g for g in grouped.values() if g["n_marks"] > 0]
    out.sort(key=lambda g: -g["n_marks"])
    return out[:int(limit)]


def applicant_marks(ipo_identifiers, *, limit: int = 200):
    """Every mark held by a set of applicant records (the variants of one
    company), newest first. Used when there is no CH number to join on."""
    ids = [int(i) for i in (ipo_identifiers or []) if i is not None]
    if not ids:
        return []
    inlist = ",".join(str(i) for i in ids)
    # NOTE: Query Runs cannot PROJECT a raw date/timestamp column — SELECT or
    # ORDER BY on `application_date_time` / `expiry_date` returns a 500. They
    # are fine inside a WHERE clause (which is why the corpus filter works),
    # and fine wrapped in to_char(). So: format dates as text, and sort by
    # application_number, which rises over time and gives the same
    # newest-first order without touching a date column.
    return run_sql(
        "SELECT DISTINCT mk.verbal_element_text AS mark, t.status, "
        "       t.application_number, "
        "       to_char(t.expiry_date, 'DD Mon YYYY') AS expires "
        "FROM applicants a "
        "JOIN applicant_trademarks apt ON apt.applicant_id = a.id AND apt.active "
        "JOIN trademarks t ON t.id = apt.trademark_id "
        "JOIN marks mk ON mk.trademark_id = t.id "
        f"WHERE a.ipo_identifier IN ({inlist}) "
        f"ORDER BY t.application_number DESC LIMIT {int(limit)}")

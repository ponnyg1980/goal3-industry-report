"""
The Trademark Helpline — report engine as a JSON API.

WHY THIS EXISTS
The report logic (Temmy queries, empirical banding, viability scoring, SIC
naming) is finished and correct, but it lived only inside a Streamlit app.
Streamlit renders its own single-page app, so it can't BE a page on
thetrademarkhelpline.com — only sit in an iframe on one. This API exposes the
exact same engine as plain JSON (plus a few pre-rendered brandkit fragments
for the heavy visual components), so native HTML pages on the WordPress site
can call it and render as first-class pages: real URLs, real SEO, no iframe.

The engine modules are imported unchanged — this file is a thin transport
layer, not a reimplementation. One source of truth.

Run locally:   uvicorn api.main:app --reload --port 8000
Deploy:        Cloud Run (see api/Dockerfile) behind api.thetrademarkhelpline.com
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# The engine lives one level up; import it as-is.
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for p in (str(_ROOT),):
    if p not in sys.path:
        sys.path.insert(0, p)

import data_access as da            # noqa: E402
import companies_house as ch        # noqa: E402
import recommend as rec             # noqa: E402
import resolve as rsv               # noqa: E402
import viability as vb              # noqa: E402
import assessment as asmt           # noqa: E402
import brandkit as bk               # noqa: E402
import risk as rsk                  # noqa: E402

app = FastAPI(title="TMH Report Engine", version="1.0")

# Only our own pages may call this. Extend the list for partner embeds.
_ALLOWED = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS",
    "https://www.thetrademarkhelpline.com,https://thetrademarkhelpline.com"
).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=_ALLOWED, allow_methods=["GET", "POST"],
    allow_headers=["*"], max_age=3600)


@app.get("/health")
def health():
    return {"ok": da.api_ready() and da.health(),
            "sector": da.query_runs_ready()}


# ── 1. find a company / owner (the two-register merge) ────────────────
@app.get("/find")
def find(q: str):
    """resolve.find — Companies House AND the trademark register, merged.
    Returns the four scenarios (both / ch_only / register_only / none)."""
    if len((q or "").strip()) < 3:
        return {"candidates": []}
    cands = rsv.find(q, limit=10)
    # CH search doesn't return SICs — backfill them for the whole list in one
    # query so the picker can show the sector, which (with the postcode) helps
    # the visitor pick the right organisation.
    nums = [c.get("company_number") for c in cands if c.get("company_number")]
    try:
        sics_by_num = da.company_sics_bulk(nums)
    except Exception:
        sics_by_num = {}
    out = []
    for c in cands:
        sics = c.get("sic_codes") or []
        num = c.get("company_number")
        if not sics and num:
            key = "".join(ch for ch in str(num) if ch.isalnum())
            sics = sics_by_num.get(key) or sics_by_num.get(str(num)) or []
        sic1 = str(sics[0]) if sics else None
        out.append({
            "key": c.get("key"), "name": c.get("display_name"),
            "company_number": num,
            "status": c.get("status"), "sic_codes": sics,
            "sic": sic1,
            "sic_desc": bk.sic_description(sic1) if sic1 else None,
            "postcode": c.get("postcode"),
            "address": c.get("address"),
            "n_marks": c.get("n_marks", 0),
            "ipo_identifiers": c.get("ipo_identifiers") or [],
            "scenario": c.get("scenario"), "label": rsv.label(c)})
    return {"candidates": out}


class OwnerReq(BaseModel):
    company_number: str | None = None
    ipo_identifiers: list[int] = []


@app.post("/owner-marks")
def owner_marks(req: OwnerReq):
    rows = rsv.marks_for({"company_number": req.company_number,
                          "ipo_identifiers": req.ipo_identifiers}, limit=200)
    return {"marks": rows}


# ── 2. resolve the sector (SICs → named industry) ────────────────────
@app.get("/company/{number}")
def company(number: str):
    prof = ch.profile(number)
    if not prof:
        raise HTTPException(404, "Company not found")
    sics = prof.get("sic_codes") or []
    return {"name": prof.get("name"), "number": number,
            "sic_codes": sics, "sics_named": _name_sics(sics),
            "incorporated": prof.get("incorporated")}


@app.get("/business-types")
def business_types(sics: str = "", q: str = ""):
    """Candidate business types for a SIC set, or the full list for search."""
    if sics:
        cands = rec.candidate_types([s for s in sics.split(",") if s])
        return {"types": cands}
    allt = rec.all_types()
    if q:
        allt = [t for t in allt if q.lower() in t.lower()]
    return {"types": [{"business_type": t} for t in allt]}


@app.get("/sector")
def sector(sic: str):
    rep = da.sector_report(sic)
    rep["sic_label"] = bk.sic_label(sic)
    rep["sic_section"] = bk.sic_section(sic)
    return rep


@app.get("/industries")
def industries(q: str = "", limit: int = 12):
    """Search the SIC catalogue by plain-English description → the 'confirm
    your industry' picker on Input 1.

    Companies House SICs are frequently generic, stale, or simply absent
    (overseas applicants, sole traders, trading names). Letting a visitor
    confirm or correct their industry means the sector report benchmarks
    against the RIGHT peer group, not whatever code the register happens to
    hold. Each result maps 1:1 to a SIC the sector engine already understands.
    """
    ql = (q or "").strip().lower()
    if len(ql) < 2:
        return {"industries": []}
    tbl = bk._sic_table()                 # {code: (section_letter, description)}
    hits = []
    for code, row in tbl.items():
        desc = row[1]
        pos = desc.lower().find(ql)
        if pos < 0:
            continue
        # earlier match + shorter description rank higher (tighter relevance)
        hits.append(((0 if desc.lower().startswith(ql) else 1, pos, len(desc)),
                     {"sic": code, "label": desc, "section": bk.sic_section(code)}))
    hits.sort(key=lambda h: h[0])
    n = max(1, min(int(limit or 12), 30))
    return {"industries": [h[1] for h in hits[:n]]}


# ── 3. recommendations ───────────────────────────────────────────────
@app.get("/classes")
def classes(sics: str = "", business_type: str = ""):
    if business_type:
        return rec.class_recommendations_for_type(business_type)
    return rec.class_recommendations([s for s in sics.split(",") if s])


@app.get("/terms")
def terms(sics: str, cls: int):
    return rec.term_recommendations([s for s in sics.split(",") if s], cls)


# ── benchmark: "how you compare" (mean / sector / this company) ──────
@app.get("/benchmark")
def benchmark(sics: str, number: str = ""):
    """da.benchmark — sector penetration vs all-industry mean, trademarks
    per applicant, and years-to-first-filing, each with an ahead/behind
    verdict. Powers the report's 'How you compare' section."""
    return da.benchmark(number, [s for s in sics.split(",") if s])


# ── similar marks: conflict counts + the marks like this name ────────
@app.get("/similar")
def similar(name: str, classes: str = "", own: str = ""):
    """risk.assess over data_access.similar_marks — the register rows whose
    verbal element could conflict with `name`, banded High/Medium/Low with
    own marks excluded. Powers Reveal 2's viability dials (conflict drag) and
    the 'marks like yours on the register' table.

    `classes` is an optional comma list of the user's kept Nice classes; a
    similar mark in the SAME class scores higher than one in a distant class.
    `own` is the applicant/company name(s) to exclude — so an owner already on
    the register isn't shown as a conflict against itself.
    """
    if len((name or "").strip()) < 2:
        return {"counts": {}, "marks": [], "total_candidates": 0}
    rows = da.similar_marks(name, limit=300)
    tcls = [int(c) for c in classes.split(",") if c.strip().isdigit()]
    owns = [o.strip() for o in own.split("|") if o.strip()]
    res = rsk.assess(rows, brand=name, target_classes=tcls,
                     own_applicant_names=owns, limit=25)
    marks = [{
        "mark": r.get("verbal_element_text") or "",
        "owner": r.get("applicant_name") or "—",
        "classes": r.get("classes") or [],
        "status": r.get("status") or "",
        "risk": r.get("risk") or "",
        "score": r.get("score"),
    } for r in res.get("marks", [])]
    c = res.get("counts", {})
    return {
        "counts": {
            "high": c.get("High Risk", 0),
            "medium": c.get("Medium Risk", 0),
            "low": c.get("Low Risk", 0),
            "negligible": c.get("Negligible", 0),
        },
        "marks": marks,
        "total_candidates": res.get("total_candidates", 0),
    }


# ── 4. viability (dials) — JSON scores + the rendered CSS gauge ───────
class ViabilityReq(BaseModel):
    name: str
    n_similar: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    years: float | None = None


@app.post("/viability")
def viability(req: ViabilityReq):
    v = vb.compute(name=req.name, n_similar=req.n_similar, high=req.high,
                   medium=req.medium, low=req.low, years=req.years)
    return {"scores": v, "gauge_html": vb.gauge_html(v)}


# ── 5. assessment (3 questions → banded result) ──────────────────────
class AssessReq(BaseModel):
    q1: int
    q2_flags: list[int] = []
    q2_none: bool = False
    q3: int
    n_similar: int = 0


@app.post("/assessment")
def assessment(req: AssessReq):
    res = asmt.score(req.q1, req.q2_flags, req.q2_none, req.q3)
    copy = asmt.result_copy(res, n_similar=req.n_similar)
    return {"result": res, "copy": copy}


@app.get("/assessment/questions")
def assessment_questions():
    return {"q1": asmt.Q1, "q2": asmt.Q2, "q3": asmt.Q3}


def _name_sics(sics):
    return [{"code": c, "description": bk.sic_description(c),
             "section": bk.sic_section(c), "label": bk.sic_label(c)}
            for c in (sics or [])]

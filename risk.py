"""
Risk banding for the industry report — SAME rules as the Braudit Audit
Report tool (deploy-v2-hotfix/filters.py), vendored here so goal3 deploys
self-contained. If the Braudit rubric changes, update this copy.

Word-axis score (out of ~11+):
    Status:      Registered +4 · Pending +3 · Ended 0
    Similarity:  Exact +4 · Starts-with +2 · Contains (whole word) +2
                 · fuzzy >= .85 +2 · fuzzy >= .78 +1   (max component kept)
    Mark type:   Word +2 · Combined +1 · Stylised +1
    Classes:     +1 per Nice class overlapping the target classes

Bands (risk_from_score, identical thresholds to Braudit):
    Ended -> Negligible · >= 11 High Risk · 8-10 Medium Risk · <= 7 Low Risk
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# Semantic risk colours — match brand_tokens.py (stable across rebrands).
RISK_COLOUR = {
    "High Risk": "#C00000",     # dark red
    "Medium Risk": "#F4B084",   # orange
    "Low Risk": "#C5E0B4",      # green
    "Negligible": "#9AA5AE",    # grey
}
RISK_TEXT = {  # readable text colour on each chip
    "High Risk": "#FFFFFF", "Medium Risk": "#1D1D1B",
    "Low Risk": "#1D1D1B", "Negligible": "#FFFFFF",
}


def _norm_status(status: str) -> str:
    s = (status or "").lower()
    if "regist" in s:
        return "registered"
    if "pend" in s or "applic" in s or "examin" in s:
        return "pending"
    if any(k in s for k in ("end", "dead", "expir", "withdraw", "refus",
                            "remov", "surrender")):
        return "ended"
    return s or "unknown"


def _similarity_score(mark: str, brand: str) -> int:
    """Braudit mark-similarity component (BR-013 semantics, single brand
    phrase): Exact +4, Starts-with +2, Contains-as-word +2, fuzzy tiers."""
    m = re.sub(r"\s+", " ", (mark or "").upper().strip())
    b = re.sub(r"\s+", " ", (brand or "").upper().strip())
    if not m or not b:
        return 0
    if m == b:
        return 4
    best = 0
    if m.startswith(b + " ") or m.startswith(b + "-"):
        best = 2
    if re.search(r"(?:^|[\s\-])" + re.escape(b) + r"(?:$|[\s\-])", m):
        best = max(best, 2)
    # fuzzy: whole-string OR best token-level ratio
    ratios = [SequenceMatcher(None, m, b).ratio()]
    ratios += [SequenceMatcher(None, tok, b).ratio() for tok in m.split()]
    r = max(ratios)
    if r >= 0.85:
        best = max(best, 2)
    elif r >= 0.78:
        best = max(best, 1)
    return best


def _type_score(mark_type: str) -> int:
    t = (mark_type or "").lower()
    if "combined" in t or "stylis" in t or "styliz" in t:
        return 1
    if "word" in t:
        return 2
    return 0


def risk_from_score(score: int, status: str) -> str:
    """Identical thresholds to Braudit filters.risk_from_score()."""
    if _norm_status(status) == "ended":
        return "Negligible"
    if score >= 11:
        return "High Risk"
    if score >= 8:
        return "Medium Risk"
    return "Low Risk"


def score_mark(*, mark_text: str, brand: str, status: str, mark_type: str,
               classes: list[int], target_classes: set[int]) -> dict:
    st = _norm_status(status)
    score = {"registered": 4, "pending": 3}.get(st, 0)
    score += _similarity_score(mark_text, brand)
    score += _type_score(mark_type)
    overlap = sum(1 for c in classes or [] if c in target_classes)
    score += overlap
    return {"score": score, "risk": risk_from_score(score, status),
            "class_overlap": overlap}


def assess(rows: list[dict], *, brand: str, target_classes,
           own_applicant_names=(), limit: int = 25) -> dict:
    """Score candidate register rows (from data_access.similar_marks) and
    return {counts, marks} — highest risk first, own marks excluded."""
    tgt = {int(c) for c in target_classes or []}
    own = {(n or "").strip().upper() for n in own_applicant_names}
    scored = []
    for r in rows:
        appl = (r.get("applicant_name") or "").strip()
        if appl.upper() in own:
            continue
        classes = r.get("classes") or []
        if not isinstance(classes, list):
            classes = [int(p) for p in re.split(r"[,\s{}]+", str(classes))
                       if p.strip().isdigit()]
        s = score_mark(mark_text=r.get("verbal_element_text") or "",
                       brand=brand, status=r.get("status") or "",
                       mark_type=r.get("mark_type") or "",
                       classes=[int(c) for c in classes if str(c).isdigit()
                                or isinstance(c, int)],
                       target_classes=tgt)
        scored.append({**r, **s})
    order = {"High Risk": 0, "Medium Risk": 1, "Low Risk": 2, "Negligible": 3}
    scored.sort(key=lambda x: (order.get(x["risk"], 9), -x["score"]))
    counts = {b: sum(1 for x in scored if x["risk"] == b) for b in order}
    return {"counts": counts, "marks": scored[:limit],
            "total_candidates": len(scored)}

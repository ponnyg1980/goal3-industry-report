"""Find the company — Companies House AND the trademark register, together.

The report used to search Companies House alone. That answers "does this
company exist?" but not "does it own trademarks?", and it silently loses
owners CH has never heard of: overseas companies, partnerships, individuals,
and companies dissolved before the register forgot them.

So we ask both, and merge. Four outcomes, each a different journey:

  1. CH + register   → the full report. Show the applicant name, the
                       portfolio size, and let them view the marks.
  2. CH only         → real company, no marks. The report still works; the
                       trademark section says so honestly. This is the
                       best-fit prospect: they exist and own nothing.
  3. Neither         → nothing to anchor to. Route to Trading Name Mode.
  4. Register only   → they own marks but are not a UK company (or not
                       under this name). Pull the marks; sector data comes
                       from the marks' classes rather than a SIC.

Matching rule: CH number when both sides have one; otherwise the normalised
name (case, punctuation and legal suffix stripped) — because
applicants.company_number is frequently NULL and 'Ltd.' vs 'LIMITED' is not
a different company.
"""
from __future__ import annotations

import data_access as da
import companies_house as ch


def _norm(s):
    return da.norm_company_name(s)


def find(name: str, *, limit: int = 10) -> list[dict]:
    """Merged candidate list, best first. Each candidate:

      {key, display_name, company_number, status, sic_codes,
       n_marks, ipo_identifiers, scenario, on_ch, on_register}

    `scenario` is one of 'both' | 'ch_only' | 'register_only', matching the
    numbering above (3 is the empty list).
    """
    name = (name or "").strip()
    if len(name) < 3:
        return []

    ch_hits = []
    if ch.ready():
        try:
            ch_hits = ch.search(name, limit=limit) or []
        except Exception:
            ch_hits = []
    try:
        tm_hits = da.search_applicants(name, limit=limit) or []
    except Exception:
        tm_hits = []

    merged: dict = {}

    for h in ch_hits:
        num = (h.get("company_number") or "").strip()
        key = num or _norm(h.get("title"))
        merged[key] = {
            "key": key, "display_name": h.get("title"),
            "company_number": num or None, "status": h.get("status"),
            "sic_codes": h.get("sic_codes") or [],
            "address": h.get("address"), "postcode": h.get("postcode"),
            "n_marks": 0, "ipo_identifiers": [],
            "on_ch": True, "on_register": False,
            "norm": _norm(h.get("title")),
        }

    for g in tm_hits:
        num = (g.get("company_number") or "").strip() or None
        nrm = g.get("norm") or _norm(g.get("display_name"))
        # Prefer an exact CH-number match; fall back to the normalised name,
        # which is how we catch the 'not on CH under this number' cases.
        key = None
        if num and num in merged:
            key = num
        else:
            key = next((k for k, v in merged.items() if v["norm"] == nrm), None)
        if key is None:
            key = num or nrm
            merged[key] = {
                "key": key, "display_name": g.get("display_name"),
                "company_number": num, "status": None, "sic_codes": [],
                "n_marks": 0, "ipo_identifiers": [],
                "on_ch": False, "on_register": False, "norm": nrm,
            }
        c = merged[key]
        c["on_register"] = True
        c["n_marks"] += int(g.get("n_marks") or 0)
        c["ipo_identifiers"] += [i for i in (g.get("ipo_identifiers") or [])
                                 if i is not None]
        if num and not c["company_number"]:
            c["company_number"] = num

    for c in merged.values():
        c["scenario"] = ("both" if c["on_ch"] and c["on_register"]
                         else "ch_only" if c["on_ch"] else "register_only")

    out = list(merged.values())
    # A trademark owner is a warmer, more certain match than a bare name on
    # the CH index, so portfolio size leads; then CH-registered; then name.
    out.sort(key=lambda c: (-c["n_marks"], not c["on_ch"],
                            c["display_name"] or ""))
    return out[:limit]


def label(c: dict) -> str:
    """One line for the selectbox — the number of marks is the thing the
    visitor recognises, so it goes where the eye lands."""
    bits = [c.get("display_name") or "—"]
    if c.get("company_number"):
        bits.append(c["company_number"])
    if c.get("status"):
        bits.append(str(c["status"]).title())
    tail = " · ".join(bits)
    n = c.get("n_marks") or 0
    if n:
        tail += f"  —  {n} trademark{'s' if n != 1 else ''}"
    elif c.get("on_ch"):
        tail += "  —  no trademarks found"
    return tail


def marks_for(c: dict, *, limit: int = 200):
    """Every mark this candidate holds. Uses the CH-number join when we have
    one (it catches applicant records our name search missed), otherwise the
    applicant ids we matched on."""
    if c.get("company_number"):
        try:
            rows = da.company_marks(c["company_number"], limit=limit)
            if rows:
                return rows
        except Exception:
            pass
    return da.applicant_marks(c.get("ipo_identifiers"), limit=limit)

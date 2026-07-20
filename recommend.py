"""
Goal #1/#3 — Classes & Terms Recommendations.

RECONCILED (18 Jul 2026): this module no longer carries its own class logic.
It delegates to the shared `freesearch` engine so the report, the free-search
wizard and the class-assistant widget all show the SAME numbers from the SAME
source. Previously goal3 rolled its own SQL and bands (Always/Often at 25/15,
counted by trademark, whole register) which drifted from everything else.

What the shared engine brings here:
  • Corpus = UK Registered marks, last 3 years, Company/Organisation applicants.
  • Bands  = All use this / Most use this / Some use this / A few have this
             (from freesearch.bands — the one place the words live).
  • Empirical seed → instant (no 25s live aggregation per report).
  • Inconclusive SICs (70229 etc.) are flagged and routed, not guessed.
  • Business-type view (SaaS vs Fintech vs Cybersecurity, all SIC 62012) with
    characteristic TERMS — because the class number alone is ambiguous and the
    description is what tells a designer's class 42 from a coder's.

The public shape is unchanged, so branded_report.py / app.py keep working:
  class_recommendations(sics) -> {total, classes:[{class,heading,trademarks,
                                   pct,band,colour, share,tier,terms}], ...}
  term_recommendations(sics, cls) -> {class_total, terms:[{term,trademarks,
                                       pct,band,colour}]}
"""
from __future__ import annotations

import sys
from pathlib import Path

# The engine is vendored into this repo (goal3/freesearch/, see vendor_engine.py)
# so goal3 deploys self-contained. Ensure this dir is importable, then use the
# vendored package — never the parent's, so local == Cloud.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from freesearch.sic_engine import map_sic_codes            # noqa: E402
from freesearch.bands import TIER_LABELS, tier_for          # noqa: E402
from freesearch import taxonomy as _tx                      # noqa: E402
from freesearch.nice_labels import short as _short          # noqa: E402

try:
    from nice_classes import NICE_HEADINGS                   # full official headings
except Exception:                                            # pragma: no cover
    NICE_HEADINGS = {}

# Tier -> display colour (kept close to the old palette so the report styling
# needs no change; strongest = black, weakest = red).
TIER_COLOUR = {'a': '#1D1D1B', 'b': '#2E7D32', 'c': '#E69500', 'd': '#C0392B'}


def _heading(cls: int) -> str:
    return NICE_HEADINGS.get(cls) or _short(cls)


def _row(c: dict) -> dict:
    """Map an engine class row to the report's shape (+ new fields)."""
    tier = c.get('tier', 'd')
    share = c.get('share')
    return {
        'class': c['nice_class'],
        'heading': _heading(c['nice_class']),
        'class_label': c.get('class_label') or _short(c['nice_class']),
        'trademarks': c.get('n_marks'),          # may be None for concordance
        'pct': round((share or 0) * 100, 1),
        'share': share,
        'tier': tier,
        'band': TIER_LABELS.get(tier, ''),       # "All use this" etc.
        'colour': TIER_COLOUR.get(tier, '#C0392B'),
        'terms': c.get('terms') or [],
    }


def class_recommendations(sics) -> dict:
    """Per Nice class for the company's SIC(s), banded, from the shared engine.

    Returns total=0 with `inconclusive`/`message`/`routes` when the SIC(s)
    describe no goods or services (point 8), so the report can route the user
    to the competitor-mark / website / description tools instead of guessing.
    """
    m = map_sic_codes(sics)
    if m.get('inconclusive'):
        return {'total': 0, 'classes': [], 'inconclusive': True,
                'message': m.get('message'), 'routes': m.get('routes', []),
                'inconclusive_sics': m.get('inconclusive_sics', [])}
    classes = [_row(c) for c in m.get('classes', [])]
    total = sum(c['trademarks'] for c in classes if c['trademarks']) or len(classes)
    return {'total': total, 'classes': classes,
            'method': m.get('method'),
            'skipped_inconclusive': m.get('skipped_inconclusive', [])}


def class_recommendations_for_type(business_type: str) -> dict:
    """Business-type view — the clean split the SIC alone can't give.

    Reads the classification sweep's type_seed (SaaS vs Fintech vs Cybersecurity
    etc.), including the characteristic terms per type. Falls back to the SIC
    view when the type isn't banded.
    """
    import json
    seed = _HERE / 'freesearch' / 'data' / 'type_seed.json'
    data = json.loads(seed.read_text()) if seed.exists() else {}
    rec = data.get(business_type)
    if not rec:
        # fall back to the type's SIC(s)
        sics = _type_sics(business_type)
        out = class_recommendations(sics) if sics else {'total': 0, 'classes': []}
        out['business_type'] = business_type
        out['source'] = 'sic-fallback'
        return out
    classes = []
    for c in rec['classes']:
        tier = c.get('band') or tier_for(c.get('share', 0))
        classes.append({
            'class': c['nice_class'], 'heading': _heading(c['nice_class']),
            'class_label': _short(c['nice_class']),
            'trademarks': c.get('n_marks'), 'pct': round(c.get('share', 0) * 100, 1),
            'share': c.get('share'), 'tier': tier,
            'band': TIER_LABELS.get(tier, ''), 'colour': TIER_COLOUR.get(tier, '#C0392B'),
        })
    return {'business_type': business_type, 'source': 'sweep',
            'total': rec.get('total_marks', 0), 'classes': classes,
            'terms': rec.get('terms', [])}


def type_sics(business_type: str) -> list[str]:
    """The SIC codes behind a business type (public — the report uses these
    for term lookups when the user picks a type outside the company's SIC)."""
    return _type_sics(business_type)


def _type_sics(business_type: str) -> list[str]:
    for _sector, types in _tx.SECTORS.items():
        if business_type in types:
            return [str(c) for c in types[business_type]]
    return []


def candidate_types(sics) -> list[dict]:
    """Business types that share the company's SIC(s) — the toggle options.

    A SIC like 62012 covers ten different business types (SaaS, fintech,
    cybersecurity…) that file very differently; the SIC view blends them. This
    returns the candidates so the report can ask "which one is this company?"
    and switch to the sweep's per-type bands. Types with sweep data first
    (they get the confirmed cohort + characteristic terms), then the rest.
    """
    import json
    if isinstance(sics, str):
        sics = [sics]
    wanted = {str(s).strip() for s in (sics or []) if str(s).strip()}
    seed = _HERE / 'freesearch' / 'data' / 'type_seed.json'
    swept = set(json.loads(seed.read_text())) if seed.exists() else set()
    out = []
    for sector, types in _tx.SECTORS.items():
        for name, codes in types.items():
            if wanted & {str(c) for c in codes}:
                out.append({'business_type': name, 'sector': sector,
                            'has_sweep_data': name in swept})
    out.sort(key=lambda d: (not d['has_sweep_data'], d['business_type']))
    return out


def all_types() -> list[str]:
    """Every business type in the taxonomy (for the 'something else' search)."""
    return sorted(n for types in _tx.SECTORS.values() for n in types)


def term_recommendations(sics, cls: int, limit: int = 25) -> dict:
    """Top goods/services terms within one class for the industry.

    Now served from the empirical seed (already attached to each class by the
    engine) — instant, and identical to what the widget shows. No live query.
    """
    cls = int(cls)
    m = map_sic_codes(sics)
    row = next((c for c in m.get('classes', []) if c['nice_class'] == cls), None)
    terms = (row or {}).get('terms') or []
    out = []
    for t in terms[:limit]:
        tier = t.get('band', 'd')
        share = t.get('share')
        out.append({'term': t['text'], 'trademarks': t.get('n_marks'),
                    'pct': round((share or 0) * 100, 1),
                    'tier': tier,
                    'band': TIER_LABELS.get(tier, ''),
                    'colour': TIER_COLOUR.get(tier, '#C0392B')})
    return {'class_total': (row or {}).get('n_marks', 0), 'terms': out}


# Back-compat: some callers imported NICE_HEADINGS from here.
__all__ = ['class_recommendations', 'class_recommendations_for_type',
           'term_recommendations', 'candidate_types', 'all_types', 'type_sics',
           'NICE_HEADINGS']

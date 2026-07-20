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


def _type_sics(business_type: str) -> list[str]:
    for _sector, types in _tx.SECTORS.items():
        if business_type in types:
            return [str(c) for c in types[business_type]]
    return []


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
           'term_recommendations', 'NICE_HEADINGS']

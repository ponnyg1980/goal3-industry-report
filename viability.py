"""Trademark Viability Score (item 4, 20 Jul).

Four indicators, each 0–100, shown as radial gauges, plus a master score.

  Uniqueness      — how alone the name is on the register (fewer similar
                    marks found = higher).
  Conflicts       — how dangerous the similar marks are (High weighs far
                    more than Medium; Low barely counts).
  Distinctiveness — how protectable the wording is in law. Trademark
                    strength runs generic → descriptive → suggestive →
                    invented; "SUSTAINABLE WEALTH MANAGEMENT" is three
                    descriptive words, "MONZO" is invented. We count how
                    much of the name is ordinary trade language.
  Proof of Use    — time in genuine use (Companies House incorporation, or
                    the stated trading-name years). Use builds unregistered
                    rights and answers "when did you start?".

MASTER: weighted blend, floored at 50 — deliberately. Below-50 theatre
serves nobody: there is always a route (evidence, narrowing, a rework of a
descriptive element), so the floor encodes "this is fixable" while the
gauges show honestly WHERE the work is.

The gauges are pure HTML/CSS (conic-gradient) — no charting dependency, so
the container stays slim and the same markup can go into the branded PDF.
"""
from __future__ import annotations

import re
from datetime import date

WEIGHTS = {'conflicts': 0.35, 'uniqueness': 0.25,
           'distinctiveness': 0.20, 'proof_of_use': 0.20}
MASTER_FLOOR = 50

# Ordinary trade language that weakens a mark. Deliberately generic-only —
# sector-specific descriptive terms come in via `sector_terms` at call time
# (the sweep's characteristic terms: a wealth manager's "wealth management"
# is descriptive FOR THEM, distinctive for a bakery).
GENERIC_WORDS = {
    'uk', 'gb', 'ltd', 'limited', 'plc', 'llp', 'group', 'holdings', 'co',
    'company', 'the', 'and', 'of', 'services', 'service', 'solutions',
    'consulting', 'consultancy', 'management', 'partners', 'associates',
    'international', 'global', 'national', 'direct', 'online', 'digital',
    'pro', 'plus', 'premier', 'premium', 'quality', 'first', 'best',
    'smart', 'easy', 'simple', 'express', 'sustainable', 'green', 'eco',
    'new', 'modern', 'classic', 'london', 'british', 'england', 'scotland',
    'wales',
}


def _clamp(x):
    return max(0, min(100, round(x)))


def uniqueness(n_similar: int) -> int:
    """95 when the register shows nothing like it, sliding down as the
    crowd grows. 50 similar marks ≈ a very busy name."""
    return _clamp(95 - n_similar * 1.6)


def conflicts(high: int, medium: int, low: int) -> int:
    """High risks dominate: one High costs more than ten Lows."""
    return _clamp(100 - (high * 22 + medium * 4 + low * 0.8))


def distinctiveness(name: str, sector_terms=()) -> int:
    """Share of the name that is NOT ordinary/sector trade language.
    Invented or arbitrary words score high; a name made entirely of
    descriptive words scores low (but never zero — stylisation, logos and
    acquired distinctiveness are all still routes)."""
    words = [w for w in re.split(r'[^a-z0-9]+', (name or '').lower()) if w]
    if not words:
        return 50
    sector_vocab = set()
    for t in sector_terms or []:
        sector_vocab.update(re.split(r'[^a-z0-9]+', str(t).lower()))
    descriptive = sum(1 for w in words
                      if w in GENERIC_WORDS or w in sector_vocab)
    share_distinctive = 1 - descriptive / len(words)
    # scale 20..95: all-descriptive isn't hopeless, all-invented isn't perfect
    return _clamp(20 + share_distinctive * 75)


def proof_of_use(years: float | None) -> int:
    """0 years = 25 (starting isn't a fault, it's just less evidence);
    10+ years of use ≈ as strong as this axis gets."""
    if not years or years <= 0:
        return 25
    return _clamp(25 + min(years, 10) / 10 * 70)


def years_since(iso_date: str | None) -> float | None:
    try:
        y, m, d = str(iso_date).split('-')
        return round((date.today() - date(int(y), int(m), int(d))).days / 365.25, 1)
    except Exception:
        return None


def master(scores: dict) -> int:
    m = sum(scores[k] * w for k, w in WEIGHTS.items())
    return max(MASTER_FLOOR, round(m))


def compute(*, name: str, n_similar: int, high: int, medium: int, low: int,
            years: float | None, sector_terms=()) -> dict:
    s = {
        'uniqueness': uniqueness(n_similar),
        'conflicts': conflicts(high, medium, low),
        'distinctiveness': distinctiveness(name, sector_terms),
        'proof_of_use': proof_of_use(years),
    }
    return {'scores': s, 'master': master(s)}


# ── rendering (HTML/CSS radial gauges; Streamlit + branded report) ──────────

LABELS = {
    'uniqueness': ('Uniqueness', 'How alone your name is on the register'),
    'conflicts': ('Conflicts', 'How serious the similar marks are'),
    'distinctiveness': ('Distinctiveness', 'How protectable the wording is'),
    'proof_of_use': ('Proof of Use', 'Time in genuine use'),
}


def _colour(v: int) -> str:
    if v >= 70:
        return '#2E7D32'
    if v >= 45:
        return '#E69500'
    return '#C0392B'


def gauge_html(result: dict, *, brand_hex: str = '#1D1D1B') -> str:
    g = []
    for key, (label, sub) in LABELS.items():
        v = result['scores'][key]
        c = _colour(v)
        g.append(f"""
  <div class="vg">
    <div class="dial" style="background:
      conic-gradient({c} {v * 3.6}deg, #ECEFF1 0deg)">
      <div class="hole"><span>{v}</span></div>
    </div>
    <b>{label}</b><small>{sub}</small>
  </div>""")
    m = result['master']
    mc = _colour(m)
    return f"""
<div class="viability">
  <div class="master">
    <div class="dial big" style="background:
      conic-gradient({mc} {m * 3.6}deg, #ECEFF1 0deg)">
      <div class="hole"><span>{m}%</span></div>
    </div>
    <b>Trademark Viability</b>
    <small>Never below {MASTER_FLOOR}% — there is always a route; the dials
    show where the work is.</small>
  </div>
  <div class="gauges">{''.join(g)}</div>
</div>
<style>
.viability{{display:flex;gap:28px;align-items:center;flex-wrap:wrap;
  font-family:inherit;margin:6px 0 2px}}
.viability .master{{text-align:center;max-width:190px}}
.viability .gauges{{display:flex;gap:22px;flex-wrap:wrap}}
.viability .vg{{text-align:center;width:110px}}
.viability .dial{{width:92px;height:92px;border-radius:50%;margin:0 auto 6px;
  display:flex;align-items:center;justify-content:center}}
.viability .dial.big{{width:150px;height:150px}}
.viability .hole{{width:70%;height:70%;background:#fff;border-radius:50%;
  display:flex;align-items:center;justify-content:center}}
.viability .dial span{{font-weight:700;font-size:18px;color:{brand_hex}}}
.viability .dial.big span{{font-size:30px}}
.viability b{{display:block;font-size:13px;margin-top:2px}}
.viability small{{display:block;color:#667085;font-size:11px;line-height:1.35}}
</style>"""

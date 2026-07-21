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

MASTER: the three strengths set the ceiling; conflict pressure drags it
down. A floor applies (see MASTER_FLOOR) because there is always a route —
evidence, narrowing the specification, restyling a descriptive element. The
floor is deliberately NOT stated in client-facing copy: a published floor
reads as rigged, and the dials already show honestly where the work is.

The gauges are pure HTML/CSS (conic-gradient) — no charting dependency, so
the container stays slim and the same markup can go into the branded PDF.
"""
from __future__ import annotations

import re
from datetime import date

# Structure (Jonathan, 20 Jul): Uniqueness + Distinctiveness + Proof of Use
# are the POSITIVE group ("Brand Strengths"); Conflicts is the NEGATIVE — a
# drag applied to the strengths. Master = strengths minus the conflict drag,
# floored at 50.
STRENGTH_WEIGHTS = {'uniqueness': 0.35, 'distinctiveness': 0.40,
                    'proof_of_use': 0.25}
CONFLICT_DRAG = 0.40          # how hard conflict pressure pulls the master down
# Floor: the master never prints below this. Rationale unchanged — there is
# always a route (evidence, narrowing, restyling a descriptive element) — but
# the number is NOT disclosed in client-facing copy: publishing the floor
# invites "so it's rigged", and a visible ceiling on bad news reads as spin.
# Internal only.
MASTER_FLOOR = 41

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
    """95 when the register shows nothing like it, sliding down as the crowd
    grows. Uses the TOTAL flagged (not a display cap); softens after the
    first dozen — 20 vs 200 similar marks is a difference of degree."""
    return _clamp(95 - min(n_similar * 0.9, 75))


def conflicts(high: int, medium: int, low: int) -> int:
    """Conflict pressure, scored as headroom (100 = clear, 0 = blocked).

    Per-band CAPS are the honesty fix: severity must dominate volume. The old
    linear sum let 191 Low-risk marks zero the dial — telling someone whose
    risks are all LOW that conflicts are catastrophic, the opposite of what
    "low risk" means. Now Low can never cost more than 10 points in total,
    Medium 25, while genuine High risks properly hurt (20 each, up to 60)."""
    penalty = min(high * 20, 60) + min(medium * 2.5, 25) + min(low * 0.08, 10)
    return _clamp(100 - penalty)


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


def strengths_composite(scores: dict) -> int:
    return round(sum(scores[k] * w for k, w in STRENGTH_WEIGHTS.items()))


def master(scores: dict) -> int:
    """Strengths minus the conflict drag, floored.

    The three positives set the ceiling; conflict pressure (100 - the
    conflicts headroom score) pulls it down. 191 Lows ≈ 4-point drag; three
    genuine Highs ≈ 24-point drag."""
    positive = strengths_composite(scores)
    drag = (100 - scores['conflicts']) * CONFLICT_DRAG
    return max(MASTER_FLOOR, round(positive - drag))


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

STRENGTH_LABELS = {
    'uniqueness': ('Uniqueness', 'How alone your name is on the register'),
    'distinctiveness': ('Distinctiveness', 'How protectable the wording is'),
    'proof_of_use': ('Proof of Use', 'Time in genuine use'),
}
CONFLICT_LABEL = ('Conflicts', 'Headroom — how little the similar marks bite')


def _colour(v: int) -> str:
    if v >= 70:
        return '#2E7D32'
    if v >= 45:
        return '#E69500'
    return '#C0392B'


def _dial(v, label, sub):
    c = _colour(v)
    return f"""
  <div class="vg">
    <div class="dial" style="background:
      conic-gradient({c} {v * 3.6}deg, #ECEFF1 0deg)">
      <div class="hole"><span>{v}</span></div>
    </div>
    <b>{label}</b><small>{sub}</small>
  </div>"""


def gauge_html(result: dict, *, brand_hex: str = '#1D1D1B') -> str:
    """The dials, as Claude Design's `.dial` components.

    All styling now lives in braudit.css — the only thing passed in is `--v`,
    a 0-100 number the conic-gradient reads. That keeps screen and print
    identical, and means the dials survive print-to-PDF (no JS, no canvas).

    `brand_hex` is retained so older callers don't break; colour comes from
    the stylesheet.
    """
    def sub(value, label, is_strength=True):
        kind = "is-strength" if is_strength else "is-negative"
        return (f'<div class="subdial">'
                f'<div class="dial dial-sub {kind}" style="--v:{int(value)}">'
                f'<span class="val">{int(value)}</span></div>'
                f'<div class="nm">{label}</div></div>')

    strengths = ''.join(sub(result['scores'][k], lab, True)
                        for k, (lab, _s) in STRENGTH_LABELS.items())
    conflict = sub(result['scores']['conflicts'], CONFLICT_LABEL[0], False)
    m = int(result['master'])
    return f"""
<div class="row" style="gap:28px;align-items:center;flex-wrap:wrap">
  <div style="text-align:center">
    <div class="dial dial-master" style="--v:{m}">
      <span class="val">{m}%</span><span class="cap">viable</span></div>
  </div>
  <div class="dial-group strengths" style="flex:1;min-width:280px">
    <div class="g-head">&#9650; Brand strengths</div>
    <div class="dials">{strengths}</div>
    <div class="g-head" style="margin-top:10px;color:var(--risk)">&#9888; Working against you</div>
    <div class="dials negatives">{conflict}</div>
  </div>
</div>"""

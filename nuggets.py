"""'Did you know' cards for the report-building screen.

Copy by Jonathan (20 Jul), lightly tidied for grammar only — the claims,
figures and framing are his and must not be embellished. Two rules held here:

  * Nothing states or implies a guarantee. The 98% and the 4,000 are
    historical fact, phrased as history.
  * Every card is a real, checkable point about trademarks — this screen is
    the one moment we have someone's full attention, so it teaches rather
    than sells. The selling is the CTA at the end.

Rendered as a CSS-only carousel: the animation runs client-side, so the cards
keep cycling while Python is still building the report. No JS, so it also
survives Streamlit's rerun model and the print-to-PDF path.
"""
from __future__ import annotations

NUGGETS = [
    ("Your brand is an asset in its own right",
     "Trademarks are saleable assets. A brand can hold value entirely "
     "separately from the company that uses it — and as the registered "
     "owner, that asset is yours."),

    ("You don't have to own it through your company",
     "Some people register trademarks in their own personal name, or in "
     "trust, and licence it back to their company. It protects the brand if "
     "the company ever becomes insolvent, and it gives you far stronger "
     "individual negotiating power if the company is sold."),

    ("It's how the big platforms verify you",
     "Google, Amazon and eBay use trademark registrations to confirm you "
     "have the right to use a name, logo or tagline. Without one, proving "
     "it is a great deal harder."),

    ("It isn't only names",
     "A trademark can be a logo, a tagline, a sound — even a smell. If it "
     "identifies you to your customers, it may be protectable."),

    ("It can save you a fortune in legal fees",
     "Owning a trademark can save hundreds of thousands of pounds in "
     "enforcement action. It can be used to demand surrender of similar "
     "domain names, social media accounts and counterfeit listings — often "
     "without going near a court."),

    ("Protection stops at the border",
     "Trademarks are territorial. Applying abroad means working with local "
     "attorneys in each country — we have a long-established network of "
     "affordable ones who can handle your case."),

    ("The first five years are the strongest",
     "For the first five years you can enforce your rights without having "
     "to prove you've used the mark. It's why large organisations often "
     "re-apply for key trademarks every five years, rather than simply "
     "renewing at ten."),

    ("We've done this a few times",
     "We've registered over 4,000 trademarks since 2008. Last year our "
     "application success rate was 98%."),
]

# Seconds each card is held. Tuned so a set of 4 lasts ~20s — long enough to
# read, short enough that nobody watches the set loop. Jonathan (20 Jul):
# "I would not scroll through between build screen and reveal, maybe do 3 or
# 4 max dependent how long that takes."
DWELL = 5.0

# The build happens twice, so the cards are split — nobody sees a repeat.
SET_ONE = NUGGETS[:4]      # while we read the register and the sector
SET_TWO = NUGGETS[4:]      # while we tailor the report to their answers


def carousel_html(cards=None, *, brand_pink: str = '#E51652',
                  brand_navy: str = '#2D455A',
                  brand_slate: str = '#617383',
                  message: str = 'Building your report…') -> str:
    """CSS-only rotating cards. Total cycle = len(cards) * DWELL."""
    NUGGETS_ = cards if cards is not None else NUGGETS
    n = len(NUGGETS_)
    total = n * DWELL
    # each card: fade in, hold, fade out, then stay hidden for the rest
    frames = []
    for i, (title, body) in enumerate(NUGGETS_):
        start = (i / n) * 100
        fade = 1.2 / total * 100          # ~1.2s fade
        hold_end = start + (100 / n) - fade
        frames.append(f"""
@keyframes nug{i} {{
  0%, {max(start - 0.01, 0):.3f}% {{ opacity:0; transform:translateY(8px); }}
  {min(start + fade, 100):.3f}%   {{ opacity:1; transform:translateY(0); }}
  {max(hold_end, 0):.3f}%          {{ opacity:1; transform:translateY(0); }}
  {min(hold_end + fade, 100):.3f}%, 100% {{ opacity:0; transform:translateY(-8px); }}
}}""")
    out = []
    for i, (title, body) in enumerate(NUGGETS_):
        out.append(f"""
  <div class="nug" style="animation:nug{i} {total}s ease-in-out infinite">
    <div class="eyebrow">Did you know…</div>
    <h3>{title}</h3>
    <p>{body}</p>
  </div>""")
    return f"""
<div class="nugwrap">
  <div class="loader"><span></span><span></span><span></span></div>
  <div class="loadmsg">{message}</div>
  <div class="nugstage">{''.join(out)}</div>
</div>
<style>
.nugwrap {{ text-align:center; padding:26px 10px 34px; font-family:inherit; }}
.loader {{ display:flex; gap:7px; justify-content:center; margin-bottom:14px; }}
.loader span {{ width:9px; height:9px; border-radius:50%;
  background:{brand_pink}; animation:bounce 1.1s ease-in-out infinite; }}
.loader span:nth-child(2) {{ animation-delay:.16s; opacity:.75; }}
.loader span:nth-child(3) {{ animation-delay:.32s; opacity:.5; }}
@keyframes bounce {{ 0%,80%,100% {{ transform:translateY(0); }}
                     40% {{ transform:translateY(-9px); }} }}
.loadmsg {{ color:{brand_slate}; font-size:13px; letter-spacing:.02em;
  margin-bottom:22px; }}
.nugstage {{ position:relative; min-height:190px; max-width:620px;
  margin:0 auto; }}
.nug {{ position:absolute; inset:0; opacity:0; }}
.nug .eyebrow {{ color:{brand_pink}; font-size:11px; font-weight:700;
  letter-spacing:.09em; text-transform:uppercase; margin-bottom:8px; }}
.nug h3 {{ color:{brand_navy}; font-size:21px; line-height:1.25;
  margin:0 0 10px; font-weight:700; }}
.nug p {{ color:#3F4A55; font-size:15px; line-height:1.55; margin:0; }}
{''.join(frames)}
</style>"""

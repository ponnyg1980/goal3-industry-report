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

The markup is Claude Design's `.build / .nuggets / .nugget` (see braudit.css);
the timing lives in the stylesheet as fixed nth-child delays, which is why a
set is exactly FOUR cards. The progress bar is honest: it animates over the
same 20s the carousel runs for, so it reflects elapsed time rather than
pretending to know a percentage of work done.
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


import html as _html


def _esc(x):
    return _html.escape(str(x))


def carousel_html(cards=None, *, message: str = 'Building your report…',
                  **_legacy) -> str:
    """The loading screen: one set of four 'Did you know' cards.

    `**_legacy` swallows the old brand_* colour kwargs — those live in
    braudit.css now, but an older caller must not raise on a loading screen.
    """
    cards = list(cards if cards is not None else NUGGETS)[:4]
    n = len(cards) or 1
    body = "".join(
        f'<div class="nugget">'
        f'<div class="tag">Did you know &middot; {i + 1}/{n}</div>'
        f'<div class="t">{_esc(title)}</div>'
        f'<div class="b">{_esc(text)}</div></div>'
        for i, (title, text) in enumerate(cards))
    dots = "".join("<i></i>" for _ in cards)
    return (f'<div class="bd"><div class="build">'
            f'<div class="msg">{_esc(message)}</div>'
            f'<div class="build-progress"><i></i></div>'
            f'<div class="nuggets">{body}</div>'
            f'<div class="nug-dots">{dots}</div>'
            f'</div></div>')

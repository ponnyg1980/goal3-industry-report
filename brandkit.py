"""Shared TMH design components — the markup half of `braudit.css`.

Claude Design shipped a stylesheet plus reference HTML; this module is where
that markup lives as functions, so the same components render identically in
the Streamlit app and in the printed report, and so a class name only ever has
to change in one place.

Nothing here queries anything. It formats.
"""
from __future__ import annotations

import base64
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BRAND = os.path.join(HERE, "brand")
CSS = os.path.join(HERE, "braudit.css")

# Live CTA URLs (mirrored from assessment.LINKS so the print report can use
# them without importing the assessment machinery).
URL_AUDIT = "https://www.thetrademarkhelpline.com/request-brand-audit/"
URL_CALL = "https://link.cerebrumai.io/widget/booking/ZArxD6BnggpV7bsSF0ks"
URL_ENQUIRY = "https://www.thetrademarkhelpline.com/make-an-enquiry/"


def esc(x) -> str:
    return html.escape(str(x if x is not None else "—"))


def css() -> str:
    try:
        with open(CSS, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def asset_uri(filename: str) -> str:
    """Embed a brand asset as a data URI — the printed report has to be
    self-contained, and Streamlit can't serve arbitrary local files."""
    path = os.path.join(BRAND, filename)
    mime = "image/svg+xml" if filename.endswith(".svg") else "image/png"
    try:
        with open(path, "rb") as f:
            return f"data:{mime};base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def img(filename: str, *, width: int, style: str = "") -> str:
    uri = asset_uri(filename)
    if not uri:
        return ""
    return (f'<img src="{uri}" alt="" style="width:{width}px;flex:none;'
            f'filter:drop-shadow(0 5px 9px rgba(45,69,90,.2));{style}">')


# ── the video well ───────────────────────────────────────────────────
# One box, two states. A VSL is coming; until it exists the same well holds
# the quote card, which is also what prints. Building the space now means the
# page doesn't have to be redesigned around the video later.
QUOTE_TEXT = ("&ldquo;By failing to prepare, you are preparing to fail.&rdquo;")
QUOTE_FACT = ("Our success rate on UK registrations over the past 12 months "
              "is 98%.")
QUOTE_WHO = "Jonathan Paton &mdash; Founder &amp; MD"


def video_well(embed_url: str | None = None) -> str:
    """16:9 well. Pass a YouTube embed URL to switch it to the video state."""
    if embed_url:
        inner = (f'<iframe src="{esc(embed_url)}" title="" frameborder="0" '
                 f'allow="accelerometer; autoplay; clipboard-write; '
                 f'encrypted-media; gyroscope; picture-in-picture" '
                 f'allowfullscreen style="width:100%;height:100%;border:0;'
                 f'border-radius:inherit"></iframe>')
        note = ""
    else:
        inner = (f'<span class="ratio">16:9 &middot; QUOTE</span>'
                 f'<div class="play"></div>'
                 f'<div class="quote">{QUOTE_TEXT} '
                 f'<span class="fact">{QUOTE_FACT}</span></div>'
                 f'<div class="who">{QUOTE_WHO}</div>')
        # The line underneath is deliberate: the paragraph inside the card is
        # an argument about using verifiable data, so an unverifiable
        # attribution would undercut the very claim it introduces.
        note = ('<div class="muted" style="text-align:center;margin-top:5px;'
                'font-size:9px">Quote attributed to Benjamin Franklin.</div>')
    return f'<div class="well is-video"><div class="inner">{inner}</div></div>{note}'


def hero(*, eyebrow: str, title: str, lede: str, well: bool = True) -> str:
    """Page-1 hero: copy left, video well top-right above the fold."""
    right = (f'<div style="flex:1;min-width:240px">{video_well()}</div>'
             if well else "")
    return (f'<div class="row hero" style="align-items:stretch;gap:20px">'
            f'<div style="flex:1.35;display:flex;flex-direction:column;'
            f'justify-content:center;gap:8px">'
            f'<div class="eyebrow">{eyebrow}</div>'
            f'<h1 class="h1">{title}</h1>'
            f'<p class="lede">{lede}</p></div>{right}</div>')


def sec_head(num, title: str, *, pagebreak: bool = False) -> str:
    cls = "sec-head pagebreak" if pagebreak else "sec-head"
    return (f'<div class="{cls}"><span class="num">{esc(num)}</span>'
            f'<h2 class="h2">{esc(title)}</h2></div>')


# ── chips: never colour alone (glyph + word + colour) ────────────────
BAND_GLYPH = {"a": "&#11035;", "b": "&#128998;", "c": "&#128992;", "d": "&#128997;"}
RISK_META = {"High Risk": ("risk-hi", "&#9650;", "High"),
             "Medium Risk": ("risk-md", "&#9679;", "Medium"),
             "Low Risk": ("risk-lo", "&#9632;", "Low")}


def band_chip(tier: str, label: str) -> str:
    t = (tier or "d").lower()
    return (f'<span class="chip band-{t}"><i>{BAND_GLYPH.get(t, "")}</i> '
            f'{esc(label)}</span>')


def risk_chip(band: str, suffix: str = "") -> str:
    cls, glyph, word = RISK_META.get(band, ("risk-lo", "&#9632;", esc(band)))
    return (f'<span class="risk {cls}"><i>{glyph}</i> {word}'
            f'{(" " + str(suffix)) if suffix != "" else ""}</span>')


def cta_block(*, primary=("Request your Brand Audit &rarr;", URL_AUDIT),
              secondary=("Book a free 15-minute call", URL_CALL)) -> str:
    parts = [f'<a class="btn btn-primary" href="{primary[1]}">{primary[0]}</a>']
    if secondary:
        parts.append(f'<a class="btn btn-secondary" href="{secondary[1]}">'
                     f'{secondary[0]}</a>')
    return f'<div class="cta-block">{"".join(parts)}</div>'


def offer_block() -> str:
    """£149 + £149 = £298 of work for £99. The sum is checkable on purpose —
    a roundable £299 reads like marketing, £298 reads like arithmetic."""
    return f"""
<div class="offer" style="margin-top:20px">
  <div class="row" style="flex-wrap:wrap;gap:18px;align-items:center;justify-content:space-between">
    <div style="flex:1;min-width:300px">
      <div class="eyebrow">The next step</div>
      <div style="font-size:15px;font-weight:800;color:var(--brand-navy);margin-top:3px">
        A full Brand Audit + Review &amp; Consultation</div>
      <div style="display:flex;align-items:flex-end;gap:20px;margin-top:8px">
        <div><div class="muted" style="font-size:9.5px;font-weight:800;letter-spacing:.5px;text-transform:uppercase">Normally</div>
             <div class="was">&pound;298</div></div>
        <div><div class="muted" style="font-size:9.5px;font-weight:800;letter-spacing:.5px;text-transform:uppercase">Today</div>
             <div class="price">&pound;99</div></div>
      </div>
      <p class="p" style="margin-top:8px">Brand Audit &pound;149 + Review &amp; Consultation
        &pound;149. The &pound;99 comes off your application fees if you go ahead &mdash;
        and if we advise you <em>not</em> to file, you get another audit and
        consultation on a different brand, any time within three months.</p>
      <div class="cant-lose">Either way, you can&rsquo;t lose the &pound;99.</div>
      {cta_block()}
    </div>
    {img("owl-branch.png", width=150)}
  </div>
</div>"""


def urgency_block() -> str:
    return f"""
<div class="urgency" style="margin-top:16px">
  {img("bird-worm.png", width=104, style="filter:drop-shadow(0 5px 10px rgba(0,0,0,.3));")}
  <div>
    <div class="eyebrow">Don&rsquo;t leave it to chance</div>
    <div class="headline">The UKIPO works on a <em>first-to-file</em> basis.</div>
    <p class="p">The brand you&rsquo;ve built is only truly yours once it&rsquo;s filed.
      If someone else files it first, they get the rights &mdash; not you.</p>
  </div>
</div>"""

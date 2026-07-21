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


def class_rows(selection) -> str:
    """The chosen classes as `.class-row` cards.

    Deliberately a READ-ONLY view. The picking itself stays in
    `st.data_editor` — tick boxes are the one place in the report where the
    visitor does real work, and a static HTML table can't be ticked. So the
    design language arrives where it costs nothing: on the confirmed
    selection, in Reveal 2 and in the printed report.
    """
    if not selection:
        return ""
    _TIER_OF = {}
    rows = []
    for sset in selection:
        tier = (sset.get("tier")
                or _TIER_OF.get(sset.get("band"), "d"))
        terms = (sset.get("terms") or [])
        term_html = " ".join(
            f'<span class="chip" style="background:var(--hairline-2);'
            f'color:var(--brand-navy)">{esc(t.get("term"))}</span>'
            for t in terms[:8])
        more = (f'<span class="muted" style="font-size:11px">'
                f'+{len(terms) - 8} more</span>' if len(terms) > 8 else "")
        pct = sset.get("pct")
        rows.append(
            f'<div class="class-row keep">'
            f'<div class="body">'
            f'<div class="title">Class {esc(sset.get("class"))} &mdash; '
            f'{esc(sset.get("heading"))}</div>'
            f'<div class="sub">{band_chip(tier, sset.get("band") or "")} '
            f'{term_html} {more}</div></div>'
            f'<div class="pct">{esc(pct)}%</div></div>')
    return "".join(rows)


# ══════════════════════════════════════════════════════════════════════
# FULL INSTALL — the design applied to Streamlit itself, not just to our
# own blocks.
#
# Injecting braudit.css alone is a half-install: every rule is scoped to
# `.bd`, so our markup gets the brand while Streamlit's page background,
# fonts, headers, metrics and tables stay default. A page that is designed
# in patches reads worse than one that is plainly undesigned, because the
# eye keeps finding the seam.
#
# So this does three things the scoped stylesheet can't:
#   1. Loads Public Sans. The CSS names it in --font-display but never
#      fetches it, so the display type was silently falling back to system
#      sans — which is most of why it looked wrong.
#   2. Applies the page surface, content width and typography to Streamlit's
#      own containers.
#   3. Restyles the native widgets globally (buttons, inputs, selects,
#      radios, tables), so the bits we MUST keep as widgets — because they
#      are interactive — stop looking like a different product.
# ══════════════════════════════════════════════════════════════════════

FONT_URL = ("https://fonts.googleapis.com/css2?"
            "family=Public+Sans:wght@400;600;700;800&display=swap")

_GLOBAL_CSS = """
/* ---- page surface ------------------------------------------------ */
.stApp { background: var(--page-bg); }
[data-testid="stAppViewContainer"] > .main .block-container {
  max-width: 1080px; padding-top: 1.6rem; padding-bottom: 3rem;
}
/* Streamlit's own chrome adds nothing here and breaks the illusion. */
[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }

/* ---- typography -------------------------------------------------- */
/* NB: do NOT use a universal selector here. Streamlit draws its icons with
   a ligature icon font (Material Symbols), so `[data-testid=...] *` — which
   has the same specificity as the icon's own class but comes later in the
   sheet — wins, and every icon renders as its literal ligature TEXT
   ("keyboard_arrow_down", "close"). The page turns into words. Set the face
   on the root and let inheritance do the rest; icon classes then keep
   their own font-family. */
html, body, .stApp { font-family: var(--font-body); }

.stApp h1, .stApp h2, .stApp h3,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
  font-family: var(--font-display); font-weight: 800;
  color: var(--brand-navy); letter-spacing: -.4px;
}
.stApp p, [data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
  color: var(--brand-body); font-size: 15px; line-height: 1.6;
}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
  color: var(--brand-slate) !important; font-size: 12.5px !important;
}

/* ---- buttons ----------------------------------------------------- */
.stButton > button, .stLinkButton > a, .stDownloadButton > button {
  font-family: var(--font-display); font-weight: 800; font-size: 14px;
  border-radius: var(--r-md); padding: 11px 20px; border: 1px solid var(--hairline);
  background: #fff; color: var(--brand-navy); transition: all .15s ease;
}
.stButton > button:hover, .stLinkButton > a:hover,
.stDownloadButton > button:hover {
  border-color: var(--brand-navy); color: var(--brand-navy); background: #fff;
}
.stButton > button[kind="primary"], .stLinkButton > a[kind="primary"] {
  background: var(--brand-pink); border-color: var(--brand-pink); color: #fff;
}
.stButton > button[kind="primary"]:hover,
.stLinkButton > a[kind="primary"]:hover {
  background: var(--brand-pink-hover); border-color: var(--brand-pink-hover);
  color: #fff;
}
.stButton > button:focus:not(:active) { color: var(--brand-navy); }

/* ---- inputs ------------------------------------------------------ */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-baseweb="select"] > div {
  border-radius: var(--r-md) !important; border-color: var(--hairline) !important;
  font-size: 15px !important; background: #fff !important;
}
[data-testid="stTextInput"] input:focus,
[data-baseweb="select"] > div:focus-within {
  border-color: var(--brand-navy) !important; box-shadow: none !important;
}
[data-testid="stWidgetLabel"] label, [data-testid="stWidgetLabel"] p {
  font-family: var(--font-display) !important; font-weight: 700 !important;
  font-size: 12px !important; letter-spacing: .3px; text-transform: uppercase;
  color: var(--brand-slate) !important;
}

/* ---- radio / checkbox / multiselect ------------------------------- */
[data-testid="stRadio"] label p, [data-testid="stCheckbox"] label p {
  font-size: 14.5px !important; color: var(--brand-body) !important;
  text-transform: none !important; letter-spacing: 0 !important;
  font-weight: 400 !important; font-family: var(--font-body) !important;
}
[data-baseweb="tag"] { background: var(--brand-navy) !important;
  border-radius: var(--r-sm) !important; }

/* ---- tables + editors -------------------------------------------- */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
  border: 1px solid var(--hairline); border-radius: var(--r-md);
  overflow: hidden; background: #fff;
}

/* ---- expander / alerts ------------------------------------------- */
[data-testid="stExpander"] { border: 1px solid var(--hairline);
  border-radius: var(--r-md); background: #fff; }
[data-testid="stExpander"] summary { font-family: var(--font-display);
  font-weight: 700; color: var(--brand-navy); }
[data-testid="stAlert"] { border-radius: var(--r-md); border: 1px solid var(--hairline); }

/* ---- our own blocks sit on the page, not in a card ---------------- */
.bd { background: transparent; }
.bd .card, .bd .tbl, .bd .metric, .bd .class-row { background: var(--card-bg); }
hr { border-color: var(--hairline) !important; }
"""


def install(st) -> None:
    """Inject the font, the stylesheet and the Streamlit layer. Call once,
    immediately after set_page_config."""
    st.markdown(
        f'<link rel="preconnect" href="https://fonts.googleapis.com">'
        f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link href="{FONT_URL}" rel="stylesheet">'
        f"<style>{css()}\n{_GLOBAL_CSS}</style>",
        unsafe_allow_html=True)


# ── display components (replacing st.metric / st.dataframe / st.header) ──
def metrics(items) -> str:
    """[(label, value), …] as `.metrics`. Streamlit's st.metric can't be
    styled into this shape, so we render our own."""
    cells = "".join(
        f'<div class="metric"><div class="k">{esc(k)}</div>'
        f'<div class="v">{esc(v)}</div></div>' for k, v in items)
    n = max(len(list(items)), 1)
    return (f'<div class="metrics" style="grid-template-columns:'
            f'repeat({min(n, 4)},1fr)">{cells}</div>')


def table(headers, rows, *, num_cols=()) -> str:
    """`.tbl` — the designed table. `num_cols` are indexes to right-align."""
    head = "".join(
        f'<th class="num">{esc(h)}</th>' if i in num_cols else f'<th>{esc(h)}</th>'
        for i, h in enumerate(headers))
    body = []
    for r in rows:
        tds = "".join(
            f'<td class="num">{c}</td>' if i in num_cols else f'<td>{c}</td>'
            for i, c in enumerate(r))
        body.append(f"<tr>{tds}</tr>")
    if not body:
        body = [f'<tr><td colspan="{len(headers)}" class="muted">'
                f'Nothing to show.</td></tr>']
    return (f'<div class="tbl"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def callout(text: str, *, kind: str = "info") -> str:
    return f'<div class="callout"><p class="p">{text}</p></div>'


def trust(eyebrow: str, body: str) -> str:
    return (f'<div class="trust"><div class="eyebrow">{esc(eyebrow)}</div>'
            f'<p class="p">{body}</p></div>')


def dist_bars(items) -> str:
    """[(label, value), …] as the `.dist` horizontal bars."""
    items = list(items)
    top = max((v for _, v in items), default=1) or 1
    rows = "".join(
        f'<div class="d"><span class="cl">{esc(k)}</span>'
        f'<span class="track"><span class="fill" '
        f'style="width:{max(3, round(v / top * 100))}%"></span></span>'
        f'<span class="pct">{esc(f"{v:,}")}</span></div>' for k, v in items)
    return f'<div class="dist">{rows}</div>'

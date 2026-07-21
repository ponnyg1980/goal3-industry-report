"""
TMH-branded HTML report for Goal #3. Print-to-PDF ready (A4), self-contained
(logo embedded as base64). Brand colours match brand_tokens.py.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))
# bundled logo (deployed) with local brand/ folder as fallback
LOGO = os.path.join(HERE, "assets", "tmh_logo.png")
if not os.path.exists(LOGO):
    LOGO = os.path.normpath(os.path.join(HERE, "..", "brand", "tmh_logo.png"))

PINK = "#E51652"
NAVY = "#2D455A"
SLATE = "#617383"
BODY = "#1D1D1B"


def _logo_data_uri() -> str:
    try:
        with open(LOGO, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def _esc(x) -> str:
    return html.escape(str(x if x is not None else "—"))


def _sic_names(sics) -> str:
    """'Solicitors (SIC 69102)' rather than a bare number — nobody knows
    their own SIC code, let alone what it stands for."""
    import brandkit as bk
    return ", ".join(bk.sic_label(c) for c in (sics or [])) or "—"


def _risk_block(risk) -> str:
    """High/Medium/Low, as the designed components.

    Previously this hand-rolled `.cards/.card/.big/.lbl` and a bare <table>
    — none of which exist in braudit.css, so the printed report fell back to
    unstyled browser defaults while the screen looked designed. Everything
    now goes through brandkit, so there is exactly one implementation.
    """
    if not risk or not risk.get("marks"):
        return ""
    import brandkit as bk
    counts = risk.get("counts", {})
    return (
        bk.sec_head(2, "Marks like yours on the register", pagebreak=True)
        + '<p class="muted">Banded by status, similarity to the brand name, '
          'mark type and class overlap with the industry &mdash; the same '
          'rules as our Audit Report.</p>'
        + '<div class="row" style="gap:8px;margin:8px 0 10px">'
        + bk.risk_chip("High Risk", counts.get("High Risk", 0))
        + bk.risk_chip("Medium Risk", counts.get("Medium Risk", 0))
        + bk.risk_chip("Low Risk", counts.get("Low Risk", 0))
        + '</div>'
        + bk.table(["Risk", "Mark", "Owner", "Status", "Classes"],
                   [[bk.risk_chip(x["risk"]), bk.esc(x.get("verbal_element_text")),
                     bk.esc(x.get("applicant_name")), bk.esc(x.get("status")),
                     bk.esc(", ".join(str(c) for c in (x.get("classes") or [])))]
                    for x in risk["marks"]]))


def _top_applicants_block(top_applicant_marks) -> str:
    """The sector's top trademark applicants and the marks they own."""
    if not top_applicant_marks:
        return ""
    import brandkit as bk
    parts = []
    for company, mk in top_applicant_marks.items():
        parts.append(f'<h3 class="h3" style="margin-top:14px">{_esc(company)}</h3>'
                     + bk.table(["Mark", "Status"],
                                [[bk.esc(m.get("mark")), bk.esc(m.get("status"))]
                                 for m in (mk or [])]))
    return (bk.sec_head(4, "What the sector leaders protect")
            + '<p class="muted">The top trademark applicants in this sector '
              'and the marks they own (up to 10 each).</p>' + "".join(parts))


def _benchmark_block(benchmark) -> str:
    if not benchmark:
        return ""
    import brandkit as bk
    m = benchmark.get("metrics", {})
    means = benchmark.get("means", {})
    pen = m.get("penetration_pct", {})
    tpa = m.get("trademarks_per_applicant", {})
    yr = m.get("years_to_first_filing", {})
    frac = means.get("frac_trademark_post_incorporation")
    note = ""
    if frac:
        note = (f'<p class="muted">{round(frac * 100)}% of companies file '
                f'their first trademark after incorporating; the typical '
                f'company files '
                f'{_esc(means.get("mean_years_to_first_filing"))} years into '
                f'its journey.</p>')
    return (bk.sec_head(5, "How they compare")
            + '<p class="muted">All-industry mean vs their industry (union of '
              'SIC codes) vs this company.</p>' + note
            + bk.table(
                ["Metric", "All-industry mean", "Their industry", "This company"],
                [["Trademark penetration (%)", _esc(pen.get("mean")),
                  _esc(pen.get("industry")), "&mdash;"],
                 ["Trademarks (per applicant)", _esc(tpa.get("mean")),
                  _esc(tpa.get("industry")), _esc(tpa.get("company"))],
                 ["Years to first filing", _esc(yr.get("mean")),
                  _esc(yr.get("industry")), _esc(yr.get("company"))]],
                num_cols=(1, 2, 3)))


# Band label -> colour, derived from the shared vocabulary so the report can't
# drift from the engine. Old labels kept as aliases for any cached selections.
import sys as _sys
from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
if str(_HERE) not in _sys.path:
    _sys.path.insert(0, str(_HERE))
try:
    from freesearch.bands import TIER_LABELS as _TL
    _TIER_COLOUR = {"a": "#1D1D1B", "b": "#2E7D32", "c": "#E69500", "d": "#C0392B"}
    _BAND_COLOUR = {_TL[k]: _TIER_COLOUR[k] for k in _TL}
except Exception:
    _BAND_COLOUR = {}
_BAND_COLOUR.update({"Always": "#1D1D1B", "Often": "#2E7D32",   # legacy aliases
                     "Sometimes": "#E69500", "Rarely": "#C0392B"})


def render_recommendations(company_name, sics, selection) -> str:
    """Branded, colour-coded class & term recommendation sheet (Goal #1).
    selection = [{class, heading, band, pct, terms:[{term, band}]}]."""
    logo = _logo_data_uri()
    today = dt.date.today().strftime("%d %B %Y")
    blocks = []
    for s in selection or []:
        ccol = _BAND_COLOUR.get(s.get("band"), "#1D1D1B")
        terms = s.get("terms") or []
        term_html = " ".join(
            f"<span class='term' style='color:{_BAND_COLOUR.get(t.get('band'),'#1D1D1B')}'>"
            f"{_esc(t.get('term'))}</span>"
            for t in terms) or "<span class='muted'>— class kept; terms not itemised —</span>"
        blocks.append(f"""
          <div class="clsrow">
            <div class="clshdr" style="color:{ccol}">
              <span class="band" style="background:{ccol}">{_esc(s.get('band'))}</span>
              Class {_esc(s.get('class'))} — {_esc(s.get('heading'))}
              <span class="muted">({_esc(s.get('pct'))}% of industry)</span>
            </div>
            <div class="terms">{term_html}</div>
          </div>""")
    body = "".join(blocks) or "<p class='muted'>No classes selected.</p>"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Class &amp; Term Recommendations — {_esc(company_name)}</title>
<style>
  @page {{ size: A4; margin: 16mm; }}
  body {{ font-family:'Helvetica Neue',Arial,sans-serif; color:{BODY}; font-size:12px; }}
  .hdr {{ display:flex; justify-content:space-between; align-items:center;
          border-bottom:3px solid {PINK}; padding-bottom:10px; margin-bottom:16px; }}
  .hdr img {{ height:44px; }} .hdr .meta {{ text-align:right; color:{SLATE}; font-size:11px; }}
  h1 {{ color:{NAVY}; font-size:20px; margin:4px 0; }}
  .legend {{ color:{SLATE}; font-size:11px; margin-bottom:14px; }}
  .legend b {{ padding:1px 6px; border-radius:3px; color:#fff; margin-right:2px; }}
  .clsrow {{ border:1px solid #eee; border-radius:8px; padding:10px 12px; margin-bottom:10px; }}
  .clshdr {{ font-size:14px; font-weight:700; margin-bottom:6px; }}
  .band {{ color:#fff; font-size:10px; padding:1px 7px; border-radius:10px; margin-right:8px;
           vertical-align:middle; }}
  .terms {{ line-height:1.9; }}
  .term {{ display:inline-block; margin:0 10px 2px 0; font-size:12px; }}
  .muted {{ color:{SLATE}; font-weight:400; font-size:11px; }}
  .foot {{ margin-top:24px; color:{SLATE}; font-size:10px; border-top:1px solid #eee; padding-top:8px; }}
</style></head><body>
  <div class="hdr">
    <div>{'<img src="'+logo+'"/>' if logo else '<strong>The Trademark Helpline</strong>'}</div>
    <div class="meta">Class &amp; Term Recommendations<br>Generated {today}</div>
  </div>
  <h1>{_esc(company_name)}</h1>
  <p class="legend">Industry: {_sic_names(sics)}. How many businesses like this protect each:
     <b style="background:#1D1D1B">All use this</b><b style="background:#2E7D32">Most use this</b>
     <b style="background:#E69500">Some use this</b><b style="background:#C0392B">A few have this</b></p>
  {body}
  <div class="foot">A starting point based on what this industry typically protects — not legal
     advice. Final class/term selection should be confirmed for the specific goods and services.<br>
     The Trademark Helpline · Source: UK IPO registry (TemmyDB) + Companies House.</div>

  <div class="next-steps">
    <b>Next steps</b>
    <a href="https://www.thetrademarkhelpline.com/make-an-enquiry/">Make an Enquiry</a> ·
    <a href="https://link.cerebrumai.io/widget/booking/ZArxD6BnggpV7bsSF0ks">Talk to Us — book a call</a> ·
    <a href="https://www.thetrademarkhelpline.com/request-brand-audit/">Request Brand Audit</a>
  </div>
</body></html>"""


def _viability_block(viability) -> str:
    """The Trademark Viability dials, as static CSS (no JS at print time)."""
    if not viability:
        return ""
    try:
        import viability as vb
        import brandkit as bk
        return (bk.sec_head(1, "Trademark Viability")
                + "<p class='muted'>Your brand strengths, less the pressure "
                  "from conflicting marks on the register.</p>"
                + vb.gauge_html(viability))
    except Exception:
        return ""


def _selection_block(selection) -> str:
    """The classes and terms THEY chose — the tailored heart of the report."""
    import brandkit as bk
    if not selection:
        return (bk.sec_head(3, "Your classes & terms")
                + "<p class='muted'>You chose to "
                "cover classes at the audit rather than now — we'll go through "
                "them with you then.</p>")
    import brandkit as bk
    return (bk.sec_head(3, "Your classes & terms")
            + "<p class='muted'>The classes and goods/services you selected. "
              "Your registration only protects what you list here.</p>"
            + bk.class_rows(selection))


def _assessment_block(assessment) -> str:
    """What their three answers mean — the copy they were shown on screen."""
    if not assessment:
        return ""
    import re as _re
    body = assessment.get("body_md", "")
    body = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body)
    parts = []
    for para in body.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para.startswith("- "):
            items = "".join(f"<li>{ln[2:].strip()}</li>"
                            for ln in para.split("\n") if ln.strip().startswith("- "))
            parts.append(f"<ul>{items}</ul>")
        else:
            parts.append(f"<p>{para}</p>")
    import brandkit as bk
    return (bk.sec_head(6, assessment.get("title", "")) + "".join(parts))


def render(*, company_name, applicant, marks, sector_company=None, sector=None,
           benchmark=None, risk=None, top_applicant_marks=None,
           viability=None, selection=None, assessment=None) -> str:
    logo = _logo_data_uri()
    today = dt.date.today().strftime("%d %B %Y")

    marks_rows = "".join(
        f"<tr><td>{_esc(m.get('application_number'))}</td>"
        f"<td>{_esc((m.get('mark') or {}).get('verbal_element_text'))}</td>"
        f"<td>{_esc(m.get('status'))}</td>"
        f"<td>{_esc(m.get('expiry_date'))}</td></tr>"
        for m in (marks or [])[:50]) or \
        "<tr><td colspan=4 class='muted'>No marks on record.</td></tr>"

    import brandkit as bk_
    sector_block = ""
    if sector and sector.get("available"):
        size = sector.get("size", {})
        sic = sector.get("sic")
        comp_name = (sector_company or {}).get("name", "")
        top_rows = "".join(
            f"<tr><td>{_esc(t.get('name'))}</td><td>{_esc(t.get('company_number'))}</td>"
            f"<td class='num'>{t.get('trademarks', 0):,}</td></tr>"
            for t in sector.get("top_companies", []))
        class_rows = "".join(
            f"<tr><td>Class {_esc(c.get('nice_class'))}</td>"
            f"<td class='num'>{c.get('trademarks', 0):,}</td></tr>"
            for c in sector.get("class_distribution", [])[:10])
        sector_block = f"""
        {bk_.sec_head(8, "Sector intelligence")}
        <p class="lede">{bk_.sic_label(sic)}</p>
        <p class="muted">Sector taken from {_esc(comp_name)}'s Companies House
           SIC code. {_esc(bk_.sic_section(sic) or "")}</p>
        <div class="cards">
          <div class="card"><div class="big">{size.get('trademarks', 0):,}</div>
            <div class="lbl">Trademarks in sector</div></div>
          <div class="card"><div class="big">{size.get('companies', 0):,}</div>
            <div class="lbl">Companies in sector</div></div>
          <div class="card"><div class="big">{_esc(sector.get('first_filed_year'))}</div>
            <div class="lbl">Sector first filed</div></div>
        </div>
        <h3>Top companies in the sector</h3>
        <table><thead><tr><th>Company</th><th>Number</th><th class="num">Trademarks</th></tr></thead>
          <tbody>{top_rows}</tbody></table>
        <h3>Class distribution</h3>
        <table><thead><tr><th>Nice class</th><th class="num">Trademarks</th></tr></thead>
          <tbody>{class_rows}</tbody></table>
        """

    import brandkit as bk

    # The document now rides on braudit.css (the same stylesheet the app
    # injects), so the PDF and the screen cannot drift apart. Only @page and
    # a couple of print-only rules are added here.
    ident = []
    if (sector_company or {}).get("number"):
        ident.append(f"company no. {_esc(sector_company['number'])}")
    ident.append(today)

    # Built outside the f-string: an f-string expression can't contain a
    # backslash before Python 3.12, and the lede needs escaped quotes.
    _prepared_for = (sector_company or {}).get('name') or company_name
    _lede = ('Prepared for <strong style="color:var(--brand-navy)">'
             + _esc(_prepared_for) + '</strong> &middot; '
             + ' &middot; '.join(ident))
    _hero = bk.hero(eyebrow="Trademark viability report",
                    title='How protectable is &ldquo;'
                          + _esc(company_name) + '&rdquo;?',
                    lede=_lede)

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Industry Trademark Report — {_esc(company_name)}</title>
<style>
{bk.css()}
  @page {{ size: A4; margin: 16mm; }}
  body {{ margin:0; }}
  /* Print can drop background colours, so anything that carries meaning by
     fill gets a border too. */
  .bd .urgency, .bd .offer, .bd .callout {{ border:1px solid var(--hairline); }}
  .bd .pagebreak {{ page-break-before: always; }}
  .bd table, .bd .clsrow, .bd .dial-group {{ page-break-inside: avoid; }}
</style></head><body><div class="bd">
  <div class="between" style="border-bottom:2px solid var(--brand-pink);
       padding-bottom:10px;margin-bottom:16px">
    <div>{'<img src="'+logo+'" style="height:40px">' if logo else '<strong>The Trademark Helpline</strong>'}</div>
    <div class="muted" style="text-align:right;font-size:10px">
      Industry Trademark Report<br>Generated {today}</div>
  </div>

  {_hero}

  {_viability_block(viability)}
  {_risk_block(risk)}
  {_selection_block(selection)}
  {_assessment_block(assessment)}

  {sector_block}
  {_top_applicants_block(top_applicant_marks)}
  {_benchmark_block(benchmark)}

  {bk.sec_head(7, "Trademarks held")}
  <div class="tbl"><table>
    <thead><tr><th>Application</th><th>Mark</th><th>Status</th><th>Expiry</th></tr></thead>
    <tbody>{marks_rows}</tbody></table></div>

  {bk.offer_block()}
  {bk.urgency_block()}

  <div class="muted" style="border-top:1px solid var(--hairline);margin-top:22px;
       padding-top:10px;font-size:9.5px">
    Counts include all trademarks ever filed (live and lapsed), for this legal
    entity only — group subsidiaries with separate company numbers are not
    aggregated.<br>
    The Trademark Helpline &middot; Source: UK IPO registry (TemmyDB). This
    report is informational and not legal advice.
  </div>
</div></body></html>"""

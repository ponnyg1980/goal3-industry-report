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


def _benchmark_block(benchmark) -> str:
    if not benchmark:
        return ""
    m = benchmark.get("metrics", {})
    means = benchmark.get("means", {})
    pen = m.get("penetration_pct", {})
    tpa = m.get("trademarks_per_applicant", {})
    yr = m.get("years_to_first_filing", {})
    frac = means.get("frac_trademark_post_incorporation")
    rows = [
        ("Trademark penetration (%)", pen.get("mean"), pen.get("industry"), "—"),
        ("Trademarks (per applicant)", tpa.get("mean"), tpa.get("industry"), tpa.get("company")),
        ("Years to first filing", yr.get("mean"), yr.get("industry"), yr.get("company")),
    ]
    body = "".join(
        f"<tr><td>{_esc(a)}</td><td class='num'>{_esc(b)}</td>"
        f"<td class='num'>{_esc(c)}</td><td class='num'>{_esc(d)}</td></tr>"
        for a, b, c, d in rows)
    note = ""
    if frac:
        note = (f"<p class='muted'>{round(frac*100)}% of companies file their first "
                f"trademark after incorporating; the typical company files "
                f"{_esc(means.get('mean_years_to_first_filing'))} years into its journey.</p>")
    return f"""
        <h2>How they compare</h2>
        <p class="muted">All-industry mean vs their industry (union of SIC codes) vs this company.</p>
        {note}
        <table><thead><tr><th>Metric</th><th class="num">All-industry mean</th>
          <th class="num">Their industry</th><th class="num">This company</th></tr></thead>
          <tbody>{body}</tbody></table>
    """


_BAND_COLOUR = {"Always": "#1D1D1B", "Often": "#2E7D32",
                "Sometimes": "#E69500", "Rarely": "#C0392B"}


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
  <p class="legend">Industry: SIC {_esc(', '.join(sics or []))}. Frequency in this industry:
     <b style="background:#1D1D1B">Always</b><b style="background:#2E7D32">Often</b>
     <b style="background:#E69500">Sometimes</b><b style="background:#C0392B">Rarely</b></p>
  {body}
  <div class="foot">A starting point based on what this industry typically protects — not legal
     advice. Final class/term selection should be confirmed for the specific goods and services.<br>
     The Trademark Helpline · Source: UK IPO registry (TemmyDB) + Companies House.</div>
</body></html>"""


def render(*, company_name, applicant, marks, sector_company=None, sector=None,
           benchmark=None) -> str:
    logo = _logo_data_uri()
    today = dt.date.today().strftime("%d %B %Y")

    marks_rows = "".join(
        f"<tr><td>{_esc(m.get('application_number'))}</td>"
        f"<td>{_esc((m.get('mark') or {}).get('verbal_element_text'))}</td>"
        f"<td>{_esc(m.get('status'))}</td>"
        f"<td>{_esc(m.get('expiry_date'))}</td></tr>"
        for m in (marks or [])[:50]) or \
        "<tr><td colspan=4 class='muted'>No marks on record.</td></tr>"

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
        <h2>Sector intelligence — SIC {_esc(sic)}</h2>
        <p class="muted">Sector derived from {_esc(comp_name)}'s Companies House SIC code.</p>
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

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Industry Trademark Report — {_esc(company_name)}</title>
<style>
  @page {{ size: A4; margin: 18mm; }}
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color:{BODY};
          font-size: 12px; line-height: 1.5; }}
  .hdr {{ display:flex; justify-content:space-between; align-items:center;
          border-bottom: 3px solid {PINK}; padding-bottom: 10px; margin-bottom: 18px; }}
  .hdr img {{ height: 46px; }}
  .hdr .meta {{ text-align:right; color:{SLATE}; font-size: 11px; }}
  h1 {{ color:{NAVY}; font-size: 22px; margin: 4px 0 2px; }}
  h2 {{ color:{PINK}; font-size: 16px; margin-top: 26px;
        border-bottom:1px solid #eee; padding-bottom:4px; }}
  h3 {{ color:{NAVY}; font-size: 13px; margin-top: 18px; }}
  .muted {{ color:{SLATE}; }}
  table {{ width:100%; border-collapse: collapse; margin-top: 6px; }}
  th, td {{ text-align:left; padding: 5px 8px; border-bottom: 1px solid #e8e8e8; }}
  th {{ background:{NAVY}; color:#fff; font-weight:600; font-size:11px; }}
  td.num, th.num {{ text-align:right; }}
  .cards {{ display:flex; gap:12px; margin: 12px 0; }}
  .card {{ flex:1; background:#faf3f5; border:1px solid #f0d6de; border-radius:8px;
           padding:12px; text-align:center; }}
  .card .big {{ color:{PINK}; font-size: 24px; font-weight:700; }}
  .card .lbl {{ color:{SLATE}; font-size: 11px; }}
  .foot {{ margin-top: 28px; color:{SLATE}; font-size: 10px;
           border-top:1px solid #eee; padding-top: 8px; }}
</style></head><body>
  <div class="hdr">
    <div>{'<img src="'+logo+'"/>' if logo else '<strong>The Trademark Helpline</strong>'}</div>
    <div class="meta">Industry Trademark Report<br>Generated {today}</div>
  </div>
  <h1>{_esc(company_name)}</h1>
  <p class="muted">Applicant on record · IPO {_esc(applicant.get('ipo_identifier'))}
     · {_esc(len(marks or []))} trademark(s)</p>

  <h2>Trademarks held</h2>
  <table><thead><tr><th>Application</th><th>Mark</th><th>Status</th><th>Expiry</th></tr></thead>
    <tbody>{marks_rows}</tbody></table>

  {sector_block}

  {_benchmark_block(benchmark)}

  <div class="foot">Counts include all trademarks ever filed (live and lapsed), for this
     legal entity only — group subsidiaries with separate company numbers are not aggregated.<br>
     The Trademark Helpline · Source: UK IPO registry (TemmyDB).
     Figures reflect companies matched to Companies House SIC codes. This report
     is informational and not legal advice.</div>
</body></html>"""

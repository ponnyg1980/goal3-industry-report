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


def render(*, company_name, applicant, marks, sector_company=None, sector=None) -> str:
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

  <div class="foot">The Trademark Helpline · Source: UK IPO registry (TemmyDB).
     Figures reflect companies matched to Companies House SIC codes. This report
     is informational and not legal advice.</div>
</body></html>"""

"""
Goal #3 — Industry Trademark Report (Streamlit dashboard + export).

Run:
    cd "goal3-industry-report"
    pip install -r requirements.txt
    streamlit run app.py

Two front doors:
  • Trademark registry (Temmy)   — companies that hold UK trademarks.
  • Companies House (any company)— any UK company, incl. ones with no marks
                                    (needs the free COMPANIES_HOUSE_API_KEY).
Sector intelligence always comes from Temmy (by SIC), via Query Runs.
"""
import streamlit as st

import data_access as da
import companies_house as ch
import branded_report as br

st.set_page_config(page_title="Industry Trademark Report", layout="wide")
st.title("Industry Trademark Report")
st.caption("MOAT for Braudit · Goal #3 — company + sector trademark intelligence")

# ── connection status ────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.success("Temmy API: connected") if (da.api_ready() and da.health()) \
    else c1.error("Temmy API: not reachable")
c2.success("Query Runs: live") if da.query_runs_ready() \
    else c2.warning("Query Runs: pending key")
c3.success("Companies House: live") if ch.ready() \
    else c3.warning("Companies House: no key (registry-only lookups)")
st.divider()

# ── input ────────────────────────────────────────────────────────────
source = st.radio(
    "Find a company via",
    ["Trademark registry (has marks)", "Companies House (any UK company)"],
    horizontal=True,
    help="Companies House lets you look up any company, including ones with no "
         "trademarks. It needs the free CH API key.")

with st.form("lookup"):
    name = st.text_input("Company name", placeholder="e.g. Greggs")
    submitted = st.form_submit_button("Build report")

if not submitted or not name.strip():
    st.info("Enter a company name to build its industry trademark report.")
    st.stop()

# These get populated by whichever path runs, then drive the sector panel + export.
appl = {}          # {name, ipo_identifier}
marks = []
sics = []
sector_company = None  # {name, number, sic_codes}

# ── PATH A: Trademark registry (Temmy) ───────────────────────────────
if source.startswith("Trademark"):
    st.header(f"Company: {name}")
    results = da.search_company(name.strip(), limit=50)
    if not results:
        st.warning("No matching applicant found in the registry. "
                   "Try the Companies House option for companies without marks.")
        st.stop()
    labels = [f"{r['applicant'].get('name','?')}  "
              f"(IPO {r['applicant'].get('ipo_identifier','?')}, "
              f"{len(r['trademarks'])} marks)" for r in results]
    idx = st.selectbox("Matched applicant", range(len(results)),
                       format_func=lambda i: labels[i])
    appl = results[idx]["applicant"]
    marks = results[idx]["trademarks"]
    if da.query_runs_ready():
        sector_company = da.applicant_sic(appl.get("ipo_identifier"))
        sics = (sector_company or {}).get("sic_codes") or []

# ── PATH B: Companies House (any company) ────────────────────────────
else:
    if not ch.ready():
        st.error("Companies House lookups need a free API key. Add "
                 "`COMPANIES_HOUSE_API_KEY` to temmy-access/secrets.env "
                 "(register at developer.company-information.service.gov.uk).")
        st.stop()
    st.header(f"Company: {name}")
    hits = ch.search(name.strip(), limit=10)
    if not hits:
        st.warning("No companies found on Companies House for that name.")
        st.stop()
    labels = [f"{h['title']} — {h['company_number']} ({h.get('status','')})"
              for h in hits]
    idx = st.selectbox("Companies House match", range(len(hits)),
                       format_func=lambda i: labels[i])
    prof = ch.profile(hits[idx]["company_number"])
    if not prof:
        st.warning("Couldn't fetch that company's profile.")
        st.stop()
    sector_company = prof
    sics = prof.get("sic_codes") or []
    appl = {"name": prof.get("name"), "ipo_identifier": None}
    # Does this company also hold any trademarks in Temmy? (best-effort)
    reg = da.search_company(prof.get("name") or name, limit=50)
    if reg:
        marks = reg[0]["trademarks"]

# ── company summary ──────────────────────────────────────────────────
m1, m2, m3 = st.columns(3)
m1.metric("Trademarks found", len(marks))
m2.metric("Company", (sector_company or {}).get("name", appl.get("name", "—")))
m3.metric("Company no.", (sector_company or {}).get("number", "—"))
if marks:
    st.subheader("Marks held")
    st.dataframe(
        [{"Application": m.get("application_number"),
          "Mark": (m.get("mark") or {}).get("verbal_element_text"),
          "Status": m.get("status"), "Expiry": m.get("expiry_date")} for m in marks],
        use_container_width=True, hide_index=True)

# ── sector intelligence (Temmy / Query Runs) ─────────────────────────
st.header("Sector intelligence")
rep = None
if not da.query_runs_ready():
    st.info("🔒 Add `TEMMY_QUERY_RUNS_API_KEY` to activate sector intelligence.")
elif not sics:
    st.warning("No SIC codes available for this company, so no sector view.")
else:
    if sector_company:
        st.caption(f"Matched company: **{sector_company.get('name')}** "
                   f"(no. {sector_company.get('number','—')}) · SIC {', '.join(sics)}")
    sic = st.selectbox("Sector (SIC code)", sics)
    rep = da.sector_report(sic)
    size = rep.get("size", {})
    s1, s2, s3 = st.columns(3)
    s1.metric("Trademarks in sector", f"{size.get('trademarks', 0):,}")
    s2.metric("Companies in sector", f"{size.get('companies', 0):,}")
    s3.metric("Sector first filed", rep.get("first_filed_year") or "—")
    st.subheader("Top 3 companies in the sector")
    st.dataframe(rep.get("top_companies", []), use_container_width=True, hide_index=True)
    st.subheader("Class distribution")
    st.bar_chart({str(r["nice_class"]): r["trademarks"]
                  for r in rep.get("class_distribution", [])})

# ── export ───────────────────────────────────────────────────────────
st.divider()
report_html = br.render(company_name=(sector_company or {}).get("name") or appl.get("name") or name,
                        applicant=appl, marks=marks,
                        sector_company=sector_company, sector=rep)
st.download_button("⬇ Export branded report (HTML)", data=report_html,
                   file_name=f"industry_report_{name.strip().replace(' ', '_')}.html",
                   mime="text/html")
st.caption("Branded, print-to-PDF ready. Server-side PDF can be added via pdfkit.")

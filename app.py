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


# ── cached data calls (Streamlit re-runs the whole script per click) ──
@st.cache_data(ttl=1800, show_spinner=False)
def c_search(name):
    return da.search_company(name, limit=50)


@st.cache_data(ttl=1800, show_spinner=False)
def c_applicant_sic(iid):
    return da.applicant_sic(iid)


@st.cache_data(ttl=1800, show_spinner=False)
def c_sector(sic):
    return da.sector_report(sic)


@st.cache_data(ttl=1800, show_spinner=False)
def c_benchmark(number, sics_tuple):
    return da.benchmark(number, list(sics_tuple))


@st.cache_data(ttl=1800, show_spinner=False)
def c_ch_search(name):
    return ch.search(name, limit=10)


@st.cache_data(ttl=1800, show_spinner=False)
def c_ch_profile(num):
    return ch.profile(num)


st.set_page_config(page_title="Industry Trademark Report", layout="wide")
st.title("Industry Trademark Report")
st.caption("MOAT for Braudit · Goal #3 — company + sector trademark intelligence")

# ── connection status ────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
if da.api_ready() and da.health():
    c1.success("Temmy API: connected")
else:
    c1.error("Temmy API: not reachable")
if da.query_runs_ready():
    c2.success("Query Runs: live")
else:
    c2.warning("Query Runs: pending key")
if ch.ready():
    c3.success("Companies House: live")
else:
    c3.warning("Companies House: no key (registry-only lookups)")
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
    results = c_search(name.strip())
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
        sector_company = c_applicant_sic(appl.get("ipo_identifier"))
        sics = (sector_company or {}).get("sic_codes") or []

# ── PATH B: Companies House (any company) ────────────────────────────
else:
    if not ch.ready():
        st.error("Companies House lookups need a free API key. Add "
                 "`COMPANIES_HOUSE_API_KEY` to temmy-access/secrets.env "
                 "(register at developer.company-information.service.gov.uk).")
        st.stop()
    st.header(f"Company: {name}")
    hits = c_ch_search(name.strip())
    if not hits:
        st.warning("No companies found on Companies House for that name.")
        st.stop()
    labels = [f"{h['title']} — {h['company_number']} ({h.get('status','')})"
              for h in hits]
    idx = st.selectbox("Companies House match", range(len(hits)),
                       format_func=lambda i: labels[i])
    prof = c_ch_profile(hits[idx]["company_number"])
    if not prof:
        st.warning("Couldn't fetch that company's profile.")
        st.stop()
    sector_company = prof
    sics = prof.get("sic_codes") or []
    appl = {"name": prof.get("name"), "ipo_identifier": None}
    # Does this company also hold any trademarks in Temmy? (best-effort)
    reg = c_search(prof.get("name") or name)
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
st.caption("ℹ️ Figures are for this legal entity (company number). Large corporate "
           "groups may hold further trademarks in subsidiaries with separate company "
           "numbers — those are not aggregated here.")

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
    rep = c_sector(sic)
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

# ── benchmarking: company vs industry vs all-industry MEAN ───────────
bench = None
if da.query_runs_ready() and sics and sector_company:
    st.header("How they compare")
    st.caption("Three reference points per metric — the all-industry **MEAN**, "
               "**their industry** (union of their SIC codes), and **this company**. "
               "Counts include all trademarks ever filed (live and lapsed) — a measure "
               "of filing activity; the Marks-held table above shows each mark's status.")
    with st.spinner("Crunching the benchmarks…"):
        bench = c_benchmark(sector_company.get("number"), tuple(sics))
    m = bench["metrics"]

    # 1) Penetration
    pen = m["penetration_pct"]
    st.subheader("Trademark penetration")
    p1, p2 = st.columns(2)
    p1.metric("Their industry", f"{pen['industry']}%" if pen['industry'] is not None else "—",
              delta=(f"{round(pen['industry']-pen['mean'],1)} pts vs mean"
                     if pen['industry'] is not None and pen['mean'] else None))
    p2.metric("All-industry mean", f"{pen['mean']}%" if pen['mean'] else "—")
    if pen['industry'] is not None and pen['mean']:
        st.write(f"Only **{pen['industry']}%** of companies in their industry hold a "
                 f"registered trademark, vs an all-industry average of **{pen['mean']}%** "
                 f"— their sector is **{pen['industry_vs_mean']}** average trademark activity.")

    # 2) Trademarks per applicant
    tpa = m["trademarks_per_applicant"]
    st.subheader("Trademarks held")
    t1, t2, t3 = st.columns(3)
    t1.metric("This company", tpa["company"])
    t2.metric("Industry avg / applicant", tpa["industry"])
    t3.metric("All-industry mean", tpa["mean"])

    # 3) Stage of journey
    yr = m["years_to_first_filing"]
    means = bench["means"]
    st.subheader("When they protect their brand")
    frac = means.get("frac_trademark_post_incorporation")
    if frac:
        st.write(f"**{round(frac*100)}%** of companies file their first trademark "
                 f"*after* forming. The typical company files **{means.get('mean_years_to_first_filing')} years** "
                 f"into its journey; this industry averages **{yr['industry']} years**.")
    if yr["company"] is not None:
        earlier = yr["company"] < (yr["industry"] or yr["mean"] or 0)
        st.write(f"**{bench['company'].get('name')}** filed its first trademark "
                 f"**{yr['company']} years** after incorporating — "
                 f"{'earlier (more proactive) than' if earlier else 'later than'} the "
                 f"industry norm of {yr['industry']} years.")

    # summary table
    st.subheader("Summary")
    st.dataframe([
        {"Metric": "Trademark penetration (%)", "All-industry MEAN": pen["mean"],
         "Their industry": pen["industry"], "This company": "—"},
        {"Metric": "Trademarks (per applicant)", "All-industry MEAN": tpa["mean"],
         "Their industry": tpa["industry"], "This company": tpa["company"]},
        {"Metric": "Years to first filing", "All-industry MEAN": yr["mean"],
         "Their industry": yr["industry"], "This company": yr["company"]},
    ], use_container_width=True, hide_index=True)

# ── export ───────────────────────────────────────────────────────────
st.divider()
report_html = br.render(company_name=(sector_company or {}).get("name") or appl.get("name") or name,
                        applicant=appl, marks=marks,
                        sector_company=sector_company, sector=rep, benchmark=bench)
st.download_button("⬇ Export branded report (HTML)", data=report_html,
                   file_name=f"industry_report_{name.strip().replace(' ', '_')}.html",
                   mime="text/html")
st.caption("Branded, print-to-PDF ready. Server-side PDF can be added via pdfkit.")

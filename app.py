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

import pandas as pd

import data_access as da
import companies_house as ch
import branded_report as br
import recommend as rec
import risk as rk


# ── cached data calls (Streamlit re-runs the whole script per click) ──
@st.cache_data(ttl=1800, show_spinner=False)
def c_class_rec(sics_tuple):
    return rec.class_recommendations(list(sics_tuple))


@st.cache_data(ttl=1800, show_spinner=False)
def c_term_rec(sics_tuple, cls):
    return rec.term_recommendations(list(sics_tuple), cls)



@st.cache_data(ttl=1800, show_spinner=False)
def c_search(name):
    return da.search_company(name, limit=50)


@st.cache_data(ttl=1800, show_spinner=False)
def c_similar(brand):
    return da.similar_marks(brand)


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

# ── service status (client-facing: only speak up when something is down) ──
if not (da.api_ready() and da.health()):
    st.error("Our trademark data service is temporarily unavailable — "
             "please try again in a few minutes.")
    st.stop()
if not da.query_runs_ready():
    st.warning("Sector intelligence is temporarily unavailable — "
               "company and trademark lookups still work.")

# ── input ────────────────────────────────────────────────────────────
with st.form("lookup"):
    name = st.text_input("Type your brand or company name",
                         placeholder="e.g. Greggs")
    submitted = st.form_submit_button("Build my report")

# Persist the search across reruns — without this, picking from any dropdown
# below blanks the page (the form only reports True on the click's run).
if submitted and name.strip():
    st.session_state["query"] = name.strip()
query = st.session_state.get("query", "")
if not query:
    st.info("Enter your brand or company name to see how your industry "
            "protects its trademarks.")
    st.stop()

# These get populated by whichever path runs, then drive the sector panel + export.
appl = {}          # {name, ipo_identifier}
marks = []
sics = []
sector_company = None  # {name, number, sic_codes}
rec_html = None    # populated by the recommendations section, downloaded at the end

def _reg_lookup(*names):
    """Registry search that tolerates legal suffixes: tries each candidate
    name, then the same with LIMITED/LTD/PLC/LLP stripped ('GREGGS PLC'
    finds nothing; 'GREGGS' finds the marks)."""
    import re as _re
    tried = set()
    for n in names:
        n = (n or "").strip()
        for cand in (n, _re.sub(r"\s+(LIMITED|LTD|PLC|LLP)\.?$", "", n,
                                flags=_re.I).strip()):
            if cand and cand.upper() not in tried:
                tried.add(cand.upper())
                r = c_search(cand)
                if r:
                    return r
    return None


# ── one simple search: Companies House first, registry marks attached ─
if ch.ready():
    hits = c_ch_search(query)
    if not hits:
        st.warning("We couldn't find a company with that name — check the "
                   "spelling or try the registered company name.")
        st.stop()
    labels = [f"{h['title']} — {h['company_number']} ({h.get('status','')})"
              for h in hits]
    idx = st.selectbox("Select your company", range(len(hits)),
                       format_func=lambda i: labels[i])
    prof = c_ch_profile(hits[idx]["company_number"])
    if not prof:
        st.warning("We couldn't fetch that company's details — please try again.")
        st.stop()
    sector_company = prof
    sics = prof.get("sic_codes") or []
    appl = {"name": prof.get("name"), "ipo_identifier": None}
    # Does this company also hold any trademarks in Temmy? (best-effort)
    reg = _reg_lookup(prof.get("name"), query)
    if reg:
        marks = reg[0]["trademarks"]
        appl["ipo_identifier"] = reg[0]["applicant"].get("ipo_identifier")
else:
    # Fallback (no Companies House key): trademark registry only.
    results = c_search(query)
    if not results:
        st.warning("We couldn't find that name in the trademark registry — "
                   "check the spelling or try the registered company name.")
        st.stop()
    labels = [f"{r['applicant'].get('name','?')}  "
              f"({len(r['trademarks'])} marks)" for r in results]
    idx = st.selectbox("Select your company", range(len(results)),
                       format_func=lambda i: labels[i])
    appl = results[idx]["applicant"]
    marks = results[idx]["trademarks"]
    if da.query_runs_ready():
        sector_company = c_applicant_sic(appl.get("ipo_identifier"))
        sics = (sector_company or {}).get("sic_codes") or []

# Show the matched (canonical) company name, not what was typed.
display_name = (sector_company or {}).get("name") or appl.get("name") or query
st.header(display_name)

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

# ── marks like yours: risk overview (same rules as the Audit Report) ──
risk_res = None
if da.query_runs_ready():
    st.header("Marks like yours on the register")
    with st.spinner("Checking the register for similar marks…"):
        cand = c_similar(query)
    if not cand:
        st.success("No similar marks found on the register — "
                   "a good sign for your brand name.")
    else:
        tgt = []
        if sics:
            _cr = c_class_rec(tuple(sics))
            tgt = [c["class"] for c in _cr.get("classes", [])
                   if c.get("tier") in ("a", "b")]
        risk_res = rk.assess(
            cand, brand=query, target_classes=tgt,
            own_applicant_names=[appl.get("name") or "",
                                 (sector_company or {}).get("name") or ""])
        counts = risk_res["counts"]
        r1, r2, r3 = st.columns(3)
        r1.metric("🔴 High risk", counts.get("High Risk", 0))
        r2.metric("🟠 Medium risk", counts.get("Medium Risk", 0))
        r3.metric("🟢 Low risk", counts.get("Low Risk", 0))
        st.dataframe(
            [{"Risk": x["risk"], "Mark": x.get("verbal_element_text"),
              "Owner": x.get("applicant_name"), "Status": x.get("status"),
              "Type": x.get("mark_type"),
              "Classes": ", ".join(str(c) for c in (x.get("classes") or []))}
             for x in risk_res["marks"]],
            use_container_width=True, hide_index=True)
        st.caption("Banded with the same rules as our Audit Report: status, "
                   "similarity to your name, mark type and overlap with the "
                   "classes your industry registers in. Lapsed marks are "
                   "excluded as negligible.")

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

    def _cls_label(n):
        """'09 · Electronics & software' — zero-padded so chart order is numeric."""
        h = rec.NICE_HEADINGS.get(int(n), "")
        h = (h[:34] + "…") if len(h) > 35 else h
        return f"{int(n):02d} · {h}" if h else f"{int(n):02d}"

    st.bar_chart({_cls_label(r["nice_class"]): r["trademarks"]
                  for r in sorted(rep.get("class_distribution", []),
                                  key=lambda r: int(r["nice_class"]))})
    st.caption("Nice classes (1–45) — the categories trademarks are registered under.")

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

# ── Goal #1: Class & term recommendations (editable, downloadable) ────
# Keyed on tier (a/b/c/d), not the band words — so if the wording in
# freesearch.bands changes, this UI follows automatically.
_TIER_EMOJI = {"a": "⬛", "b": "🟩", "c": "🟧", "d": "🟥"}


def _chip(row):
    """'⬛ All use this' from a row carrying tier + band label."""
    return f"{_TIER_EMOJI.get(row.get('tier', 'd'), '🟥')} {row.get('band', '')}"


st.divider()
st.header("Class & term recommendations")
st.caption("Suggested Nice classes and goods/services terms for your industry, "
           "banded by how many businesses like yours protect each: "
           "⬛ All use this · 🟩 Most · 🟧 Some · 🟥 A few. Untick anything you "
           "don't need, then download your selection below.")

if not (da.query_runs_ready() and sics and sector_company):
    st.info("Sector recommendations aren't available for this company right now.")
else:
    with st.container():
        with st.spinner("Building class & term recommendations…"):
            cr = c_class_rec(tuple(sics))
        if cr.get("inconclusive"):
            # point 8: the SIC(s) describe no goods/services — route, don't guess
            st.warning(cr.get("message") or
                       "This SIC code doesn't describe the goods or services "
                       "specifically enough to suggest classes.")
            for s in cr.get("inconclusive_sics", []):
                st.caption(f"SIC {s['sic']} — {s['reason']}")
            st.markdown("**Better ways to get this right:**")
            for rt in cr.get("routes", []):
                # TODO: once the website URLs for these tools are confirmed,
                # link each label (e.g. free-search wizard / contact form).
                st.markdown(f"- **{rt['label']}** — {rt['note']}")
            st.caption("These are available from The Trademark Helpline — "
                       "get in touch and we'll run them with you.")
        elif not cr["classes"]:
            st.warning("No class data for this industry.")
        else:
            st.caption(f"Industry = SIC {', '.join(sics)} · {cr['total']:,} trademarks.")
            cls_df = pd.DataFrame([{
                "Keep": c["tier"] != "d",
                "Band": _chip(c),
                "Class": c["class"],
                "Heading": c["heading"],
                "% of industry": c["pct"],
                "Trademarks": c["trademarks"],
            } for c in cr["classes"]])
            edited = st.data_editor(
                cls_df, hide_index=True, use_container_width=True, key="cls_editor",
                column_config={"Keep": st.column_config.CheckboxColumn(required=True)},
                disabled=["Band", "Class", "Heading", "% of industry", "Trademarks"])
            kept_class_nums = set(edited[edited["Keep"]]["Class"].tolist())

            st.subheader("Terms within kept classes")
            kept_ordered = [c for c in cr["classes"] if c["class"] in kept_class_nums]
            review = st.multiselect(
                "Review goods/services terms for which classes?",
                options=[c["class"] for c in kept_ordered],
                default=[c["class"] for c in kept_ordered if c["tier"] == "a"],
                format_func=lambda n: f"Class {n}",
                help="Only the classes you pick here load their term lists "
                     "(keeps the page fast). Unpicked kept classes are saved at class level.")
            selection = []
            for c in kept_ordered:
                kept_terms = []
                if c["class"] in review:
                    st.markdown(f"**{_chip(c)} · Class {c['class']} — "
                                f"{c['heading']}**  ({c['pct']}%)")
                    with st.spinner(f"Loading class {c['class']} terms…"):
                        tr = c_term_rec(tuple(sics), c["class"])
                    if not tr["terms"]:
                        st.write("_No terms found._")
                    else:
                        tdf = pd.DataFrame([{
                            "Keep": t["tier"] != "d",
                            "Band": _chip(t),
                            "Term": t["term"],
                            "% of class": t["pct"],
                        } for t in tr["terms"]])
                        te = st.data_editor(
                            tdf, hide_index=True, use_container_width=True,
                            key=f"term_editor_{c['class']}",
                            column_config={"Keep": st.column_config.CheckboxColumn(required=True)},
                            disabled=["Band", "Term", "% of class"])
                        band_of = {t["term"]: t["band"] for t in tr["terms"]}
                        kept_terms = [{"term": x, "band": band_of.get(x, "")}
                                      for x in te[te["Keep"]]["Term"].tolist()]
                selection.append({"class": c["class"], "heading": c["heading"],
                                  "band": c["band"], "pct": c["pct"], "terms": kept_terms})

            # ── selection → branded sheet, offered in Downloads below ──
            rec_html = br.render_recommendations(display_name, sics, selection)
            st.caption(f"{len(selection)} class(es) kept — your tailored "
                       "recommendation sheet is ready in Downloads below.")

# ── downloads ────────────────────────────────────────────────────────
st.divider()
st.header("Downloads")
# Top sector applicants' own marks (best-effort, for the report appendix).
top_marks = {}
if rep:
    for tcomp in rep.get("top_companies", [])[:3]:
        mk = da.company_marks(tcomp.get("company_number") or "")
        if mk:
            top_marks[tcomp.get("name")] = mk
report_html = br.render(company_name=display_name, applicant=appl, marks=marks,
                        sector_company=sector_company, sector=rep, benchmark=bench,
                        risk=risk_res, top_applicant_marks=top_marks)
fn = display_name.strip().replace(" ", "_")
d1, d2 = st.columns(2)
d1.download_button("⬇ Industry trademark report (HTML)", data=report_html,
                   file_name=f"industry_report_{fn}.html", mime="text/html")
if rec_html:
    d2.download_button("⬇ Class & term recommendations (HTML)", data=rec_html,
                       file_name=f"class_term_recommendations_{fn}.html",
                       mime="text/html")
st.caption("Print-ready — open the file and use your browser's "
           "Print → Save as PDF.")

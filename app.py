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
def c_type_rec(business_type):
    return rec.class_recommendations_for_type(business_type)


@st.cache_data(ttl=1800, show_spinner=False)
def c_candidates(sics_tuple):
    return rec.candidate_types(list(sics_tuple))



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

# ── magic link (item 2) ──────────────────────────────────────────────
# A report link like  https://<app>/?company=13327422  opens with the company
# already loaded — no typing. That's what goes in client emails: one click and
# the report is theirs. (?tn=Trading+Name&tny=3 optionally pre-fills Trading
# Name Mode.)
_qp = st.query_params
_link_company = (_qp.get("company") or "").strip()


import importlib
import nuggets as nug

# Streamlit hot-reloads app.py but keeps helper modules in sys.modules, so a
# changed nuggets.py can stay stale until the app is rebooted — that's what
# made the loader fall back to showing ALL eight cards instead of a set of
# four. Reloading here (the module is ~5KB, so it's free) means a deploy of
# nuggets.py always takes effect immediately.
try:
    nug = importlib.reload(nug)
except Exception:
    pass


def _cards(which: str, message: str) -> str:
    """Render a nugget set, tolerating a stale `nuggets` module.

    Streamlit reloads app.py on deploy but keeps already-imported modules in
    sys.modules — so a NEW attribute or signature in nuggets.py can be absent
    at runtime until the app is rebooted (the same sys.modules trap noted in
    CLAUDE.md for the Vienna work). A loading screen must never be the thing
    that breaks a deploy, so we degrade instead of raising.
    """
    all_ = getattr(nug, "NUGGETS", [])
    sets = {"one": getattr(nug, "SET_ONE", None) or all_[:4],
            "two": getattr(nug, "SET_TWO", None) or all_[4:]}
    cards = sets.get(which) or all_
    try:
        return nug.carousel_html(cards, message=message)
    except TypeError:            # older signature: no per-set argument
        try:
            return nug.carousel_html(message=message)
        except Exception:
            return f"<p style='text-align:center;padding:40px'>{message}</p>"
    except Exception:
        return f"<p style='text-align:center;padding:40px'>{message}</p>"


_stage = st.session_state.get("stage", "input")
if _link_company and _stage == "input":
    # Magic link: straight past the form to the build.
    st.session_state["company_number"] = _link_company
    st.session_state["trading_name"] = (_qp.get("tn") or "").strip()
    try:
        st.session_state["trading_years"] = float(_qp.get("tny") or 0) or None
    except (TypeError, ValueError):
        st.session_state["trading_years"] = None
    st.session_state["tn_same_sector"] = True
    st.session_state["tn_type"] = None
    _stage = st.session_state["stage"] = "build1"


# ── STAGE: input 1 — find the company ────────────────────────────────
if _stage == "input":
    st.subheader("Let's find your company")
    st.caption("This report is built from your official Companies House "
               "record, so we start there. Looking up a brand name rather "
               "than a company? Use our Free Trademark Search instead.")

    _name = st.text_input("Input UK Company Name", placeholder="e.g. Greggs Plc")
    if _name.strip():
        st.session_state["query"] = _name.strip()

    _q = st.session_state.get("query", "")
    _chosen = None
    if _q:
        if ch.ready():
            _hits = c_ch_search(_q)
            if not _hits:
                st.warning("We couldn't find a company with that name — check "
                           "the spelling, or try the full registered name.")
            else:
                _labels = [f"{h['title']} — {h['company_number']} "
                           f"({h.get('status','')})" for h in _hits]
                _i = st.selectbox("Select your company", range(len(_hits)),
                                  format_func=lambda i: _labels[i])
                _chosen = _hits[_i]["company_number"]
        else:
            st.error("Companies House lookup is unavailable right now.")

    _tn, _tny, _same, _type = "", None, True, None
    if _chosen:
        with st.expander("Do you trade under a different name?"):
            st.markdown(
                "This report is based on your **registered company name**. If "
                "your customers know you by something else — a brand over the "
                "door, on your website, on your invoices — that trading name "
                "is what needs protecting. Switch it on and we'll run the "
                "report on that instead.")
            if st.toggle("Use Trading Name Mode"):
                _tn = st.text_input("Your trading name")
                _same = st.radio("Same sector and industry as your company?",
                                 ["Yes", "No"], horizontal=True,
                                 help="Yes: keep the sector picture from your "
                                      "Companies House record. No: tell us the "
                                      "business type and we'll use that.") == "Yes"
                if not _same:
                    _type = st.selectbox("What kind of business trades under "
                                         "this name?", rec.all_types(),
                                         index=None, placeholder="Start typing…")
                _tny = st.number_input(
                    "How long have you traded under this name? (years)",
                    min_value=0.0, max_value=100.0, step=0.5, value=0.0,
                    help="Time in genuine use builds unregistered rights and "
                         "strengthens an application.")

        st.divider()
        if st.button("See how my industry protects itself →", type="primary",
                     use_container_width=True):
            st.session_state.update(
                company_number=_chosen, trading_name=_tn.strip(),
                trading_years=_tny or None, tn_same_sector=_same,
                tn_type=_type, stage="build1")
            st.rerun()
    st.stop()


# ══════════════════════════════════════════════════════════════════════
# SIX-STAGE FLOW (Jonathan, 20 Jul)
#   input   → build1 → sector  →  input2  → build2 → report
#   company   cards    SECTOR      classes?  cards    FULL TAILORED
#                      ONLY        + Q&A              REPORT
#
# Two reveals, because they do different jobs. The first proves we have real
# data about their industry — earned credibility, nothing asked of them yet.
# Only then do we ask for the answers that make the second report personal.
# ══════════════════════════════════════════════════════════════════════

# ── STAGE: build 1 — the register and the sector ─────────────────────
if _stage == "build1":
    st.markdown(_cards("one", "Reading the register, your sector and "
                              "Companies House…"), unsafe_allow_html=True)
    _num0 = st.session_state.get("company_number", "")
    _prof0 = c_ch_profile(_num0)
    if _prof0:
        _s0 = _prof0.get("sic_codes") or []
        try:
            if _s0:
                rec.ensure_seeded(_s0)          # may be a live seed (~7s)
                c_class_rec(tuple(_s0))
            c_similar(st.session_state.get("trading_name") or _prof0.get("name"))
            if _s0 and da.query_runs_ready():
                c_sector(_s0[0])
                c_benchmark(_num0, tuple(_s0))
        except Exception:
            pass
    st.session_state["stage"] = "sector"
    st.rerun()


# ── STAGE: build 2 — tailoring to their answers ──────────────────────
if _stage == "build2":
    st.markdown(_cards("two", "Tailoring your report to the classes and "
                              "answers you gave us…"), unsafe_allow_html=True)
    try:
        for _c in st.session_state.get("kept_classes", [])[:6]:
            c_term_rec(tuple(st.session_state.get("sics", [])), _c)
    except Exception:
        pass
    st.session_state["stage"] = "report"
    st.rerun()


# ── STAGE 3: the report ──────────────────────────────────────────────
_num = st.session_state.get("company_number", "")
if not _num:
    st.session_state["stage"] = "input"
    st.rerun()

query = st.session_state.get("query", "")
trading_name = (st.session_state.get("trading_name") or "").strip()
trading_years = st.session_state.get("trading_years")
tn_same_sector = st.session_state.get("tn_same_sector", True)
st.session_state["tn_business_type"] = (
    None if tn_same_sector else st.session_state.get("tn_type"))

appl = {}
marks = []
sics = []
sector_company = None
rec_html = None


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


prof = c_ch_profile(_num)
if not prof:
    st.warning("We couldn't load that company from Companies House — it may "
               "have been dissolved or renamed.")
    if st.button("Start again"):
        st.session_state["stage"] = "input"
        st.rerun()
    st.stop()

sector_company = prof
sics = prof.get("sic_codes") or []
appl = {"name": prof.get("name"), "ipo_identifier": None}
reg = _reg_lookup(prof.get("name"), query)
if reg:
    marks = reg[0]["trademarks"]
    appl["ipo_identifier"] = reg[0]["applicant"].get("ipo_identifier")

company_name = prof.get("name") or query
if trading_name:
    display_name = trading_name
    reg_tn = _reg_lookup(trading_name)
    marks = reg_tn[0]["trademarks"] if reg_tn else []
    if reg_tn:
        appl = reg_tn[0]["applicant"]
    if ch.ready():
        _clash = [h for h in (c_ch_search(trading_name) or [])
                  if h.get("title", "").upper()
                  .replace(" LIMITED", "").replace(" LTD", "")
                  == trading_name.upper()]
        if _clash:
            st.warning(f"Heads-up: **{len(_clash)} compan"
                       f"{'y is' if len(_clash)==1 else 'ies are'} registered "
                       f"at Companies House under this exact name** — worth "
                       f"reviewing in the audit, because a company "
                       f"registration isn't a trademark but it can signal a "
                       f"competing claim.")
else:
    display_name = company_name

_hdr, _btn = st.columns([5, 1])
with _btn:
    if st.button("↻ New report", use_container_width=True):
        for _k in ("stage", "company_number", "query", "trading_name",
                   "trading_years", "tn_type", "logged_report"):
            st.session_state.pop(_k, None)
        st.rerun()

st.header(display_name)
if trading_name.strip():
    st.caption(f"Trading name of **{company_name}**"
               + (f" · trading {trading_years:g} years" if trading_years else ""))


# ══════════════════════════════════════════════════════════════════════
# REVEAL 1 — sector information only
# No viability, no risk table, no CTA yet: this is the free, factual
# picture of their industry. It earns the right to ask for their answers.
# ══════════════════════════════════════════════════════════════════════
if _stage == "sector":
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
    st.caption("The register, filtered to businesses like yours: how many "
               "protect their brand, which classes they use, and who leads. "
               "This is real filing behaviour — not our opinion.")
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
        st.caption("The most protected brands in your space. If the leaders in "
                   "your sector hold trademarks, that's the market telling you "
                   "what it takes to compete — see their actual marks below.")
        st.dataframe(rep.get("top_companies", []), use_container_width=True, hide_index=True)
        # item 6 — proof, not assertion: show each leader's actual trademarks.
        # Look up by COMPANY NUMBER via SQL, not by name via mark-text search:
        # data_access.company_marks says it plainly — "REST applicant search
        # misses many legal names; the SQL join by company_number doesn't".
        for _tc in (rep.get("top_companies") or [])[:3]:
            _tc_name = _tc.get("name") or ""
            _tc_num = _tc.get("company_number") or ""
            _tc_count = _tc.get("trademarks")
            if not _tc_name:
                continue
            with st.expander(f"View trademarks — {_tc_name}"
                             + (f" ({_tc_count})" if _tc_count else "")):
                _tm = da.company_marks(_tc_num, limit=500) if _tc_num else []
                if not _tm:
                    # Some groups file under an applicant record with no company
                    # number attached — fall back to the name search.
                    _alt = _reg_lookup(_tc_name)
                    _tm = [{"mark": (t.get("mark") or {}).get("verbal_element_text"),
                            "status": t.get("status")}
                           for t in (_alt[0]["trademarks"] if _alt else [])]
                if not _tm:
                    st.write("_Their marks are filed under a different legal "
                             "entity, so we can't list them here._")
                else:
                    st.caption(f"{len(_tm)} marks on the register.")
                    st.dataframe(_tm, use_container_width=True, hide_index=True)

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
        st.caption("Your company against your sector's norms: how common "
                   "protection is, how much the protected hold, and at what "
                   "stage businesses like yours typically file. It answers the "
                   "question every founder asks — am I early, on time, or late?")
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


    st.divider()
    st.subheader("Now let's make this about you")
    st.markdown(
        "That's how your **industry** protects itself. The next part is "
        "specific to **your** name: how viable it is as a trademark, what "
        "the register already holds against it, and what it would take to "
        "protect it properly.")
    if st.button("Get my tailored report →", type="primary",
                 use_container_width=True):
        st.session_state["stage"] = "input2"
        st.rerun()
    st.stop()


# ══════════════════════════════════════════════════════════════════════
# INPUT 2 — classes (optional), the three questions, jurisdictions
# ══════════════════════════════════════════════════════════════════════
if _stage == "input2":
    st.session_state["sics"] = sics
    # the register check already ran during build 1 (cached), so the
    # "we found N similar marks" line in Q2 is a fact of their report.
    _cand = c_similar(display_name) or []
    _tgt = [c["class"] for c in (c_class_rec(tuple(sics)).get("classes", []) if sics else [])
            if c.get("tier") in ("a", "b")]
    _rr = rk.assess(_cand, brand=display_name, target_classes=_tgt,
                    own_applicant_names=[appl.get("name") or "",
                                         (sector_company or {}).get("name") or ""]) if _cand else None
    _n_sim = sum((_rr or {}).get("counts", {}).values()) if _rr else 0

    st.subheader("Your classes and terms")
    st.markdown(
        "Classes are the categories your protection covers. Picking them now "
        "makes the report specific — but it's the longest part, so you can "
        "skip it and we'll cover it at the audit instead.")
    _do_classes = st.radio(
        "Would you like to pick your classes and descriptions now?",
        ["Yes — show me the recommendations", "Skip for now"],
        index=0, label_visibility="collapsed") == "Yes — show me the recommendations"

    if _do_classes:
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
            # ── View toggle: whole SIC vs specific business type ──────────────
            # A shared SIC (62012 covers SaaS, fintech, cybersecurity…) blends very
            # different filing patterns. If the SIC maps to more than one business
            # type, ask which one this company is and use the classification sweep's
            # per-type bands + the characteristic terms that disambiguate the classes.
            candidates = c_candidates(tuple(sics))
            chosen_type = None
            # Trading Name Mode with "different sector": the user already told us the
            # business type — use it, don't ask again.
            _tn_bt = st.session_state.get("tn_business_type")
            if _tn_bt:
                chosen_type = _tn_bt
                st.caption(f"Sector basis: **{_tn_bt}** (your trading name's business "
                           f"type, as you told us — not the registered company's SIC).")
            elif len(candidates) > 1:
                cand_names = [c["business_type"] for c in candidates]
                options = [f"All of SIC {', '.join(sics)} (industry-wide)"] + cand_names \
                          + ["Something else…"]
                pick = st.selectbox(
                    "This company is a…", options, index=0,
                    help="This SIC covers several kinds of business that protect very "
                         "different things. Picking one gives figures for businesses "
                         "like this one, not the whole SIC.")
                if pick == "Something else…":
                    chosen_type = st.selectbox("Search all business types",
                                               rec.all_types(), index=None,
                                               placeholder="Start typing…")
                elif pick in cand_names:
                    chosen_type = pick
            elif len(candidates) == 1 and candidates[0]["has_sweep_data"]:
                # SIC maps to exactly one type — use its confirmed-cohort view
                # silently; there is nothing to ask the user.
                chosen_type = candidates[0]["business_type"]

            with st.container():
                with st.spinner("Building class & term recommendations…"):
                    if chosen_type:
                        cr = c_type_rec(chosen_type)
                    else:
                        cr = c_class_rec(tuple(sics))
                if chosen_type and cr.get("source") == "sweep":
                    st.caption(f"Showing **{chosen_type}** — based on {cr['total']:,} "
                               f"businesses of this type, classified from their actual "
                               f"filings (not the whole SIC).")
                    if cr.get("terms"):
                        with st.expander("What businesses like this actually protect "
                                         "(in their own words)"):
                            for t in cr["terms"][:10]:
                                st.markdown(f"- {t['text']}  ({t['share']*100:.0f}%)")
                elif chosen_type:
                    st.caption(f"**{chosen_type}** — not enough classified filings for "
                               f"a per-type view yet; showing its industry (SIC) "
                               f"figures instead.")
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
                    if not chosen_type:
                        st.caption(f"Industry = SIC {', '.join(sics)} · "
                                   f"{cr['total']:,} trademarks.")
                    cls_df = pd.DataFrame([{
                        "Keep": c["tier"] != "d",
                        "Band": _chip(c),
                        "Class": c["class"],
                        "What it covers": c.get("class_label") or "",
                        "Official description": c["heading"],
                        "% of industry": c["pct"],
                        "Trademarks": c["trademarks"],
                    } for c in cr["classes"]])
                    edited = st.data_editor(
                        cls_df, hide_index=True, use_container_width=True, key="cls_editor",
                        column_config={"Keep": st.column_config.CheckboxColumn(required=True)},
                        disabled=["Band", "Class", "What it covers",
                                  "Official description", "% of industry", "Trademarks"])
                    kept_class_nums = set(edited[edited["Keep"]]["Class"].tolist())

                    # item 8 — a one-class sector needs saying out loud, or the page
                    # looks broken ("where are the classes to choose?").
                    if len(cr["classes"]) == 1:
                        _only = cr["classes"][0]
                        st.info(f"Businesses like yours register in **one class — "
                                f"Class {_only['class']} ({_only.get('class_label') or _only['heading'][:60]})** — "
                                f"so there's nothing to choose here: it's pre-selected. "
                                f"The decisions for you are the *terms* below (what, "
                                f"specifically, you protect inside that class).")

                    st.subheader("Terms within kept classes")
                    st.caption("Classes are the shelves; terms are what you put on "
                               "them. Your registration only protects the goods and "
                               "services you actually list — so untick anything you "
                               "don't genuinely offer or intend to. Filing wider than "
                               "your real trade can be challenged as bad faith.")
                    kept_ordered = [c for c in cr["classes"] if c["class"] in kept_class_nums]
                    review = st.multiselect(
                        "Review goods/services terms for which classes?",
                        options=[c["class"] for c in kept_ordered],
                        default=[c["class"] for c in kept_ordered if c["tier"] == "a"],
                        format_func=lambda n: f"Class {n} — "
                            + next((c.get("class_label") or c["heading"][:48]
                                    for c in kept_ordered if c["class"] == n), ""),
                        help="Only the classes you pick here load their term lists "
                             "(keeps the page fast). Unpicked kept classes are saved at class level.")
                    selection = []
                    for c in kept_ordered:
                        kept_terms = []
                        if c["class"] in review:
                            # item 7 — pick terms knowing what the class IS: short
                            # label in the header, full official description behind
                            # an expander so the page stays scannable.
                            _short_lbl = c.get("class_label") or ""
                            st.markdown(f"**{_chip(c)} · Class {c['class']}"
                                        f"{' — ' + _short_lbl if _short_lbl else ''}**"
                                        f"  ({c['pct']}%)")
                            with st.expander(f"What Class {c['class']} covers "
                                             f"(official description)"):
                                st.write(c["heading"])
                            with st.spinner(f"Loading class {c['class']} terms…"):
                                # Terms come from the SIC seed. If the user picked a
                                # business type outside this company's SIC ("Something
                                # else…"), look terms up under the TYPE's own SICs.
                                term_sics = tuple(rec.type_sics(chosen_type) or sics) \
                                    if chosen_type else tuple(sics)
                                tr = c_term_rec(term_sics, c["class"])
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

        st.session_state["kept_classes"] = sorted(kept_class_nums) \
            if "kept_class_nums" in dir() else []
        st.session_state["selection"] = selection if "selection" in dir() else []
    else:
        st.caption("No problem — we'll go through classes with you at the "
                   "audit. Your report will still cover everything else.")
        st.session_state["kept_classes"] = []
        st.session_state["selection"] = []

    st.divider()
    # ── Braudit 3-Question Assessment ────────────────────────────────────
    import assessment as asmt

    st.divider()
    st.header("Does your situation need professional help?")
    st.caption("Three honest questions. Nothing here is rigged — every "
               "conclusion is earned by something you tell us, and if yours is "
               "a straightforward case, we'll say so.")

    # (_n_sim was computed at the top of this stage from the cached register
    # check — do NOT re-derive it from risk_res, which only exists in reveal 2)
    q1_idx = st.radio(asmt.Q1["question"],
                      range(len(asmt.Q1["options"])),
                      format_func=lambda i: asmt.Q1["options"][i][0],
                      index=None, key="asmt_q1")
    if q1_idx is not None:
        st.caption(asmt.Q1["options"][q1_idx][2])

    st.markdown(f"**{asmt.Q2['question']}**")
    if _n_sim:
        st.info(f"Our search found **{_n_sim} similar marks** on the register, "
                f"so we've ticked the first one for you — it's a fact of your "
                f"report, not a hypothetical.")
    q2_none = st.checkbox(asmt.Q2["none_option"][0], key="asmt_q2none")
    q2_flags = []
    if not q2_none:
        for i, (label, _pts, _note) in enumerate(asmt.Q2["options"]):
            default = (i == 0 and _n_sim > 0)
            if st.checkbox(label, value=default, key=f"asmt_q2_{i}"):
                q2_flags.append(i)
    else:
        st.caption(asmt.Q2["none_option"][1])

    q3_idx = st.radio(asmt.Q3["question"],
                      range(len(asmt.Q3["options"])),
                      format_func=lambda i: asmt.Q3["options"][i][0],
                      index=None, key="asmt_q3")
    if q3_idx is not None:
        st.caption(asmt.Q3["options"][q3_idx][2])


    st.divider()
    # ── Next step: Brand Audit (item 10) ─────────────────────────────────
    st.divider()
    st.header("How much is it?")
    st.caption("Tell us where you trade — protection is per territory, so the "
               "jurisdictions decide the cost.")

    _JURIS = ["United Kingdom", "European Union", "United States", "Australia",
              "Canada", "New Zealand", "United Arab Emirates", "Switzerland",
              "Norway", "China", "Japan", "India", "Other / not sure"]
    _jc1, _jc2 = st.columns(2)
    with _jc1:
        juris_now = st.multiselect("Where do you trade now?", _JURIS,
                                   default=["United Kingdom"])
    with _jc2:
        juris_plan = st.multiselect("Where do you plan to trade?", _JURIS)

    # NOTE: live per-territory quoting hooks into the website's fee calculator —
    # needs its endpoint/fee table wired here. Until then the audit offer carries
    # the CTA and the team quotes on the call.
    _n_territories = len(set(juris_now + juris_plan)) or 1
    st.caption(f"Protection across **{_n_territories} "
               f"territor{'y' if _n_territories == 1 else 'ies'}** — exact "
               f"application fees depend on territories and classes; we'll "
               f"confirm them in your audit consultation.")



    # Persist the answers under NON-widget keys. Streamlit raises if you
    # assign to a key that a widget owns via key= (asmt_q1/asmt_q3/asmt_q2none
    # are widget keys), so the report reads these mirrors instead.
    st.session_state["ans_q1"] = q1_idx
    st.session_state["ans_q2"] = q2_flags
    st.session_state["ans_q2none"] = q2_none
    st.session_state["ans_q3"] = q3_idx
    st.session_state["ans_juris_now"] = juris_now
    st.session_state["ans_juris_plan"] = juris_plan

    st.divider()
    if q1_idx is None or q3_idx is None:
        st.info("Answer the three questions above and we'll finish your report.")
    if st.button("Get my report", type="primary", use_container_width=True,
                 disabled=(q1_idx is None or q3_idx is None)):
        st.session_state["stage"] = "build2"
        st.rerun()
    st.stop()


# ══════════════════════════════════════════════════════════════════════
# REVEAL 2 — the full tailored report
# ══════════════════════════════════════════════════════════════════════

# Rebuild what input 2 produced: the classes/terms they kept (if they didn't
# skip), so the viability score, the branded sheet and the ledger all reflect
# THEIR choices rather than the sector default.
_selection = st.session_state.get("selection", [])
_kept_classes = st.session_state.get("kept_classes", [])
rec_html = (br.render_recommendations(display_name, sics, _selection)
            if _selection else None)
if _kept_classes:
    st.success(f"Your report is tailored to the "
               f"{len(_kept_classes)} class"
               f"{'' if len(_kept_classes) == 1 else 'es'} you selected: "
               + ", ".join(str(c) for c in _kept_classes) + ".")


# ── Trademark Viability Score (item 4) ───────────────────────────────
st.header("Trademark Viability Score")
st.caption("One number, built from four things we can measure: how alone "
           "your name is on the register, how protectable the wording is in "
           "law, how long you've used it, and how hard the similar marks "
           "push back. The dials show where the work is.")
import viability as vb
_c = (risk_res or {}).get("counts", {})
_sector_terms = []
if 'chosen_type' in dir():
    pass
try:
    _tr = c_type_rec(st.session_state.get("tn_business_type") or "") if st.session_state.get("tn_business_type") else None
    _sector_terms = [t["text"] for t in (_tr or {}).get("terms", [])]
except Exception:
    _sector_terms = []
if _kept_classes and sics:
    try:
        _sector_terms = [t["term"] for _c in _kept_classes[:4]
                         for t in c_term_rec(tuple(sics), _c).get("terms", [])[:10]]
    except Exception:
        _sector_terms = []
if not _sector_terms and sics:
    try:
        _sector_terms = [t["term"] for cl in c_class_rec(tuple(sics)).get("classes", [])[:3]
                         for t in (c_term_rec(tuple(sics), cl["class"]).get("terms", [])[:10])]
    except Exception:
        _sector_terms = []
_years = trading_years if trading_name.strip() else \
         vb.years_since((sector_company or {}).get("incorporated"))
_v = vb.compute(name=display_name,
                n_similar=sum(_c.values()) if _c else 0,
                high=_c.get("High Risk", 0), medium=_c.get("Medium Risk", 0),
                low=_c.get("Low Risk", 0),
                years=_years, sector_terms=_sector_terms)
st.markdown(vb.gauge_html(_v), unsafe_allow_html=True)
if _v["scores"]["distinctiveness"] < 45:
    st.caption("Distinctiveness is the dial to talk about: names built from "
               "everyday trade words are harder to register as words alone — "
               "but logos, styling and evidence of use are all routes we use "
               "every week.")


# ── marks like yours: risk overview (same rules as the Audit Report) ──
risk_res = None
_risk_subject = display_name          # trading name when in TN mode
if da.query_runs_ready():
    st.header("Marks like yours on the register")
    st.caption("We compare your name against live UK register data using the "
               "same rules as our paid Audit Report — status, similarity, "
               "mark type and class overlap. This is what an examiner or an "
               "opposing brand would see.")
    with st.spinner("Checking the register for similar marks…"):
        cand = c_similar(_risk_subject)
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
            cand, brand=_risk_subject, target_classes=tgt,
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
st.caption("The register, filtered to businesses like yours: how many "
           "protect their brand, which classes they use, and who leads. "
           "This is real filing behaviour — not our opinion.")
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
    st.caption("The most protected brands in your space. If the leaders in "
               "your sector hold trademarks, that's the market telling you "
               "what it takes to compete — see their actual marks below.")
    st.dataframe(rep.get("top_companies", []), use_container_width=True, hide_index=True)
    # item 6 — proof, not assertion: show each leader's actual trademarks.
    # Look up by COMPANY NUMBER via SQL, not by name via mark-text search:
    # data_access.company_marks says it plainly — "REST applicant search
    # misses many legal names; the SQL join by company_number doesn't".
    for _tc in (rep.get("top_companies") or [])[:3]:
        _tc_name = _tc.get("name") or ""
        _tc_num = _tc.get("company_number") or ""
        _tc_count = _tc.get("trademarks")
        if not _tc_name:
            continue
        with st.expander(f"View trademarks — {_tc_name}"
                         + (f" ({_tc_count})" if _tc_count else "")):
            _tm = da.company_marks(_tc_num, limit=500) if _tc_num else []
            if not _tm:
                # Some groups file under an applicant record with no company
                # number attached — fall back to the name search.
                _alt = _reg_lookup(_tc_name)
                _tm = [{"mark": (t.get("mark") or {}).get("verbal_element_text"),
                        "status": t.get("status")}
                       for t in (_alt[0]["trademarks"] if _alt else [])]
            if not _tm:
                st.write("_Their marks are filed under a different legal "
                         "entity, so we can't list them here._")
            else:
                st.caption(f"{len(_tm)} marks on the register.")
                st.dataframe(_tm, use_container_width=True, hide_index=True)

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
    st.caption("Your company against your sector's norms: how common "
               "protection is, how much the protected hold, and at what "
               "stage businesses like yours typically file. It answers the "
               "question every founder asks — am I early, on time, or late?")
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


# the answers they gave at input 2
q1_idx = st.session_state.get("ans_q1")
q2_flags = st.session_state.get("ans_q2", [])
q2_none = st.session_state.get("ans_q2none", False)
q3_idx = st.session_state.get("ans_q3")
juris_now = st.session_state.get("ans_juris_now", [])
juris_plan = st.session_state.get("ans_juris_plan", [])
_n_sim = sum((risk_res or {}).get("counts", {}).values()) if risk_res else 0
import assessment as asmt

st.divider()
st.header("What your answers tell us")
if q1_idx is not None and q3_idx is not None:
    _res = asmt.score(q1_idx, q2_flags, q2_none, q3_idx)
    _copy = asmt.result_copy(_res, n_similar=_n_sim)
    st.subheader(_copy["title"])
    st.markdown(_copy["body_md"])
    _b1, _b2 = st.columns(2)
    with _b1:
        st.link_button(_copy["primary"][0], _copy["primary"][1],
                       type="primary", use_container_width=True)
    with _b2:
        st.link_button(_copy["secondary"][0], _copy["secondary"][1],
                       use_container_width=True)


st.subheader("Next step: the Brand Audit")
st.markdown(
    "We don't advise anyone to file an application without a **Brand Audit** "
    "first. The audit expands on this quick report with searches across "
    "**international registers, Companies House, domain registrations, social "
    "media and online shopping channels** — the places oppositions and "
    "disputes actually come from.\n\n"
    "**What you get for £99:**\n\n"
    "- **Brand Audit — £149.** An hour of specialist research across all the "
    "sources above, on your exact name and classes.\n"
    "- **Review & Consultation — £149.** An hour with one of our team, by "
    "phone or Teams, walking through the findings and what they mean for "
    "you.\n\n"
    "That's **£298 of specialist work for £99** — and it gets better:\n\n"
    "- **If you proceed to trademark with us**, the £99 is deducted from "
    "your application fees — so the audit effectively costs you nothing.\n"
    "- **If we advise you *not* to proceed** — because the honest answer is "
    "that this name won't succeed — you can have another audit and "
    "consultation on a different brand, any time within **3 months** of "
    "your consultation.\n\n"
    "Either way, you can't lose the £99: it becomes your application "
    "discount, or your second audit.\n\n"
    "Our application success rate over the past 12 months is **98%**, against "
    "an industry average of about 83% — and that gap is mostly down to the "
    "research done at audit stage.")
_c1, _c2, _c3 = st.columns(3)
with _c1:
    st.link_button("Request Brand Audit — £99",
                   "https://www.thetrademarkhelpline.com/request-brand-audit/",
                   type="primary", use_container_width=True)
with _c2:
    st.link_button("Talk to us — book a call",
                   "https://link.cerebrumai.io/widget/booking/ZArxD6BnggpV7bsSF0ks",
                   use_container_width=True)
with _c3:
    st.link_button("Make an enquiry",
                   "https://www.thetrademarkhelpline.com/make-an-enquiry/",
                   use_container_width=True)

# ── Report ledger: one row per report, for follow-up + Zoho ──────────
import ledger as _led

if "logged_report" not in st.session_state:
    _c_led = (risk_res or {}).get("counts", {})
    _base = st.secrets.get("REPORT_BASE_URL", "") if hasattr(st, "secrets") else ""
    _led.record(
        company_name=(sector_company or {}).get("name") or display_name,
        company_number=(sector_company or {}).get("number"),
        company_status=(sector_company or {}).get("status"),
        incorporated=(sector_company or {}).get("incorporated"),
        sic_codes=sics,
        business_type=chosen_type if "chosen_type" in dir() else None,
        trading_name=trading_name or None,
        trading_years=trading_years or None,
        classes_shown=_kept_classes or None,
        classes_kept=_kept_classes or None,
        terms_kept=[t["term"] for sset in _selection for t in sset.get("terms", [])] or None,
        assessment_band=(_res or {}).get("band") if "_res" in dir() else None,
        viability_master=_v["master"] if "_v" in dir() else None,
        uniqueness=_v["scores"]["uniqueness"] if "_v" in dir() else None,
        distinctiveness=_v["scores"]["distinctiveness"] if "_v" in dir() else None,
        proof_of_use=_v["scores"]["proof_of_use"] if "_v" in dir() else None,
        conflicts=_v["scores"]["conflicts"] if "_v" in dir() else None,
        marks_held=len(marks),
        risk_high=_c_led.get("High Risk", 0),
        risk_medium=_c_led.get("Medium Risk", 0),
        risk_low=_c_led.get("Low Risk", 0),
        risk_total=sum(_c_led.values()) if _c_led else 0,
        report_url=_led.report_url(_base, (sector_company or {}).get("number") or "",
                                   trading_name=trading_name or "",
                                   trading_years=trading_years),
    )
    st.session_state["logged_report"] = True


# ── downloads ────────────────────────────────────────────────────────
st.divider()
st.header("Downloads")
st.caption("Everything above as a branded document — yours to keep, share "
           "with a co-founder, or bring to the audit call.")
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


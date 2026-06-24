# Goal #3 — Industry Trademark Report

A Streamlit dashboard that builds a company + sector trademark report from live TemmyDB, with export.

## Status — ALL LIVE (verified 24 Jun 2026)

Query Runs key is in place and the full chain works against the live registry
(~2.98M trademarks, 484,940 matched companies, 470,631 with SIC codes).

| Capability | Source | Status |
|---|---|---|
| Company lookup + marks held | Temmy API (standard key) | ✅ Live |
| Company SIC code(s) | Query Runs | ✅ Live (Temmy carries SIC) |
| Sector size (trademarks / companies) | Query Runs | ✅ Live |
| Sector "first filed" year | Query Runs | ✅ Live |
| Top 3 companies in sector | Query Runs | ✅ Live |
| Class distribution in sector | Query Runs | ✅ Live |
| Branded export (HTML, print-to-PDF) | local | ✅ Live |
| Direct server-side PDF | wkhtmltopdf/pdfkit | ⏳ optional add-on |

**Two front doors, both live:**
- **Trademark registry (Temmy)** — companies that hold UK marks; SIC comes from Temmy.
- **Companies House (any UK company)** — looks up *any* company, including ones with
  **no trademarks**; SIC comes from the CH API, sector stats from Temmy. Key:
  `COMPANIES_HOUSE_API_KEY` in `temmy-access/secrets.env` (CH app "MOAT Industry Report").

### Worked examples (live data)
- Registry path — `Greggs Plc` → SIC `10710` → **3,076 trademarks / 814 companies**,
  first filed **1876**. See `SAMPLE_report_Greggs.html`.
- Any-company path — `JOINERY LIMITED` (0 trademarks) → CH SIC `16230` → sector
  **355 trademarks / 194 companies**, first filed **1950**. See
  `SAMPLE_report_CompaniesHouse.html`.

## Why Query Runs (not the fixed API)

The fixed API endpoints do per-mark / per-applicant lookups only — they can't
aggregate across the registry by SIC sector, don't expose company SIC codes, and the
`/applicants/search` endpoint is slow on names and errors on some ids. Sector
intelligence is inherently an aggregation job, so it needs read-only SQL via Query Runs
(or direct registry Postgres). This is the same data path the original PhD PoC used.

## Run

```bash
cd "goal3-industry-report"
pip install -r requirements.txt
streamlit run app.py
```

Credentials are read from `../temmy-access/secrets.env` (gitignored). Never paste keys
into chat or commit them.

## Files

- `app.py` — Streamlit UI (company panel live; sector panel pending key).
- `data_access.py` — data layer. API-backed company lookup + Query Runs sector
  aggregation. The exact SQL each panel runs is in `SECTOR_SQL`.

## When the Query Runs key arrives

1. Add `TEMMY_QUERY_RUNS_API_KEY=<key>` to `../temmy-access/secrets.env`.
2. Re-run `streamlit run app.py` — the sector panel lights up.
3. On the first successful Query Run, confirm the response shape against
   `data_access._qr_id()` / `run_sql()` and adjust if Temmy's body/field names differ
   from the documented `/api/v2/query-runs` contract (it's the one untested interface).
4. Wire branded PDF export (pdfkit + wkhtmltopdf) once the sector content is confirmed.

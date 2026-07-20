# Deploy goal3-industry-report (reconciled onto the shared engine)

Run these from **your Terminal** (the sandbox can't write to git on the mounted
drive). Everything is already prepared and verified on disk.

```bash
cd "/Users/macbook/Documents/Claude/Projects/MOAT for Braudit/goal3-industry-report"

# 1. Clear the lock + temp objects the sandbox left behind (harmless, but they
#    block git until removed)
rm -f .git/index.lock
find .git/objects -name 'tmp_obj_*' -delete

# 2. Stage the reconciliation (NOT .DS_Store)
git add app.py recommend.py branded_report.py freesearch nice_classes.py vendor_engine.py

# 3. Commit
git commit -m "Reconcile report onto shared freesearch engine

- recommend.py delegates to vendored freesearch (bands/sic_engine/taxonomy):
  same corpus (Registered/3y/orgs), All/Most/Some/A-few bands, empirical seed
  (instant), inconclusive-SIC routing, business-type view + characteristic terms
- app.py: tier-keyed bands, surfaces inconclusive routing
- branded_report.py: colours/legend derived from bands.py
- vendor_engine.py: sync script; engine vendored so the repo deploys self-contained"

# 4. Push -> Streamlit Community Cloud auto-redeploys from main
git push origin main
```

## Before / after the push

- **Secrets**: no change. Streamlit Cloud reads the 5 keys from the app's
  Settings → Secrets (set back in June); they are NOT in the repo.
- **Dependencies**: `requirements.txt` is unchanged — the vendored engine is
  pure standard library, so nothing new to install on Cloud.
- **Watch**: after the push, open the app on Streamlit Cloud and confirm it
  rebuilds green. Spot-check: a software company (SIC 62012) shows All/Most/Some
  bands; a management-consultancy SIC (70229) shows the "inconclusive → try
  competitor mark / website / description" routing instead of a class list.

## Refreshing later

The engine is **vendored** into `goal3/freesearch/` so the repo is
self-contained. After any change to the parent engine or a seed refresh, re-sync
before committing:

```bash
python vendor_engine.py
```

(One known follow-up, non-blocking: the SIC-level view is mark-level while the
business-type view and leads are company-level — align on a later seed refresh.)

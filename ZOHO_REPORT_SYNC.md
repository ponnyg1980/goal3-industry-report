# Report ledger → Zoho CRM

Every report viewed or created becomes a row in `data/report_ledger.csv`, and
that row becomes (or updates) a Lead. Mapped against the **live** Leads schema
pulled 20 Jul 2026 — 249 fields, checked field by field, not assumed.

## The chain

```
report viewed → ledger.record() → report_ledger.csv → zoho_sync.sync_row()
                                                    → upsertRecords (Leads)
```

The CSV is the durable record. Zoho is a copy. If a CRM call fails nothing is
lost — re-run the sync from the CSV.

## Upsert key: `Company_Number`, not Email

A report view has **no email** — the visitor hasn't given one, and asking
before showing value is what kills the funnel. But it always has a Companies
House number, which is a genuine unique key for a UK company.

So: the report sync upserts on `Company_Number`. When the same visitor later
submits a CTA form *with* an email, the existing Email-keyed flow
(`freesearch/ZOHO_FIELD_MAPPING.md`) updates the same record. Two entry
points, one row.

## Fields that already exist — reused, not duplicated

| Ledger | Zoho field | Type |
|---|---|---|
| `company_name` | `Company` | text |
| `company_number` | `Company_Number` | text |
| `classes_kept` | `Classes` | **multiselectpicklist** |
| `sic_codes` | `SIC` | text |
| company / trading name | `Search_Term` | text |
| — | `Lead_Source` = "Industry Trademark Report" | picklist |

⚠️ **`Classes` is a multiselectpicklist.** Send a list, and every value must
already exist as a picklist option or Zoho rejects the entire record. Check
the option list covers "1".."45" before the first bulk sync.

⚠️ **`Last_Name` is mandatory on Leads.** A bare report view has no person, so
we send the company name as a placeholder; the CTA form overwrites it.

## Fields to create before first sync (10)

| API name | Type | Why |
|---|---|---|
| `Report_ID` | text | ties the CRM row back to the ledger CSV row |
| `Report_URL` | website | the magic link that reopens their report, ready |
| `Viability_Score` | integer | master % — sort and segment by brand strength |
| `Risk_High` | integer | high-risk conflicting marks found |
| `Risk_Medium` | integer | medium-risk conflicting marks found |
| `Risk_Low` | integer | low-risk conflicting marks found |
| `Business_Type` | text | sweep-classified type, e.g. "Fintech platform" |
| `Assessment_Band` | picklist (A/B/C) | 3-question result — the routing signal |
| `Terms_Kept` | textarea | the goods/services terms they actually kept |
| `Trading_Name` | text | when they trade under something other than the company name |

Confirmed absent from the live schema: no existing field contains
"trademark", "viability", "report", "audit", "risk", "business_type",
"tenant" or "assessment" — so these names are free.

## Running a sync

`zoho_sync.sync_row()` **builds** the payload; it does not call Zoho. Writing
to a live CRM should be a deliberate act, never a side effect of someone
loading a page. To sync, hand the payload to `upsertRecords`:

```python
import ledger, zoho_sync
rows    = ledger.read_all()
payload = zoho_sync.sync_all(rows)     # up to 100 records per call
# then: upsertRecords(module='Leads', body={
#     'data': payload['data'],
#     'duplicate_check_fields': payload['duplicate_check_fields']})
```

## What the team gets out of it

Because `Assessment_Band` and `Viability_Score` land in the CRM, the
follow-up sorts itself:

- **Band A + low viability** → strongest audit leads; they told us the name
  matters *and* the data says it's difficult
- **Band C** → do not chase (per the assessment doc, these are the ones we
  deliberately tell "you may not need us") — tag for nurture only
- **High `Risk_High` count** → urgent; a live conflict they don't know about
- **`Report_URL`** → paste straight into the follow-up email; they click and
  their report opens exactly as they left it

## Gap-lead crossover

The 2,621 gap leads in `freesearch/data/leads.csv` (companies missing classes
their sector standard) share `Company_Number` as a key — so the same upsert
merges the two: a company that both ran a report *and* shows a protection gap
becomes one enriched record, not two.

"""Report ledger — one row per report viewed or created.

WHY

Every report someone opens is an intent signal: they typed their company in,
we told them what their sector protects, and they either engaged or left. That
row is the lead. Without it the report is a nice page nobody can follow up.

WHAT IT CAPTURES (Jonathan, 20 Jul: "company name, classes and terms, link to
the report")

  who      — company name + number, trading name if used, business type
  what     — the classes and terms they were shown, and which they KEPT
  score    — viability master + the four dials
  risk     — high/medium/low counts from the register check
  intent   — did they open the assessment, what band, did they click a CTA
  link     — the magic-link URL that reopens THIS report, ready

Deliberately no personal data unless the visitor gives it (name/email arrive
only via the CTA forms downstream). The company is public record; the person
is not, until they choose.

STORAGE

Append-only CSV at data/report_ledger.csv — trivially openable, trivially
importable, no database to run. `to_zoho_payload()` shapes a row for the Zoho
CRM push (see ZOHO_FIELD_MAPPING.md); the CSV stays the durable local record
even if the CRM call fails, so nothing is ever lost to a network blip.
"""
from __future__ import annotations

import csv
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data'
LEDGER = DATA / 'report_ledger.csv'

FIELDS = [
    'report_id', 'timestamp_utc', 'tenant',
    # who
    'company_name', 'company_number', 'company_status', 'incorporated',
    'sic_codes', 'business_type', 'trading_name', 'trading_years',
    # what we showed
    'classes_shown', 'classes_kept', 'terms_kept', 'class_source',
    # scores
    'viability_master', 'uniqueness', 'distinctiveness', 'proof_of_use',
    'conflicts',
    # register check
    'marks_held', 'risk_high', 'risk_medium', 'risk_low', 'risk_total',
    # intent
    'assessment_band', 'assessment_score', 'assessment_flags',
    'cta_clicked', 'juris_now', 'juris_planned',
    # link back
    'report_url',
]


def _csv(v) -> str:
    if v is None:
        return ''
    if isinstance(v, (list, tuple, set)):
        return '; '.join(str(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, separators=(',', ':'))
    return str(v)


def new_report_id() -> str:
    return uuid.uuid4().hex[:12]


def report_url(base_url: str, company_number: str, *,
               trading_name: str = '', trading_years=None) -> str:
    """The magic link that reopens this exact report, pre-loaded."""
    if not company_number:
        return base_url
    url = f"{base_url.rstrip('/')}/?company={company_number}"
    if trading_name:
        from urllib.parse import quote
        url += f"&tn={quote(trading_name)}"
        if trading_years:
            url += f"&tny={trading_years:g}"
    return url


def record(**row) -> dict:
    """Append one report row. Unknown keys are ignored, missing ones blank —
    so a caller can log early (report opened) and log again on engagement
    without either call needing the full picture."""
    DATA.mkdir(parents=True, exist_ok=True)
    row.setdefault('report_id', new_report_id())
    row.setdefault('timestamp_utc',
                   datetime.now(timezone.utc).isoformat(timespec='seconds'))
    row.setdefault('tenant', 'tmh')
    clean = {k: _csv(row.get(k)) for k in FIELDS}
    exists = LEDGER.exists()
    with LEDGER.open('a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerow(clean)
    return clean


def read_all() -> list[dict]:
    if not LEDGER.exists():
        return []
    with LEDGER.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


# ── Zoho ───────────────────────────────────────────────────────────────────

def to_zoho_payload(row: dict) -> dict:
    """Shape a ledger row for Zoho CRM.

    Deliberately mirrors ZOHO_FIELD_MAPPING.md (Leads, upsert on Email) but
    a report view has NO email until the visitor gives one. So:
      - with an email  -> Lead (upsert, dedupe on Email)
      - without        -> a company-level activity record, which the team can
                          still act on ("someone at X Ltd ran their report")
    The module choice is left to the caller/Flow; this returns both shapes.
    """
    classes = row.get('classes_kept') or row.get('classes_shown') or ''
    common = {
        'Company': row.get('company_name'),
        'Company_Number': row.get('company_number'),
        'Business_Type': row.get('business_type'),
        'Trading_Name': row.get('trading_name'),
        'Classes': classes,
        'Terms_Kept': row.get('terms_kept'),
        'Viability_Score': row.get('viability_master'),
        'Risk_High': row.get('risk_high'),
        'Risk_Medium': row.get('risk_medium'),
        'Risk_Low': row.get('risk_low'),
        'Assessment_Band': row.get('assessment_band'),
        'Report_URL': row.get('report_url'),
        'Report_ID': row.get('report_id'),
        'Lead_Source': 'Industry Trademark Report',
        'Tenant': row.get('tenant'),
    }
    return {'has_email': False, 'fields': common}

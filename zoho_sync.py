"""Report ledger → Zoho CRM.

Mapped against the LIVE Leads schema (249 fields, pulled 20 Jul 2026) — not
guessed. Existing fields are reused; only genuinely new concepts get new
fields (see ZOHO_REPORT_SYNC.md for the create-these list).

Reused (already in Leads):
    Company               <- company_name
    Company_Number        <- company_number
    Classes               <- classes_kept   (multiselectpicklist!)
    SIC                   <- sic_codes
    Search_Term           <- the name the report ran on
    Industry / Website / Description as available

New (must be created before first sync):
    Viability_Score, Report_URL, Report_ID, Risk_High/Medium/Low,
    Business_Type, Assessment_Band, Terms_Kept, Trading_Name

WHY UPSERT ON COMPANY_NUMBER, NOT EMAIL
A report view has no email — the visitor hasn't given one. But it always has
a Companies House number, which is a true unique key for a UK company. So the
report sync upserts on Company_Number, creating a "company ran their report"
lead the team can act on. If the visitor later submits a CTA form WITH an
email, the normal Email-keyed flow (ZOHO_FIELD_MAPPING.md) updates the same
record. Two keys, one row, no duplicates.

SAFETY
`sync_row()` builds and returns the payload — it does NOT call Zoho. The
caller (or the Claude session with the Zoho MCP) performs the upsert, so
nothing writes to the CRM implicitly from a page view. Writing to a live CRM
is a side effect that should always be a deliberate act.
"""
from __future__ import annotations

MODULE = 'Leads'
DUPLICATE_CHECK_FIELDS = ['Company_Number']

# Fields that exist today (verified against the live schema).
EXISTING = {
    'company_name': 'Company',
    'company_number': 'Company_Number',
    'sic_codes': 'SIC',
}

# Fields to create — api_name -> (data type, why)
FIELDS_TO_CREATE = {
    'Report_ID': ('text', 'ties the CRM row to the ledger CSV row'),
    'Report_URL': ('website', 'magic link that reopens their report, ready'),
    'Viability_Score': ('integer', 'master % — sort/segment by brand strength'),
    'Risk_High': ('integer', 'high-risk conflicting marks found'),
    'Risk_Medium': ('integer', 'medium-risk conflicting marks found'),
    'Risk_Low': ('integer', 'low-risk conflicting marks found'),
    'Business_Type': ('text', 'the sweep-classified type, e.g. Fintech platform'),
    'Assessment_Band': ('picklist A/B/C', '3-question result — the routing signal'),
    'Terms_Kept': ('textarea', 'the goods/services terms they actually kept'),
    'Trading_Name': ('text', 'when they trade under something else'),
}


def _int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def sync_row(row: dict, *, lead_source: str = 'Industry Trademark Report') -> dict:
    """Ledger row -> Zoho upsert payload. Does not call Zoho."""
    classes = [c.strip() for c in str(row.get('classes_kept')
                                      or row.get('classes_shown') or '').split(';')
               if c.strip()]
    record = {
        # existing fields
        'Company': row.get('company_name') or '',
        'Company_Number': row.get('company_number') or '',
        'SIC': row.get('sic_codes') or '',
        'Search_Term': row.get('trading_name') or row.get('company_name') or '',
        'Lead_Source': lead_source,
        # Classes is a multiselectpicklist — send a list, and only values that
        # exist as options, or Zoho rejects the whole record.
        'Classes': classes,
        # new fields (create these first — see FIELDS_TO_CREATE)
        'Report_ID': row.get('report_id') or '',
        'Report_URL': row.get('report_url') or '',
        'Viability_Score': _int(row.get('viability_master')),
        'Risk_High': _int(row.get('risk_high')),
        'Risk_Medium': _int(row.get('risk_medium')),
        'Risk_Low': _int(row.get('risk_low')),
        'Business_Type': row.get('business_type') or '',
        'Assessment_Band': row.get('assessment_band') or '',
        'Terms_Kept': row.get('terms_kept') or '',
        'Trading_Name': row.get('trading_name') or '',
    }
    # Leads requires Last_Name. No person yet on a bare report view, so use the
    # company as the placeholder — the CTA form overwrites it with the real one.
    record.setdefault('Last_Name', row.get('company_name') or 'Report visitor')
    return {
        'module': MODULE,
        'duplicate_check_fields': DUPLICATE_CHECK_FIELDS,
        'data': [{k: v for k, v in record.items() if v not in ('', [], None)}],
    }


def sync_all(rows: list[dict]) -> dict:
    """Batch payload for a whole ledger (Zoho upsert takes up to 100/call)."""
    data = []
    for r in rows:
        data.extend(sync_row(r)['data'])
    return {'module': MODULE, 'duplicate_check_fields': DUPLICATE_CHECK_FIELDS,
            'data': data[:100]}

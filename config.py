"""
Unified secret loader — works in three environments, in priority order:

  1. Environment variables           (CI / container overrides)
  2. st.secrets                       (Streamlit Community Cloud secret store)
  3. ../temmy-access/secrets.env      (local dev; gitignored, never deployed)

So the SAME code runs locally and on Streamlit Cloud with no edits — on cloud
you paste the keys into the app's Secrets panel; locally they come from
secrets.env. No secret is ever committed to the repo.
"""
from __future__ import annotations

import os

# local dev fallback file (one level up; absent on cloud)
_HERE = os.path.dirname(os.path.abspath(__file__))
_SECRETS_ENV = os.path.normpath(os.path.join(_HERE, "..", "temmy-access", "secrets.env"))

_FILE_CACHE: dict | None = None


def _from_file(key: str) -> str:
    global _FILE_CACHE
    if _FILE_CACHE is None:
        _FILE_CACHE = {}
        if os.path.exists(_SECRETS_ENV):
            for line in open(_SECRETS_ENV):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    _FILE_CACHE[k.strip()] = v.strip().strip('"').strip("'")
    return _FILE_CACHE.get(key, "")


def _from_st(key: str) -> str:
    try:
        import streamlit as st
        # st.secrets raises if no secrets file/config exists
        return str(st.secrets[key]) if key in st.secrets else ""
    except Exception:
        return ""


def get_secret(key: str, default: str = "") -> str:
    return os.environ.get(key) or _from_st(key) or _from_file(key) or default

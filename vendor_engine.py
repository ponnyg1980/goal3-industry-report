"""Vendor the shared engine into goal3 so it deploys as a self-contained repo.

WHY

goal3-industry-report is its own GitHub repo and deploys to Streamlit Cloud on
its own. The shared `freesearch` engine lives in the parent project, which Cloud
never sees. So we copy the modules goal3 actually uses into goal3/freesearch/.

Only the deterministic, read-only pieces are vendored (bands, sic_engine,
sic_seed, taxonomy, nice_labels + the JSON seeds + nice_classes headings). The
heavy live-search __init__ is deliberately replaced with a light one so
importing the package doesn't pull in the Temmy search stack.

This is a vendored COPY, so it can drift. Re-run after any change to the engine
or a seed refresh:

    python vendor_engine.py           # from goal3-industry-report/
"""
from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'freesearch'
DEPLOY = HERE.parent / 'deploy-v2-hotfix'
DST = HERE / 'freesearch'

MODULES = ['bands.py', 'sic_engine.py', 'sic_seed.py', 'taxonomy.py',
           'nice_labels.py']
DATA = ['sic_seed.json', 'type_seed.json']

LIGHT_INIT = '''"""Vendored subset of the Braudit engine (see vendor_engine.py).

Only the deterministic class/term modules are here — NOT the live-search stack,
so importing this package is cheap and has no Temmy dependency.
"""
'''


def main() -> None:
    (DST / 'data').mkdir(parents=True, exist_ok=True)
    for m in MODULES:
        shutil.copy2(SRC / m, DST / m)
    (DST / '__init__.py').write_text(LIGHT_INIT)
    for d in DATA:
        src = SRC / 'data' / d
        if src.exists():
            shutil.copy2(src, DST / 'data' / d)
    # NICE_HEADINGS (full official class headings) — used for report headings
    nc = DEPLOY / 'nice_classes.py'
    if nc.exists():
        shutil.copy2(nc, HERE / 'nice_classes.py')
    print(f'vendored {len(MODULES)} modules + {len(DATA)} seeds into {DST}')
    print(f'copied nice_classes.py -> {HERE / "nice_classes.py"}')


if __name__ == '__main__':
    main()

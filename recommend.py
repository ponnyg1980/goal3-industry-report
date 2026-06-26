"""
Goal #1 — Classes & Terms Recommendations by SIC code.

For a company's SIC code(s) (union), recommend the Nice classes and the
goods/services terms commonly used in that industry, each banded by how
frequently it appears:

    Always   (Black)  — most common
    Often    (Green)
    Sometimes(Amber)
    Rarely   (Red)    — long tail

Classes are banded by % of the sector's trademarks that include the class.
Terms are split from the free-text goods/services descriptions (';'-delimited),
normalised, and banded by % of that class's trademarks that use the term.

All live via Temmy Query Runs.
"""
from __future__ import annotations

from data_access import run_sql, run_scalar, _sic_pred, _safe_sic, query_runs_ready  # noqa

# ── Nice classification standard class headings (abbreviated) ────────
NICE_HEADINGS = {
    1: "Chemicals for industry, science & agriculture",
    2: "Paints, varnishes, colorants",
    3: "Cosmetics & cleaning preparations",
    4: "Industrial oils, greases, fuels & lighting",
    5: "Pharmaceuticals & medical/veterinary preparations",
    6: "Common metals & goods of metal",
    7: "Machines & machine tools; motors",
    8: "Hand tools & implements",
    9: "Computers, software & scientific/electrical apparatus",
    10: "Medical, surgical & dental apparatus",
    11: "Lighting, heating, cooking, refrigerating apparatus",
    12: "Vehicles & apparatus for locomotion",
    13: "Firearms, ammunition, explosives, fireworks",
    14: "Precious metals, jewellery, horological instruments",
    15: "Musical instruments",
    16: "Paper, stationery, printed matter",
    17: "Rubber, plastics, insulating materials",
    18: "Leather goods, luggage, bags, umbrellas",
    19: "Non-metallic building materials",
    20: "Furniture, mirrors, picture frames",
    21: "Household & kitchen utensils, glassware",
    22: "Ropes, nets, tents, sacks; raw fibrous materials",
    23: "Yarns & threads for textile use",
    24: "Textiles & textile substitutes; household linen",
    25: "Clothing, footwear, headgear",
    26: "Lace, ribbons, buttons, haberdashery",
    27: "Carpets, rugs, mats, wall hangings",
    28: "Games, toys, sporting goods",
    29: "Meat, fish, dairy, prepared foods",
    30: "Coffee, tea, bread, cereals, confectionery, sauces",
    31: "Raw agricultural & horticultural products; live animals",
    32: "Beers, soft drinks, juices, mineral waters",
    33: "Alcoholic beverages (except beers)",
    34: "Tobacco & smokers' articles",
    35: "Advertising, business management, retail services",
    36: "Insurance, financial & real-estate services",
    37: "Construction, installation & repair services",
    38: "Telecommunications",
    39: "Transport, packaging & storage; travel arrangement",
    40: "Treatment of materials; manufacturing services",
    41: "Education, training, entertainment, sport & culture",
    42: "Scientific & technological services; software design",
    43: "Food & drink services; temporary accommodation",
    44: "Medical, veterinary, hygiene & agricultural services",
    45: "Legal & security services; personal/social services",
}

# ── Banding (fixed % of the industry; tunable) ───────────────────────
# class bands = % of the sector's trademarks that include the class
CLASS_BANDS = [(25, "Always", "#1D1D1B"),   # Black
               (15, "Often", "#2E7D32"),     # Green
               (5,  "Sometimes", "#E69500"), # Amber
               (0,  "Rarely", "#C0392B")]     # Red
# term bands = % of the class's trademarks that use the term
TERM_BANDS = [(20, "Always", "#1D1D1B"),
              (10, "Often", "#2E7D32"),
              (3,  "Sometimes", "#E69500"),
              (0,  "Rarely", "#C0392B")]


def _band(pct, bands):
    for threshold, label, colour in bands:
        if pct is not None and pct >= threshold:
            return label, colour
    return bands[-1][1], bands[-1][2]


def _sector_total(pred) -> int:
    row = run_scalar(
        "SELECT count(distinct at.trademark_id) n "
        "FROM companies c JOIN applicants a ON a.company_id=c.id "
        "JOIN applicant_trademarks at ON at.applicant_id=a.id AND at.active "
        f"WHERE {pred}")
    return row.get("n", 0) or 0


def class_recommendations(sics) -> dict:
    """Per Nice class: trademark count, % of sector, band + colour."""
    pred = _sic_pred(sics)
    total = _sector_total(pred)
    if not total:
        return {"total": 0, "classes": []}
    rows = run_sql(
        "SELECT nc.number cls, count(distinct nct.trademark_id) n "
        "FROM companies c JOIN applicants a ON a.company_id=c.id "
        "JOIN applicant_trademarks at ON at.applicant_id=a.id AND at.active "
        "JOIN nice_class_trademarks nct ON nct.trademark_id=at.trademark_id AND nct.active "
        "JOIN nice_classes nc ON nc.id=nct.nice_class_id "
        f"WHERE {pred} GROUP BY nc.number ORDER BY 2 DESC")
    out = []
    for r in rows:
        cls = r["cls"]
        pct = round(r["n"] / total * 100, 1)
        label, colour = _band(pct, CLASS_BANDS)
        out.append({"class": cls, "heading": NICE_HEADINGS.get(cls, ""),
                    "trademarks": r["n"], "pct": pct,
                    "band": label, "colour": colour})
    return {"total": total, "classes": out}


def term_recommendations(sics, cls: int, limit: int = 25) -> dict:
    """Top goods/services terms within one class for the industry, banded."""
    pred = _sic_pred(sics)
    cls = int(cls)
    class_total = run_scalar(
        "SELECT count(distinct nct.trademark_id) n "
        "FROM companies c JOIN applicants a ON a.company_id=c.id "
        "JOIN applicant_trademarks at ON at.applicant_id=a.id AND at.active "
        "JOIN nice_class_trademarks nct ON nct.trademark_id=at.trademark_id AND nct.active "
        "JOIN nice_classes nc ON nc.id=nct.nice_class_id "
        f"WHERE {pred} AND nc.number={cls}").get("n", 0) or 0
    if not class_total:
        return {"class_total": 0, "terms": []}
    rows = run_sql(
        "SELECT lower(btrim(term)) t, count(distinct nct.trademark_id) n "
        "FROM companies c JOIN applicants a ON a.company_id=c.id "
        "JOIN applicant_trademarks at ON at.applicant_id=a.id AND at.active "
        "JOIN nice_class_trademarks nct ON nct.trademark_id=at.trademark_id AND nct.active "
        "JOIN nice_classes nc ON nc.id=nct.nice_class_id "
        "CROSS JOIN LATERAL unnest(string_to_array(nct.goods_services_description, ';')) term "
        f"WHERE {pred} AND nc.number={cls} AND length(btrim(term)) BETWEEN 3 AND 80 "
        f"GROUP BY 1 ORDER BY 2 DESC LIMIT {int(limit)}")
    out = []
    for r in rows:
        pct = round(r["n"] / class_total * 100, 1)
        label, colour = _band(pct, TERM_BANDS)
        out.append({"term": r["t"], "trademarks": r["n"], "pct": pct,
                    "band": label, "colour": colour})
    return {"class_total": class_total, "terms": out}

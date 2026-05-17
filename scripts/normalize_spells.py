#!/usr/bin/env python3
"""
Transforms raw spells.json (from concept1 importer) into normalized format.

Deterministic transformations:
  - deduplication + lore grouping (each spell appears once, lore is an array)
  - slug-based ID generation
  - range normalization
  - duration normalization
  - references extraction from effect text
  - rawText preserved

NOT done here (requires LLM enrichment later):
  - effects[] — semantic parsing of effect descriptions
  - target deep normalization — too many variants

Usage:
  python3 scripts/normalize_spells.py <input.json> <output.json>

Example:
  python3 scripts/normalize_spells.py \
    data/output/winds_of_magic/spells.json \
    data/output/winds_of_magic/spells_normalized.json
"""

import json
import re
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# Page ranges per book → content type → lore
# Source: hardcoded page ranges from concept1 book classes
# ---------------------------------------------------------------------------

SPELL_PAGE_MAP: dict[str, list[dict]] = {
    "winds_of_magic": [
        {"pages": list(range(26, 28)),   "lores": None},          # Arcane (all lores)
        {"pages": list(range(62, 66)),   "lores": ["BEASTS"]},
        {"pages": list(range(74, 78)),   "lores": ["DEATH"]},
        {"pages": list(range(86, 90)),   "lores": ["FIRE"]},
        {"pages": list(range(98, 102)),  "lores": ["HEAVENS"]},
        {"pages": list(range(110, 114)), "lores": ["METAL"]},
        {"pages": list(range(122, 126)), "lores": ["LIFE"]},
        {"pages": list(range(134, 138)), "lores": ["LIGHT"]},
        {"pages": list(range(146, 150)), "lores": ["SHADOWS"]},
    ],
    "core_rulebook": [
        {"pages": list(range(240, 258)), "lores": None},
    ],
    "enemy_in_shadows_companion": [
        {"pages": None, "lores": None},  # unknown — update when parsed
    ],
}


def resolve_source_pages(book: str, lores: list[str] | None) -> list[int]:
    """
    Returns page range(s) for a spell given its book and lore list.
    Arcane spells (lores=None or multi-lore) get the arcane section pages.
    Single-lore spells get their lore's section pages.
    """
    mapping = SPELL_PAGE_MAP.get(book)
    if not mapping:
        return []

    pages: set[int] = set()

    if not lores:
        # No lore → arcane section
        for entry in mapping:
            if entry["lores"] is None and entry["pages"]:
                pages.update(entry["pages"])
    else:
        for lore in lores:
            for entry in mapping:
                if entry["lores"] and lore in entry["lores"] and entry["pages"]:
                    pages.update(entry["pages"])

        # If still empty (e.g. multi-lore arcane) fall back to arcane section
        if not pages:
            for entry in mapping:
                if entry["lores"] is None and entry["pages"]:
                    pages.update(entry["pages"])

    return sorted(pages)


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def name_to_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"spell_{slug}"


# ---------------------------------------------------------------------------
# Range normalization
# ---------------------------------------------------------------------------

RANGE_FORMULA_PATTERNS = [
    (r"willpower\s+bonus\s+yards?", "WP_BONUS_YARDS"),
    (r"wp\s+bonus\s+yards?",        "WP_BONUS_YARDS"),
    (r"initiative\s+bonus\s+yards?","I_BONUS_YARDS"),
    (r"strength\s+bonus\s+yards?",  "S_BONUS_YARDS"),
    (r"toughness\s+bonus\s+yards?", "T_BONUS_YARDS"),
]

def normalize_range(raw: str) -> dict:
    r = raw.strip()
    lower = r.lower()

    if lower in ("touch",):
        return {"type": "touch"}

    if lower in ("yourself", "self", "you"):
        return {"type": "self"}

    if lower == "special":
        return {"type": "special", "raw": r}

    if lower == "unlimited":
        return {"type": "unlimited"}

    if lower == "sight":
        return {"type": "sight"}

    for pattern, constant in RANGE_FORMULA_PATTERNS:
        if re.search(pattern, lower):
            return {"type": "formula", "value": constant}

    # "X yards" or "X yard"
    m = re.match(r"^(\d+)\s+yards?$", r, re.IGNORECASE)
    if m:
        return {"type": "fixed_yards", "value": int(m.group(1))}

    # "up to X yards"
    m = re.match(r"^up\s+to\s+(\d+)\s+yards?$", r, re.IGNORECASE)
    if m:
        return {"type": "fixed_yards", "value": int(m.group(1)), "qualifier": "up_to"}

    return {"type": "raw", "raw": r}


# ---------------------------------------------------------------------------
# Target normalization (best effort — complex cases fall back to raw)
# ---------------------------------------------------------------------------

def normalize_target(raw: str) -> dict:
    r = raw.strip()
    lower = r.lower()

    if lower in ("yourself", "self", "you", "the caster"):
        return {"type": "self"}

    if lower == "special":
        return {"type": "special", "raw": r}

    # AoE patterns: "AoE X Yards", "AoE (X yard radius)"
    m = re.search(r"aoe\s*[:(]?\s*(\d+)\s*yards?\s*radius", lower)
    if m:
        return {"type": "aoe", "radius_yards": int(m.group(1))}

    m = re.match(r"aoe\s+(\d+)\s+yards?", lower)
    if m:
        return {"type": "aoe", "radius_yards": int(m.group(1))}

    # "X Targets", "Up to X targets"
    m = re.match(r"(?:up\s+to\s+)?(\d+)\s+targets?", lower)
    if m:
        return {"type": "creature", "count": int(m.group(1))}

    # "Any X <creature>" or "X <creature>"
    m = re.match(r"(?:any\s+)?(\d+)\s+(.+)", r, re.IGNORECASE)
    if m:
        count = int(m.group(1))
        entity = m.group(2).strip().rstrip("s").title()  # crude singularize
        return {"type": "creature", "count": count, "entity": entity}

    return {"type": "raw", "raw": r}


# ---------------------------------------------------------------------------
# Duration normalization
# ---------------------------------------------------------------------------

STAT_NAMES = {
    "willpower bonus": "WP_BONUS",
    "willpower":       "WP_BONUS",
    "wp bonus":        "WP_BONUS",
    "initiative bonus":"I_BONUS",
    "initiative":      "I_BONUS",
    "intelligence bonus": "INT_BONUS",
    "intelligence":    "INT_BONUS",
    "strength bonus":  "S_BONUS",
    "toughness bonus": "T_BONUS",
    "toughness":       "T_BONUS",
    "fellowship bonus":"FEL_BONUS",
    "fellowship":      "FEL_BONUS",
    "agility bonus":   "AG_BONUS",
}

def normalize_duration(raw: str) -> str:
    d = raw.strip().lower()

    if d == "instant":
        return "instant"
    if "concentration" in d:
        return "concentration"
    if "sustained" in d:
        return "sustained"
    if "permanent" in d:
        return "permanent"
    if "until dispelled" in d:
        return "until_dispelled"
    if "until sunrise" in d or "next sunrise" in d:
        return "until_sunrise"

    # "<Stat> Bonus rounds/minutes/hours/days"
    for stat_phrase, constant in STAT_NAMES.items():
        for unit in ("round", "minute", "hour", "day", "week", "month"):
            if re.search(rf"{re.escape(stat_phrase)}\s+{unit}s?", d):
                return f"{constant}_{unit.upper()}S"

    # "X rounds" / "X minutes" / "X hours"
    m = re.match(r"(\d+)\s+(round|minute|hour|day)s?", d)
    if m:
        return f"{m.group(1)}_{m.group(2).upper()}S"

    return raw.strip()


# ---------------------------------------------------------------------------
# References extraction
# ---------------------------------------------------------------------------

def extract_references(effect_text: str) -> list:
    refs = []

    # Pattern: (**BOOK**, page N) or (**BOOK**, p. N)
    pattern = re.compile(
        r"\(\*\*([^*]+)\*\*,\s*p(?:age|\.?)?\s*(\d+)\)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(effect_text):
        refs.append({
            "book": m.group(1).strip(),
            "page": int(m.group(2)),
        })

    return refs


# ---------------------------------------------------------------------------
# Base name extraction (strips lore suffix)
# ---------------------------------------------------------------------------

def get_base_name(name: str) -> str:
    """
    "Belligerence of the Bloodmarsh (Beasts)" -> "Belligerence of the Bloodmarsh"
    "Belligerence of the Bloodmarsh"          -> "Belligerence of the Bloodmarsh"
    """
    return re.sub(r"\s*\([^)]+\)\s*$", "", name).strip()


# ---------------------------------------------------------------------------
# Main transform
# ---------------------------------------------------------------------------

def transform(spells: list, book: str = "") -> list:
    # Group by base name preserving order
    seen_order = []
    grouped: dict[str, list] = defaultdict(list)

    for spell in spells:
        base = get_base_name(spell["name"])
        if base not in grouped:
            seen_order.append(base)
        grouped[base].append(spell)

    result = []
    for base_name in seen_order:
        variants = grouped[base_name]

        lores = sorted(set(v["lore"] for v in variants if v["lore"]))
        # Use the variant without a lore suffix as source (or first if all have lore)
        source = next(
            (v for v in variants if get_base_name(v["name"]) == v["name"]),
            variants[0],
        )

        effect_text = (source.get("effect") or "").strip()
        refs = extract_references(effect_text)
        # Arcane spells have a variant with lore=None in raw data (duplicated to all lores by importer)
        # → use arcane section pages only, not every lore's pages
        is_arcane = any(v.get("lore") is None for v in variants)
        source_pages = resolve_source_pages(book, None if is_arcane else (lores or None))

        result.append({
            "id": name_to_id(base_name),
            "name": base_name,
            "type": "spell",
            "source": book or None,
            "sourcePages": source_pages,
            "lore": lores if lores else None,
            "castingNumber": source["castingNumber"],
            "range": normalize_range(source.get("range") or ""),
            "target": normalize_target(source.get("target") or ""),
            "duration": normalize_duration(source.get("duration") or ""),
            # effects left empty — to be filled by LLM enrichment pipeline
            "effects": [],
            "references": refs,
            "rawText": effect_text,
        })

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input.json> <output.json> [book_name]")
        print(f"  book_name: winds_of_magic | core_rulebook | enemy_in_shadows_companion ...")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]
    # Derive book name from parent folder if not explicitly provided
    book = sys.argv[3] if len(sys.argv) > 3 else input_path.split("/")[-2]

    with open(input_path, encoding="utf-8") as f:
        spells = json.load(f)

    print(f"Loaded {len(spells)} spell entries (with lore duplicates) [book: {book}]")

    normalized = transform(spells, book=book)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)

    print(f"Written {len(normalized)} unique spells → {output_path}")


if __name__ == "__main__":
    main()

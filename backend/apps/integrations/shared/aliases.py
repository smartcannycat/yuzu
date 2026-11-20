"""Shared vehicle make/model alias tables, transliteration, and noise-token helpers."""

from __future__ import annotations

import re

CYRILLIC_TRANSLIT: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

MAKE_ALIASES: dict[str, tuple[str, ...]] = {
    "toyota": ("toyota", "тойота"),
    "honda": ("honda", "хонда"),
    "nissan": ("nissan", "ниссан"),
    "mazda": ("mazda", "мазда"),
    "subaru": ("subaru", "субару"),
    "suzuki": ("suzuki", "сузуки"),
    "mitsubishi": ("mitsubishi", "митсубиси", "мицубиси"),
    "daihatsu": ("daihatsu", "дайхатсу"),
    "lexus": ("lexus", "лексус"),
    "mercedes": ("mercedes", "mercedesbenz", "мерседес", "мерседесбенц"),
    "mercedesbenz": ("mercedesbenz", "mercedes", "мерседес", "мерседесбенц"),
    "bmw": ("bmw", "бмв"),
    "audi": ("audi", "ауди"),
    "volkswagen": ("volkswagen", "vw", "фольксваген"),
    "mini": ("mini", "мини"),
    "hyundai": ("hyundai", "хендай", "хундай", "хендэ"),
    "kia": ("kia", "киа"),
    "volvo": ("volvo", "вольво"),
    "porsche": ("porsche", "порше"),
    "landrover": ("landrover", "лендровер"),
    "ford": ("ford", "форд"),
    "chevrolet": ("chevrolet", "шевроле"),
    "geely": ("geely", "джили"),
    "chery": ("chery", "чери"),
    "haval": ("haval", "хавал", "хавейл"),
}

CANONICAL_BRAND_SLUGS: dict[str, str] = {
    "mercedes": "mercedes-benz",
    "мерседес": "mercedes-benz",
    "мерседес бенц": "mercedes-benz",
    "мерседес-бенц": "mercedes-benz",
    "vw": "volkswagen",
    "фольксваген": "volkswagen",
    "бмв": "bmw",
    "bmv": "bmw",
    "мини": "mini",
}

SISTER_MAKES: dict[str, frozenset[str]] = {
    "toyota": frozenset({"toyota", "lexus", "daihatsu"}),
    "lexus": frozenset({"lexus", "toyota"}),
    "daihatsu": frozenset({"daihatsu", "toyota"}),
    "nissan": frozenset({"nissan", "infiniti"}),
    "infiniti": frozenset({"infiniti", "nissan"}),
    "honda": frozenset({"honda", "acura"}),
    "acura": frozenset({"acura", "honda"}),
    "hyundai": frozenset({"hyundai", "kia", "genesis"}),
    "kia": frozenset({"kia", "hyundai", "genesis"}),
    "genesis": frozenset({"genesis", "hyundai", "kia"}),
}

MODEL_ALIASES: dict[str, tuple[str, ...]] = {
    "freed": ("freed", "фрид"),
    "freedspike": ("freedspike", "freed", "фридспайк", "фрид"),
    "fit": ("fit", "фит"),
    "vezel": ("vezel", "везел"),
    "corolla": ("corolla", "королла"),
    "corollafielder": ("corollafielder", "fielder", "филдер", "короллафилдер"),
    "corollatouring": ("corollatouring", "короллатуринг"),
    "prius": ("prius", "приус"),
    "priusalpha": ("priusalpha", "приусальфа"),
    "aqua": ("aqua", "аква"),
    "vitz": ("vitz", "витц"),
    "yaris": ("yaris", "ярис"),
    "yariscross": ("yariscross", "ярискросс"),
    "tank": ("tank", "танк"),
    "roomy": ("roomy", "руми"),
    "raize": ("raize", "райз"),
    "rocky": ("rocky", "рокки"),
    "rush": ("rush", "раш"),
    "probox": ("probox", "пробокс"),
    "succeed": ("succeed", "саксид"),
    "stepwgn": ("stepwgn", "степвагон", "степвагн"),
    "note": ("note", "ноут", "нот"),
    "roox": ("roox", "рукс"),
    "serena": ("serena", "серена"),
    "xtrail": ("xtrail", "икстрейл"),
    "rav4": ("rav4", "рав4"),
    "harrier": ("harrier", "харриер"),
    "alphard": ("alphard", "альфард"),
    "vellfire": ("vellfire", "веллфайр"),
    "voxy": ("voxy", "вокси"),
    "noah": ("noah", "ноах"),
    "camry": ("camry", "камри"),
    "crown": ("crown", "краун"),
    "wish": ("wish", "виш"),
    "estima": ("estima", "эстима"),
    "chr": ("chr", "схр"),
    "landcruiser": ("landcruiser", "лендкрузер", "крузер"),
    "landcruiserprado": ("landcruiserprado", "prado", "прадо"),
    "sienta": ("sienta", "сиента"),
    "insight": ("insight", "инсайт"),
    "shuttle": ("shuttle", "шатл"),
    "odyssey": ("odyssey", "одиссей"),
    "civic": ("civic", "цивик"),
    "nbox": ("nbox", "нбокс"),
    "nwgn": ("nwgn", "нвгн"),
    "impreza": ("impreza", "импреза"),
    "levorg": ("levorg", "леворг"),
    "forester": ("forester", "форестер"),
    "xv": ("xv", "хв"),
    "legacy": ("legacy", "легаси"),
    "outback": ("outback", "аутбек"),
    "delica": ("delica", "делика"),
    "delicad5": ("delicad5", "delica", "деликад5", "делика"),
    "outlander": ("outlander", "аутлендер"),
    "eclipsecross": ("eclipsecross", "эклипскросс"),
    "demio": ("demio", "демио"),
    "axela": ("axela", "аксела"),
    "cx5": ("cx5", "сх5"),
    "swift": ("swift", "свифт"),
    "jimny": ("jimny", "джимни"),
    "solio": ("solio", "солио"),
    "hustler": ("hustler", "хастлер"),
    "spacia": ("spacia", "спейсия"),
    "wagonr": ("wagonr", "вагонр"),
    "tanto": ("tanto", "танто"),
}

COMPOUND_ALIAS_PATTERNS: dict[str, str] = {
    "mercedesbenz": r"mercedes[\s-]*benz",
    "мерседесбенц": r"мерседес[\s-]*бенц",
    "landrover": r"land[\s-]*rover",
    "лендровер": r"ленд[\s-]*ровер",
}

MAKE_CONFLICT_PATTERNS: dict[str, re.Pattern[str]] = {
    make_name: re.compile(
        r"(?<![a-zа-я0-9])(?:"
        + "|".join(COMPOUND_ALIAS_PATTERNS.get(v, re.escape(v)) for v in variants)
        + r")(?![a-zа-я0-9])",
        re.I,
    )
    for make_name, variants in MAKE_ALIASES.items()
}

TRIM_NOISE_WORDS = frozenset(
    {"hybrid", "hv", "e-power", "epower", "4wd", "2wd", "turbo", "wxb", "w×b"}
)

_FARPOST_EXTRA_TRIM_TOKENS = (
    "phev",
    "phv",
    "e:hev",
    "awd",
    "custom",
    "crosstar",
    "spada",
    "g4",
    "modulo",
    "nismo",
    r"gr\s*sport",
)

FARPOST_MODEL_TRIM_RE = re.compile(
    r"\b(?:"
    + "|".join(
        [
            *(re.escape(tok) for tok in sorted(TRIM_NOISE_WORDS - {"turbo", "wxb", "w×b"})),
            *_FARPOST_EXTRA_TRIM_TOKENS,
        ]
    )
    + r")\b",
    re.I,
)


def transliterate_cyrillic(value: str) -> str:
    """Transliterate Cyrillic characters into ASCII equivalents."""
    return "".join(CYRILLIC_TRANSLIT.get(ch, ch) for ch in value.lower())


def compact_alnum(value: str) -> str:
    """Fold case, normalize Russian 'ё', and strip non-alphanumeric characters."""
    return re.sub(r"[^a-zа-я0-9]", "", value.casefold().replace("ё", "е"))

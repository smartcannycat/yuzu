"""Deterministic defect code, body panel, and structural risk normalizers."""

import re
import unicodedata

from ml_service.domains.enums import BodyPanel, DefectCode

DEFECT_ITEM_RE = re.compile(r"^([A-Z]{1,3})([1-4])?$")
_DEDICATED_DEFECT_RE = re.compile(r"^(XX|BP|X|R)([1-4])?$")
_JAPANESE_SIZE_RE = re.compile(r"^([A-Z]{1,3})\(?([小中大])\)?$")
_SEVERITY_RANGE_RE = re.compile(r"^([A-Z]{1,3})([1-4])[-~～]([1-4])$")
_CONCAT_PAIRS_RE = re.compile(r"^(?:(?:XX|BP|[A-Z])[1-4]){2,}$")
_CONCAT_TOKEN_RE = re.compile(r"(XX|BP|[A-Z])([1-4])")
_JAPANESE_SIZE_SEVERITY: dict[str, int] = {"小": 1, "中": 2, "大": 3}

_VALID_SINGLE_DEFECT_LETTERS = frozenset(
    {"A", "U", "B", "E", "W", "S", "C", "Y", "P", "H", "G", "O", "T", "L", "F", "M"}
)
_DEDICATED_TOKENS = frozenset({"XX", "BP", "X", "R"})
_VALID_ALL_TOKENS = _VALID_SINGLE_DEFECT_LETTERS | _DEDICATED_TOKENS

_DEFECT_LABELS_RU: dict[str, str] = {
    "A": "царапина",
    "U": "вмятина",
    "B": "вмятина с царапиной",
    "E": "мелкая вмятина (тычок)",
    "W": "ремонт/волна окраса",
    "S": "ржавчина",
    "C": "коррозия",
    "Y": "трещина/разрыв",
    "P": "нарушение ЛКП",
    "H": "выгорание/облезание ЛКП",
    "G": "скол стекла",
    "O": "выпуклость (выдавливание)",
    "T": "подкрас/скол",
    "L": "перекос/зазор элемента",
    "F": "трещина/отслоение",
    "M": "отсутствует элемент/доработка",
    "BP": "кузовной ремонт с окрасом",
    "XX": "замена детали",
    "X": "требуется замена",
    "R": "следы ремонта",
}

_PANEL_ZONE_KEYWORDS: tuple[tuple[str, BodyPanel, str], ...] = (
    ("コアサポート", BodyPanel.OTHER, "Рамка радиатора (Core Support)"),
    ("クロスメンバー", BodyPanel.OTHER, "Поперечина кузова (Crossmember)"),
    ("インパネ", BodyPanel.OTHER, "Брызговик/внутреннее крыло"),
    ("インサイドパネル", BodyPanel.OTHER, "Брызговик/внутреннее крыло"),
    ("ピラー", BodyPanel.OTHER, "Стойка кузова"),
    ("サイドメンバー", BodyPanel.OTHER, "Лонжерон"),
    ("フレーム", BodyPanel.OTHER, "Рама / силовой лонжерон"),
    ("フェンダー左前", BodyPanel.FRONT_LEFT_FENDER, "Переднее левое крыло"),
    ("左Fフェンダー", BodyPanel.FRONT_LEFT_FENDER, "Переднее левое крыло"),
    ("右Fフェンダー", BodyPanel.FRONT_RIGHT_FENDER, "Переднее правое крыло"),
    ("左Fドア", BodyPanel.FRONT_LEFT_DOOR, "Передняя левая дверь"),
    ("右Fドア", BodyPanel.FRONT_RIGHT_DOOR, "Передняя правая дверь"),
    ("左Rドア", BodyPanel.REAR_LEFT_DOOR, "Задняя левая дверь"),
    ("右Rドア", BodyPanel.REAR_RIGHT_DOOR, "Задняя правая дверь"),
    ("Fバンパー", BodyPanel.FRONT_BUMPER, "Передний бампер"),
    ("Rバンパー", BodyPanel.REAR_BUMPER, "Задний бампер"),
    ("ボンネット", BodyPanel.HOOD, "Капот"),
    ("ルーフ", BodyPanel.ROOF, "Крыша"),
    ("トランク", BodyPanel.TAILGATE, "Крышка багажника / пятая дверь"),
    ("バックドア", BodyPanel.TAILGATE, "Пятая дверь"),
    ("フロントガラス", BodyPanel.WINDSHIELD, "Лобовое стекло"),
)

_REPAIR_ACTION_RE = re.compile(
    r"(XX|BP\d?|\bX\b|\bR\b|W\d?|交換|修理|鈑金|歪|曲|凹|修復|замен|ремонт|деформац)",
    re.IGNORECASE,
)
_PILLAR_OR_FRAME_RE = re.compile(
    r"(ピラー|サイドメンバー|フレーム|修復歴|骨格|стойк|лонжерон)", re.IGNORECASE
)
_INSIDE_PANEL_ONLY_RE = re.compile(r"(インパネ|インサイドパネル)", re.IGNORECASE)
_CORE_SUPPORT_RE = re.compile(r"(コアサポート|рамк[аи]\s+радиатора|телевизор)", re.IGNORECASE)
_NO_ANOMALY_RE = re.compile(r"(異常なし|問題なし|исправн|в\s+норме)", re.IGNORECASE)
_STANDALONE_NO_ANOMALY_RE = re.compile(
    r"^(?:特に)?(?:異常なし|問題なし|исправно|в\s+норме)$", re.IGNORECASE
)


def _expand_defect_letters(
    letters: str, severity: int | None
) -> list[tuple[DefectCode, int | None]] | None:
    if letters in _DEDICATED_TOKENS:
        return [(DefectCode(letters), severity)]
    if letters and all(ch in _VALID_SINGLE_DEFECT_LETTERS for ch in letters):
        return [(DefectCode(ch), severity) for ch in letters]
    return None


def _parse_single_defect_token(upper_part: str) -> list[tuple[DefectCode, int | None]] | None:
    dedicated = _DEDICATED_DEFECT_RE.match(upper_part)
    if dedicated:
        code_str, sev_str = dedicated.groups()
        return [(DefectCode(code_str), int(sev_str) if sev_str else None)]

    jp_size = _JAPANESE_SIZE_RE.match(upper_part)
    if jp_size:
        letters, size_char = jp_size.groups()
        return _expand_defect_letters(letters, _JAPANESE_SIZE_SEVERITY[size_char])

    sev_range = _SEVERITY_RANGE_RE.match(upper_part)
    if sev_range:
        letters, sev_start, sev_end = sev_range.groups()
        return _expand_defect_letters(letters, max(int(sev_start), int(sev_end)))

    if _CONCAT_PAIRS_RE.match(upper_part):
        pairs = _CONCAT_TOKEN_RE.findall(upper_part)
        if pairs and all(tok in _VALID_ALL_TOKENS for tok, _ in pairs):
            return [(DefectCode(tok), int(sev)) for tok, sev in pairs]
        return None

    standard = DEFECT_ITEM_RE.match(upper_part)
    if standard:
        letters, sev_str = standard.groups()
        return _expand_defect_letters(letters, int(sev_str) if sev_str else None)

    return None


def parse_defect_codes_with_warnings(
    raw_code: str,
) -> tuple[list[tuple[DefectCode, int | None]], list[str]]:
    """Parse composite defect code into validated (DefectCode, severity) pairs and warnings."""
    norm = unicodedata.normalize("NFKC", raw_code).strip()
    norm = re.sub(r"([1-4])\s*([-~～])\s*([1-4])", r"\1\2\3", norm)
    parts = re.split(r"[/,\s+・]+", norm)
    results: list[tuple[DefectCode, int | None]] = []
    warnings: list[str] = []

    for part in parts:
        raw_part = part.strip()
        if not raw_part:
            continue
        parsed = _parse_single_defect_token(raw_part.upper())
        if parsed is None:
            warnings.append(f"unknown_defect_code:{raw_part}")
            continue
        results.extend(parsed)

    return results, warnings


def split_defect_codes(raw_code: str) -> list[tuple[str, int | None]]:
    """Split composite body diagram defect codes into validated (code, severity) pairs."""
    parsed, _ = parse_defect_codes_with_warnings(raw_code)
    return [(code.value, severity) for code, severity in parsed]


def build_defect_description_ru(
    panel_ru: str,
    defect_code: DefectCode | str,
    severity: int | None,
    *,
    raw_code: str = "",
) -> str:
    """Build deterministic Russian human-readable description for a normalized defect."""
    code_str = defect_code.value if isinstance(defect_code, DefectCode) else str(defect_code)
    label = _DEFECT_LABELS_RU.get(code_str, code_str.lower())
    panel = panel_ru.strip() or "Кузов"
    norm_raw = unicodedata.normalize("NFKC", raw_code)
    small_suffix = " (small)" if "小" in norm_raw else ""
    if severity is not None:
        return f"{panel} — {label}, степень {severity}{small_suffix}"
    return f"{panel} — {label}{small_suffix}"


def normalize_body_panel(
    panel_id: BodyPanel,
    panel_ru: str,
    visual_location: str = "",
) -> tuple[BodyPanel, str]:
    """Map body panel into canonical 16 panels or BodyPanel.OTHER with Russian name."""
    combined = f"{visual_location} {panel_ru}"
    for keyword, mapped_panel, default_ru in _PANEL_ZONE_KEYWORDS:
        if keyword in combined:
            clean_ru = panel_ru.strip() or default_ru
            if mapped_panel == BodyPanel.OTHER:
                return BodyPanel.OTHER, clean_ru
            return mapped_panel if panel_id == BodyPanel.OTHER else panel_id, clean_ru
    return panel_id, (panel_ru.strip() or "Другая зона кузова")


def derive_structural_risk_flags(
    *,
    llm_pillar_or_frame: bool,
    llm_core_support: bool,
    inspector_notes_raw: list[str],
    inspector_notes_ru: list[str],
    defect_texts: list[str],
) -> tuple[bool, bool]:
    """Deterministically refine structural risk flags based on Japanese notes and repair codes."""
    all_lines = [*inspector_notes_raw, *inspector_notes_ru, *defect_texts]
    all_raw = " | ".join(inspector_notes_raw)
    clauses = [
        clause.strip()
        for line in all_lines
        for clause in re.split(r"[、,。;/\n]+", line)
        if clause.strip()
    ]
    raw_clauses = [
        clause.strip()
        for line in inspector_notes_raw
        for clause in re.split(r"[、,。;/\n]+", line)
        if clause.strip()
    ]
    has_standalone_no_anomaly = any(_STANDALONE_NO_ANOMALY_RE.match(c) for c in raw_clauses)

    pillar_clauses = [c for c in clauses if _PILLAR_OR_FRAME_RE.search(c)]
    has_active_pillar = any(not _NO_ANOMALY_RE.search(c) for c in pillar_clauses)
    has_inside_panel_only = bool(_INSIDE_PANEL_ONLY_RE.search(all_raw)) and not pillar_clauses

    if has_active_pillar:
        pillar_or_frame = True
    elif pillar_clauses or has_inside_panel_only or has_standalone_no_anomaly:
        pillar_or_frame = False
    else:
        pillar_or_frame = llm_pillar_or_frame

    core_clauses = [c for c in clauses if _CORE_SUPPORT_RE.search(c)]
    if core_clauses:
        core_support = any(
            _REPAIR_ACTION_RE.search(c) and not _NO_ANOMALY_RE.search(c) for c in core_clauses
        )
    else:
        core_support = False if has_standalone_no_anomaly else llm_core_support

    return pillar_or_frame, core_support

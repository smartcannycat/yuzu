"""Deterministic defect code, body panel, and structural risk normalizers."""

import re
import unicodedata

from ml_service.domains.enums import BodyPanel, DefectCode

DEFECT_ITEM_RE = re.compile(r"^([A-Z]{1,2})([1-3])?$")
_VALID_SINGLE_DEFECT_LETTERS = frozenset({"A", "U", "W", "S", "C", "P", "G"})

_DEFECT_LABELS_RU: dict[str, str] = {
    "A": "царапина",
    "U": "вмятина",
    "W": "ремонт/волна окраса",
    "S": "ржавчина",
    "C": "коррозия",
    "P": "нарушение ЛКП",
    "G": "скол стекла",
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
    r"(XX|\bX\b|\bR\b|W\d?|交換|修理|鈑金|歪|曲|凹|修復|замен|ремонт|деформац)", re.IGNORECASE
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


def parse_defect_codes_with_warnings(
    raw_code: str,
) -> tuple[list[tuple[DefectCode, int | None]], list[str]]:
    """Parse composite defect code into validated (DefectCode, severity) pairs and warnings."""
    norm = unicodedata.normalize("NFKC", raw_code).strip()
    parts = re.split(r"[/,\s]+", norm)
    results: list[tuple[DefectCode, int | None]] = []
    warnings: list[str] = []

    for part in parts:
        raw_part = part.strip()
        if not raw_part:
            continue
        upper_part = raw_part.upper()

        if upper_part in {"S小", "S(小)"}:
            results.append((DefectCode.S, 1))
            continue
        if upper_part in {"C小", "C(小)"}:
            results.append((DefectCode.C, 1))
            continue
        if upper_part in {"XX", "X", "R"}:
            results.append((DefectCode(upper_part), None))
            continue

        match = DEFECT_ITEM_RE.match(upper_part)
        if not match:
            warnings.append(f"unknown_defect_code:{raw_part}")
            continue

        letters = match.group(1)
        severity = int(match.group(2)) if match.group(2) else None
        if all(ch in _VALID_SINGLE_DEFECT_LETTERS for ch in letters):
            results.extend((DefectCode(ch), severity) for ch in letters)
        else:
            warnings.append(f"unknown_defect_code:{raw_part}")

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

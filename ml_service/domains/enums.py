from enum import Enum


class BodyPanel(str, Enum):
    """Canonical 16 vehicle body panels (Domain 1) + safe fallback 'other'."""

    FRONT_BUMPER = "front_bumper"
    REAR_BUMPER = "rear_bumper"
    HOOD = "hood"
    ROOF = "roof"
    TAILGATE = "tailgate"
    FRONT_LEFT_FENDER = "front_left_fender"
    FRONT_RIGHT_FENDER = "front_right_fender"
    FRONT_LEFT_DOOR = "front_left_door"
    FRONT_RIGHT_DOOR = "front_right_door"
    REAR_LEFT_DOOR = "rear_left_door"
    REAR_RIGHT_DOOR = "rear_right_door"
    REAR_LEFT_QUARTER = "rear_left_quarter"
    REAR_RIGHT_QUARTER = "rear_right_quarter"
    LEFT_SILL = "left_sill"
    RIGHT_SILL = "right_sill"
    WINDSHIELD = "windshield"
    OTHER = "other"


class AuctionHouse(str, Enum):
    """Canonical auction house identifiers (Domain 1 + API contracts)."""

    TAA = "TAA"
    USS = "USS"
    JU = "JU"
    ARAI = "ARAI"
    CAA = "CAA"
    HONDA = "Honda"
    AUCNET = "AUCNET"
    MIRIVE = "MIRIVE"
    ORIX = "ORIX"
    ZIP = "ZIP"
    KCAA = "KCAA"
    LAA = "LAA"
    OTHER = "OTHER"


class DefectCode(str, Enum):
    """Canonical Japanese auction sheet defect mark codes."""

    A = "A"
    U = "U"
    W = "W"
    S = "S"
    C = "C"
    XX = "XX"
    X = "X"
    P = "P"
    G = "G"
    R = "R"


class TaskStep(str, Enum):
    """Canonical batch item processing step names."""

    QUEUED = "queued"
    GATEKEEPER = "gatekeeper"
    FAST_HEADER_OCR = "fast_header_ocr"
    GEMINI_OCR = "gemini_ocr"
    COMPLETED = "completed"
    FAILED = "failed"


class OdometerStatus(str, Enum):
    """Odometer authenticity status based on Japanese auction sheet marks."""

    CONFIRMED = "confirmed"
    REPLACED = "replaced"    # Marked with '*' on sheet
    TAMPERED = "tampered"    # Marked with '$' on sheet
    UNKNOWN = "unknown"      # Marked with '#' on sheet


class FuelType(str, Enum):
    """Vehicle powertrain fuel type."""

    GASOLINE = "gasoline"
    HYBRID = "hybrid"
    DIESEL = "diesel"
    EV = "ev"
    OTHER = "other"


class DriveType(str, Enum):
    """Explicitly marked drive configuration on auction sheet."""

    TWO_WD = "2WD"
    FOUR_WD = "4WD"


class FrameIdConfidence(str, Enum):
    """Confidence level of canonical Frame ID normalization."""

    EXACT = "exact"              # Full code-chassis written on sheet (e.g. NRE210-2005418)
    SYNTHESIZED = "synthesized"  # Synthesized from katashiki + serial (e.g. 6AA-RV5 + 1356915 -> RV5-1356915)
    RAW = "raw"                  # Unverified fallback


class ParseStatus(str, Enum):
    """Final status of auction sheet parsing."""

    OK = "ok"
    PARTIAL = "partial"
    REJECTED_NOT_SHEET = "rejected_not_sheet"


class LayoutComplexity(str, Enum):
    """Sheet visual complexity determined by the Gatekeeper model."""

    CLEAN_DIGITAL = "clean_digital"
    COMPLEX_OR_HANDWRITTEN = "complex_or_handwritten"


class BatchStatus(str, Enum):
    """Overall status of a multi-sheet batch."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"


class BatchItemState(str, Enum):
    """Processing state of an individual sheet inside a batch."""

    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    REJECTED_NOT_SHEET = "rejected_not_sheet"

from django.db.models import TextChoices


class TrafficLightColor(TextChoices):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class AuctionHouse(TextChoices):
    TAA = "TAA"
    USS = "USS"
    CAA = "CAA"
    JU = "JU"
    HONDA = "Honda"
    ARAI = "ARAI"
    MIRIVE = "MIRIVE"
    KCAA = "KCAA"
    LAA = "LAA"
    ORIX = "ORIX"
    ZIP = "ZIP"
    AUCNET = "AUCNET"
    OTHER = "OTHER"


class BatchStatus(TextChoices):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"


class ItemProcessingStatus(TextChoices):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class TaskStep(TextChoices):
    GATEKEEPER = "gatekeeper"
    FAST_HEADER_OCR = "fast_header_ocr"
    GEMINI_OCR = "gemini_ocr"
    CROSS_AUDIT = "cross_audit"
    CUSTOMS_CALC = "customs_calc"
    FARPOST_PARTS = "farpost_parts"
    DROM_MARKET = "drom_market"
    SCORING = "scoring"
    COMPLETED = "completed"
    FAILED = "failed"


class MascotMood(TextChoices):
    SLEEPING = "sleeping"
    THINKING = "thinking"
    HAPPY = "happy"
    CONFUSED = "confused"
    WARNING = "warning"


class BodyPanel(TextChoices):
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


class DefectCode(TextChoices):
    A = "A"
    U = "U"
    W = "W"
    S = "S"
    C = "C"
    XX = "XX"
    X = "X"
    P = "P"
    G = "G"


class OdometerStatus(TextChoices):
    CONFIRMED = "confirmed"
    REPLACED = "replaced"
    TAMPERED = "tampered"
    UNKNOWN = "unknown"


class RiskLevel(TextChoices):
    CLEAN = "CLEAN"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AgeCorridor(TextChoices):
    UNDER_3_YEARS = "under_3_years"
    THREE_TO_FIVE_YEARS = "3_to_5_years"
    OVER_5_YEARS = "over_5_years"


class UtilFeeType(TextChoices):
    PERSONAL = "personal"
    COMMERCIAL = "commercial"


class ChecklistItemStatus(TextChoices):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CrossAuditStatus(TextChoices):
    CLEAN = "clean"
    ANOMALY_DETECTED = "anomaly_detected"
    NOT_FOUND = "not_found"
    LIVE_ONLY = "live_only"
    UNAVAILABLE = "unavailable"


class DriveType(TextChoices):
    TWO_WD = "2WD"
    FOUR_WD = "4WD"


class FuelType(TextChoices):
    GASOLINE = "gasoline"
    HYBRID = "hybrid"
    DIESEL = "diesel"
    EV = "ev"
    OTHER = "other"


class FrameIdConfidence(TextChoices):
    EXACT = "exact"
    SYNTHESIZED = "synthesized"
    RAW = "raw"


class PowerHpSource(TextChoices):
    DROM_CATALOG = "drom_catalog"
    KATASHIKI_CACHE = "katashiki_cache"
    MANUAL = "manual"


class DutyCalculationMode(TextChoices):
    EUR_PER_CC = "eur_per_cc"
    PCT_OF_VALUE = "pct_of_value"


class WorkType(TextChoices):
    MOUNT_DISMOUNT = "mount_dismount"
    PAINT = "paint"
    PDR_AND_POLISH = "pdr_and_polish"
    BODYWORK = "bodywork"


class SystemKey(TextChoices):
    STRUCTURAL_FRAME = "structural_frame"
    AIRBAGS_SRS = "airbags_srs"
    ENGINE_TRANSMISSION = "engine_transmission"
    UNDERBODY_CORROSION = "underbody_corrosion"
    FLOOD_OR_FIRE = "flood_or_fire"


class AnomalySeverity(TextChoices):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ExternalCacheSource(TextChoices):
    CBRF = "cbrf"
    DROM = "drom"
    FARPOST = "farpost"
    AUCJP = "aucjp"


class LotLifecycleFilter(TextChoices):
    ACTIVE = "active"
    ARCHIVED = "archived"
    ALL = "all"


class LotArchiveReason(TextChoices):
    EXPIRED = "expired"
    MANUAL = "manual"

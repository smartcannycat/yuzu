from django.contrib import admin

from apps.lots.models import (
    AnomalyAlert,
    Batch,
    BatchItem,
    CrossAuditReport,
    CurrencyRatesSnapshot,
    CustomsCalculation,
    DamagedPartItem,
    FarpostRepairSummary,
    Lot,
    LotDefect,
    LotRiskFlags,
    MarketComparisonInfo,
    PastAuctionRecord,
    SafetyCheckItem,
    SafetyChecklist,
    ServiceWorkItem,
    TrafficLightVerdict,
    WiseCostLadder,
    WiseCostStep,
)


class BatchItemInline(admin.StackedInline):
    model = BatchItem
    extra = 0
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("user__email", "id")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [BatchItemInline]


class LotDefectInline(admin.TabularInline):
    model = LotDefect
    extra = 0


class LotRiskFlagsInline(admin.StackedInline):
    model = LotRiskFlags
    extra = 0


class TrafficLightVerdictInline(admin.StackedInline):
    model = TrafficLightVerdict
    extra = 0


class MarketComparisonInfoInline(admin.StackedInline):
    model = MarketComparisonInfo
    extra = 0


class SafetyChecklistInline(admin.StackedInline):
    model = SafetyChecklist
    extra = 0


class CustomsCalculationInline(admin.StackedInline):
    model = CustomsCalculation
    extra = 0


class FarpostRepairSummaryInline(admin.StackedInline):
    model = FarpostRepairSummary
    extra = 0


class WiseCostLadderInline(admin.StackedInline):
    model = WiseCostLadder
    extra = 0


class CrossAuditReportInline(admin.StackedInline):
    model = CrossAuditReport
    extra = 0


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "make",
        "model",
        "lot_number",
        "frame_id",
        "verdict",
        "has_anomaly",
        "completed_at",
    )
    list_filter = ("verdict", "has_anomaly", "auction_house", "meti_sanction_risk")
    search_fields = ("make", "model", "frame_id", "lot_number", "chassis_number")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [
        LotDefectInline,
        LotRiskFlagsInline,
        TrafficLightVerdictInline,
        MarketComparisonInfoInline,
        CrossAuditReportInline,
        SafetyChecklistInline,
        CustomsCalculationInline,
        FarpostRepairSummaryInline,
        WiseCostLadderInline,
    ]


class AnomalyAlertInline(admin.TabularInline):
    model = AnomalyAlert
    extra = 0


class PastAuctionRecordInline(admin.TabularInline):
    model = PastAuctionRecord
    extra = 0


class SafetyCheckItemInline(admin.TabularInline):
    model = SafetyCheckItem
    extra = 0


class DamagedPartItemInline(admin.TabularInline):
    model = DamagedPartItem
    extra = 0


class ServiceWorkItemInline(admin.TabularInline):
    model = ServiceWorkItem
    extra = 0


class WiseCostStepInline(admin.TabularInline):
    model = WiseCostStep
    extra = 0


class CurrencyRatesSnapshotInline(admin.StackedInline):
    model = CurrencyRatesSnapshot
    extra = 0

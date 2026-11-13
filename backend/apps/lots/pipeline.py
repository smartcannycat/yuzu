import logging
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.module_loading import import_string

from apps.core.enums import (
    BatchStatus,
    ItemProcessingStatus,
    MascotMood,
    TaskStep,
)
from apps.core.exceptions import (
    BadRequestProblemError,
    ConflictProblemError,
    NotFoundProblemError,
)
from apps.lots.economics import (
    _missing_customs_inputs,
    _resolve_start_bid_jpy,
    recompute_lot_economics,
)
from apps.lots.integrations.drom.schemas import DromFetchError, DromMarketResult, DromSearchCriteria
from apps.lots.integrations.farpost.service import save_repair_estimate
from apps.lots.models import Batch, BatchItem, Lot, MarketComparisonInfo, WiseCostLadder
from apps.lots.queries import _build_lot_summary, _has_full_detail
from apps.lots.schemas import (
    BatchCreateResponse,
    BatchItemStatus,
    BatchProgressResponse,
    LotSummary,
    MascotState,
)
from apps.users.models import User

logger = logging.getLogger(__name__)

_ALLOWED_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
)
_ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"})
_MAX_FILE_SIZE = 15 * 1024 * 1024
_MAX_FILES_PER_UPLOAD = 10
_MAX_FILES_PER_BATCH = 20
_POLL_INTERVAL_MS = 1500
_PIPELINE_STEP_DELAY_SEC = 0.2

_BATCH_TERMINAL_STATUSES = frozenset({BatchStatus.COMPLETED, BatchStatus.FAILED})

_SUMMARY_REQUIRED_FIELDS: tuple[str, ...] = (
    "make",
    "model",
    "frame_id",
    "auction_house",
    "lot_number",
    "overall_grade",
    "turnkey_cost_rub",
    "market_price_rf_rub",
    "verdict",
    "verdict_headline",
    "net_benefit_rub",
)


def _validate_upload_files(files: list[UploadedFile]) -> None:
    if not files:
        raise BadRequestProblemError(
            "Не выбрано ни одного файла",
            title="Файлы не переданы",
        )
    if len(files) > _MAX_FILES_PER_UPLOAD:
        raise BadRequestProblemError(
            f"Можно загрузить не более {_MAX_FILES_PER_UPLOAD} файлов за один раз",
            title="Превышен лимит файлов",
        )
    for upload in files:
        _validate_single_file(upload)


def _validate_single_file(upload: UploadedFile) -> None:
    name = upload.name or ""
    ext = Path(name).suffix.lower()
    content_type = (upload.content_type or "").lower()
    allowed = content_type in _ALLOWED_MIME_TYPES if content_type else ext in _ALLOWED_EXTENSIONS
    if not allowed:
        raise BadRequestProblemError(
            f"Файл «{name}» имеет недопустимый формат. Разрешены: JPEG, PNG, WEBP, HEIC, HEIF",
            title="Недопустимый формат файла",
        )
    if upload.size is None or upload.size > _MAX_FILE_SIZE:
        raise BadRequestProblemError(
            f"Файл «{name}» превышает максимальный размер {_MAX_FILE_SIZE // (1024 * 1024)} МБ",
            title="Превышен размер файла",
        )


def _next_file_index(batch: Batch) -> int:
    max_index = batch.items.aggregate(max=Max("file_index"))["max"]
    return (max_index if max_index is not None else -1) + 1


def _create_batch_items(
    batch: Batch,
    user: User,
    files: list[UploadedFile],
    *,
    start_index: int = 0,
) -> None:
    for offset, upload in enumerate(files):
        upload.seek(0)
        lot = Lot.objects.create(user=user)
        item = BatchItem.objects.create(
            batch=batch,
            lot=lot,
            file_index=start_index + offset,
            original_filename=upload.name,
            status=ItemProcessingStatus.QUEUED,
            current_step=TaskStep.GATEKEEPER,
        )
        item.original_file.save(upload.name, upload, save=True)


def _schedule_batch_pipeline(batch_id: uuid.UUID) -> None:
    transaction.on_commit(
        lambda: threading.Thread(target=run_batch_pipeline, args=(batch_id,), daemon=True).start()
    )


@transaction.atomic
def create_batch(user: User, files: list[UploadedFile]) -> BatchCreateResponse:
    """Validate uploaded auction sheets, create a batch, and enqueue background processing."""
    _validate_upload_files(files)
    batch = Batch.objects.create(user=user, status=BatchStatus.QUEUED)
    _create_batch_items(batch, user, files, start_index=0)
    _schedule_batch_pipeline(batch.id)
    return BatchCreateResponse(
        batch_id=batch.id,
        total_items=len(files),
        status=batch.status,
        created_at=batch.created_at,
        poll_interval_ms=_POLL_INTERVAL_MS,
    )


@transaction.atomic
def append_batch_items(
    user: User,
    batch_id: uuid.UUID,
    files: list[UploadedFile],
) -> BatchProgressResponse:
    """Append additional auction sheets to an active or partial-failed batch."""
    _validate_upload_files(files)
    try:
        batch = Batch.objects.select_for_update().get(id=batch_id, user=user)
    except Batch.DoesNotExist as exc:
        raise NotFoundProblemError(
            "Пачка не найдена",
            title="Пачка не найдена",
        ) from exc
    if batch.status in _BATCH_TERMINAL_STATUSES:
        raise ConflictProblemError(
            "Пачка уже завершена. Откройте новую пачку через POST /api/v1/lots/batches",
            title="Пачка завершена",
        )
    current_count = batch.items.count()
    if current_count + len(files) > _MAX_FILES_PER_BATCH:
        raise BadRequestProblemError(
            f"В одной пачке может быть не более {_MAX_FILES_PER_BATCH} файлов",
            title="Превышен лимит файлов в пачке",
        )
    _create_batch_items(batch, user, files, start_index=_next_file_index(batch))
    if batch.status == BatchStatus.PARTIAL_FAILED:
        batch.status = BatchStatus.QUEUED
        batch.save(update_fields=["status", "updated_at"])
        _schedule_batch_pipeline(batch.id)
    return get_batch_progress(user, batch_id)


def get_batch_progress(user: User, batch_id: uuid.UUID) -> BatchProgressResponse:
    """Return current processing progress and item statuses for a user's batch."""
    try:
        batch = Batch.objects.get(id=batch_id, user=user)
    except Batch.DoesNotExist as exc:
        raise NotFoundProblemError(
            "Пачка не найдена",
            title="Пачка не найдена",
        ) from exc
    return _build_batch_progress(batch)


def _build_batch_progress(batch: Batch) -> BatchProgressResponse:
    items = list(batch.items.order_by("file_index").select_related("lot"))
    ready_count = sum(1 for i in items if i.status == ItemProcessingStatus.READY)
    failed_count = sum(1 for i in items if i.status == ItemProcessingStatus.FAILED)
    return BatchProgressResponse(
        batch_id=batch.id,
        status=batch.status,
        mascot=_build_mascot(batch.status, ready_count, len(items)),
        total_count=len(items),
        processed_count=ready_count + failed_count,
        ready_count=ready_count,
        failed_count=failed_count,
        items=[_build_item_status(item) for item in items],
    )


def _build_item_status(item: BatchItem) -> BatchItemStatus:
    summary: LotSummary | None = None
    if item.status == ItemProcessingStatus.READY and item.lot is not None and item.lot.make:
        summary = _build_lot_summary(item.lot)
    return BatchItemStatus(
        lot_id=item.lot_id,
        file_index=item.file_index,
        original_filename=item.original_filename,
        preview_title=item.preview_title,
        status=item.status,
        current_step=item.current_step,
        error_message=item.error_message,
        summary=summary,
    )


def _build_mascot(status: str, ready_count: int, total_count: int) -> MascotState:
    if status == BatchStatus.COMPLETED:
        return MascotState(
            mood=MascotMood.HAPPY,
            phrase_ru=f"Все лоты готовы! {ready_count}/{total_count}",
            badge_text=f"{ready_count} из {total_count} готово",
        )
    if status == BatchStatus.PARTIAL_FAILED:
        return MascotState(
            mood=MascotMood.CONFUSED,
            phrase_ru=f"Часть листов не распознана. Готово {ready_count}/{total_count}",
            badge_text=f"{ready_count} из {total_count} готово",
        )
    if status == BatchStatus.FAILED:
        return MascotState(
            mood=MascotMood.WARNING,
            phrase_ru="Не удалось обработать листы",
            badge_text=f"0 из {total_count} готово",
        )
    return MascotState(
        mood=MascotMood.THINKING,
        phrase_ru=f"Распознаем лоты... {ready_count}/{total_count}",
        badge_text=f"{ready_count} из {total_count} готово",
    )


def _claim_next_queued_item(batch_id: uuid.UUID) -> BatchItem | None:
    with transaction.atomic():
        item = (
            BatchItem.objects.select_for_update()
            .filter(batch_id=batch_id, status=ItemProcessingStatus.QUEUED)
            .order_by("file_index")
            .first()
        )
        if item is None:
            return None
        item.status = ItemProcessingStatus.PROCESSING
        item.current_step = TaskStep.GATEKEEPER
        item.save(update_fields=["status", "current_step", "updated_at"])
        return item


def _advance_step(item: BatchItem, step: TaskStep) -> None:
    item.current_step = step
    item.save(update_fields=["current_step", "updated_at"])
    time.sleep(_PIPELINE_STEP_DELAY_SEC)


def _fail_item(item: BatchItem, step: TaskStep, message: str) -> None:
    item.status = ItemProcessingStatus.FAILED
    item.current_step = step
    item.error_message = message
    item.save(update_fields=["status", "current_step", "error_message", "updated_at"])


def _missing_summary_fields(lot: Lot) -> list[str]:
    missing: list[str] = []
    for name in _SUMMARY_REQUIRED_FIELDS:
        value = getattr(lot, name, None)
        if value is None or value == "":
            missing.append(name)
    return missing


def _complete_item(item: BatchItem) -> None:
    item.status = ItemProcessingStatus.READY
    item.current_step = TaskStep.COMPLETED
    if item.lot is not None:
        item.lot.completed_at = timezone.now()
        item.lot.save(update_fields=["completed_at", "updated_at"])
    item.save(update_fields=["status", "current_step", "updated_at"])


def _step_gatekeeper(item: BatchItem) -> bool:
    _advance_step(item, TaskStep.GATEKEEPER)
    if not item.original_file or not item.original_file.storage.exists(item.original_file.name):
        _fail_item(item, TaskStep.FAILED, "Файл не найден на диске")
        return False
    return True


def _step_cross_audit(_item: BatchItem) -> bool:
    return True


def _persist_drom_market_result(lot: Lot, result: DromMarketResult) -> None:
    with transaction.atomic():
        lot_locked = Lot.objects.select_for_update().get(pk=lot.pk)
        lot_locked.market_price_rf_rub = result.market_price_rf_rub
        update_fields = ["market_price_rf_rub", "updated_at"]
        if lot_locked.power_hp is None and result.power_hp is not None:
            lot_locked.power_hp = result.power_hp
            lot_locked.power_hp_source = result.power_hp_source
            lot_locked.is_under_160_hp = result.is_under_160_hp
            update_fields.extend(["power_hp", "power_hp_source", "is_under_160_hp"])
        lot_locked.save(update_fields=update_fields)

        MarketComparisonInfo.objects.update_or_create(
            lot=lot_locked,
            defaults={
                "market_price_rf_rub": result.market_price_rf_rub,
                "analogs_count": result.analogs_count,
                "price_min_rub": result.price_min_rub,
                "price_max_rub": result.price_max_rub,
                "search_region_ru": result.search_region_ru,
                "excludes_under_order": result.excludes_under_order,
                "filtered_out_under_order_count": result.filtered_out_under_order_count,
                "is_fallback": result.is_fallback,
                "fallback_reason_ru": result.fallback_reason_ru,
                "drom_search_url": result.drom_search_url,
            },
        )


def _step_drom_market(item: BatchItem) -> bool:
    # Resolve via apps.lots.services so tests patching apps.lots.services.DromMarketService work.
    from apps.lots import services as lots_services

    try:
        lot = item.lot
        if lot is None or not lot.make or not lot.model:
            _fail_item(item, TaskStep.FAILED, "Недостаточно данных для поиска аналогов на Drom.ru")
            return False

        criteria = DromSearchCriteria(
            make=lot.make,
            model=lot.model,
            year=lot.year or lot.first_reg_year,
            engine_cc=lot.engine_cc,
            drive_type=lot.drive_type,
            transmission=lot.transmission,
            fuel_type=lot.fuel_type,
            model_code=lot.model_code,
        )
        result = lots_services.DromMarketService().evaluate(criteria)
        _persist_drom_market_result(lot, result)
        return True
    except DromFetchError as exc:
        logger.warning("Drom market step failed for item %s: %s", item.pk, exc)
        _fail_item(item, TaskStep.FAILED, "Не удалось получить рыночные аналоги на Drom.ru")
        return False
    except Exception:
        logger.exception("Unexpected error in Drom market step for item %s", item.pk)
        _fail_item(item, TaskStep.FAILED, "Ошибка при подборе рыночных аналогов на Drom.ru")
        return False


def _step_farpost_parts(item: BatchItem) -> bool:
    if item.lot is None:
        _fail_item(item, TaskStep.FAILED, "Лот не привязан к элементу пачки")
        return False
    try:
        save_repair_estimate(item.lot)
    except Exception:
        logger.exception("Repair estimate failed for item %s", item.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось сформировать смету ремонта")
        return False
    return True


def _step_customs_calc(item: BatchItem) -> bool:
    _advance_step(item, TaskStep.CUSTOMS_CALC)
    lot = item.lot
    if lot is None:
        _fail_item(item, TaskStep.FAILED, "Лот не привязан к элементу пачки")
        return False
    # Fill in the start bid (sheet -> auction history -> reverse calculation
    # from the Drom price) before checking the remaining inputs, so a new
    # lot without an explicit bid still gets its economics built.
    try:
        ladder = WiseCostLadder.objects.filter(lot=lot).first()
        bid_jpy = ladder.car_bid_jpy if ladder is not None else _resolve_start_bid_jpy(lot)
    except Exception:
        logger.exception("Start bid derivation failed for lot %s", lot.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось определить стартовую ставку лота")
        return False
    missing = _missing_customs_inputs(lot, bid_jpy)
    if missing:
        _fail_item(
            item,
            TaskStep.FAILED,
            "Недостаточно данных для расчёта таможни: " + ", ".join(missing),
        )
        return False
    try:
        recompute_lot_economics(lot, bid_jpy=bid_jpy)
        lot.refresh_from_db()
    except Exception:
        logger.exception("Customs recomputation failed for lot %s", lot.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось рассчитать таможные платежи")
        return False
    return True


def _step_scoring(item: BatchItem) -> bool:
    _advance_step(item, TaskStep.SCORING)
    return True


def _run_step_in_worker(step_fn, item: BatchItem) -> bool:
    try:
        return bool(step_fn(item))
    except Exception:
        logger.exception("Parallel pipeline step %s crashed for item %s", step_fn.__name__, item.pk)
        try:
            already_failed = BatchItem.objects.filter(
                pk=item.pk,
                status=ItemProcessingStatus.FAILED,
            ).exists()
            if not already_failed:
                _fail_item(item, TaskStep.FAILED, "Внутренняя ошибка при обработке лота")
        except Exception:
            logger.exception("Failed to mark item %s as FAILED after step crash", item.pk)
        return False
    finally:
        connection.close()


def _run_parallel_steps(item: BatchItem, step_fns: list) -> bool:
    with ThreadPoolExecutor(max_workers=len(step_fns)) as pool:
        futures = {pool.submit(_run_step_in_worker, fn, item): fn for fn in step_fns}
        for future in as_completed(futures):
            if not future.result():
                pool.shutdown(wait=False, cancel_futures=True)
                return False
    return True


def _run_ocr_stage(item: BatchItem) -> bool:
    if not settings.LOT_PARSER_BACKEND:
        _fail_item(item, TaskStep.FAILED, "Сервис распознавания не настроен")
        return False
    try:
        parser = import_string(settings.LOT_PARSER_BACKEND)()
        rejection = parser.gatekeeper(item)
        if rejection:
            _fail_item(item, TaskStep.FAILED, rejection)
            return False
        _advance_step(item, TaskStep.FAST_HEADER_OCR)
        item.preview_title = parser.fast_header(item)
        item.save(update_fields=["preview_title", "updated_at"])
        _advance_step(item, TaskStep.GEMINI_OCR)
        parser.parse(item)
        item.lot.refresh_from_db()
        if not item.lot.make or not item.lot.model:
            _fail_item(item, TaskStep.FAILED, "Распознавание не вернуло марку и модель")
            return False
        return True
    except Exception:
        logger.exception("Parser failed for batch item %s", item.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось распознать аукционный лист")
        return False


def _validate_ready_lot(item: BatchItem) -> bool:
    if item.lot is None:
        _fail_item(item, TaskStep.FAILED, "Лот не привязан к элементу пачки")
        return False
    missing = _missing_summary_fields(item.lot)
    if missing:
        _fail_item(
            item,
            TaskStep.FAILED,
            f"Недостаточно данных для карточки лота: {', '.join(missing)}",
        )
        return False
    item.lot.refresh_from_db()
    if not _has_full_detail(item.lot):
        _fail_item(
            item,
            TaskStep.FAILED,
            "Недостаточно данных для детальной карточки лота",
        )
        return False
    return True


def _process_item(item: BatchItem) -> None:
    if not _step_gatekeeper(item) or not _run_ocr_stage(item):
        return
    _advance_step(item, TaskStep.CROSS_AUDIT)
    if not _run_parallel_steps(
        item,
        [_step_cross_audit, _step_drom_market, _step_farpost_parts],
    ):
        return
    if item.lot is not None:
        item.lot.refresh_from_db()
    if not _step_customs_calc(item) or not _step_scoring(item):
        return
    if not _validate_ready_lot(item):
        return
    _complete_item(item)


def _finalize_batch_locked(batch: Batch) -> None:
    items = list(batch.items.all())
    total = len(items)
    ready = sum(1 for i in items if i.status == ItemProcessingStatus.READY)
    failed = sum(1 for i in items if i.status == ItemProcessingStatus.FAILED)
    if total == 0:
        status = BatchStatus.FAILED
    elif ready == total:
        status = BatchStatus.COMPLETED
    elif failed == total:
        status = BatchStatus.FAILED
    else:
        status = BatchStatus.PARTIAL_FAILED
    batch.status = status
    batch.save(update_fields=["status", "updated_at"])


def run_batch_pipeline(batch_id: uuid.UUID) -> None:
    """Process all queued items in a batch sequentially and finalize batch status."""
    try:
        with transaction.atomic():
            batch = Batch.objects.select_for_update().get(id=batch_id)
            if batch.status != BatchStatus.QUEUED:
                return
            batch.status = BatchStatus.PROCESSING
            batch.save(update_fields=["status", "updated_at"])
        while True:
            item = _claim_next_queued_item(batch_id)
            if item is not None:
                _process_item(item)
                continue
            with transaction.atomic():
                batch = Batch.objects.select_for_update().get(id=batch_id)
                if batch.items.filter(status=ItemProcessingStatus.QUEUED).exists():
                    continue
                _finalize_batch_locked(batch)
                break
    except Exception:
        logger.exception("Batch pipeline failed for %s", batch_id)
        with transaction.atomic():
            batch = Batch.objects.select_for_update().get(id=batch_id)
            batch.items.filter(
                status__in=(ItemProcessingStatus.QUEUED, ItemProcessingStatus.PROCESSING)
            ).update(
                status=ItemProcessingStatus.FAILED,
                current_step=TaskStep.FAILED,
                error_message="Не удалось обработать аукционный лист",
                updated_at=timezone.now(),
            )
            _finalize_batch_locked(batch)
    finally:
        connection.close()


def recover_batches_on_startup() -> None:
    """Requeue interrupted batches when the application server starts."""
    if "pytest" in sys.modules:
        return
    stuck_statuses = [BatchStatus.QUEUED, BatchStatus.PROCESSING]
    batches = Batch.objects.filter(status__in=stuck_statuses)
    for batch in batches:
        BatchItem.objects.filter(
            batch=batch,
            status=ItemProcessingStatus.PROCESSING,
        ).update(
            status=ItemProcessingStatus.QUEUED,
            current_step=TaskStep.GATEKEEPER,
        )
        Batch.objects.filter(id=batch.id).update(status=BatchStatus.QUEUED)
        threading.Thread(target=run_batch_pipeline, args=(batch.id,), daemon=True).start()

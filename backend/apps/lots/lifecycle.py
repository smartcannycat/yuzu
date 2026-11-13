import re
import uuid
from datetime import UTC, datetime, timedelta
from datetime import timezone as dt_timezone

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.enums import LotArchiveReason
from apps.core.exceptions import NotFoundProblemError
from apps.lots import schemas
from apps.lots.models import Lot
from apps.users.models import User

_JST = dt_timezone(timedelta(hours=9))
_FALLBACK_TTL = timedelta(days=3)
_AUCTION_DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")


def compute_lot_expires_at(created_at: datetime, auction_date: str | None) -> datetime:
    """Compute auto-archive deadline (UTC): auction_date end-of-day JST + 24h, or +3d."""
    if auction_date:
        match = _AUCTION_DATE_RE.match(auction_date.strip())
        if match:
            day, month, year = (int(group) for group in match.groups())
            try:
                end_of_day_jst = datetime(year, month, day, 23, 59, 59, tzinfo=_JST)
            except ValueError:
                end_of_day_jst = None
            if end_of_day_jst is not None:
                return (end_of_day_jst + timedelta(days=1)).astimezone(UTC)

    base = created_at
    if timezone.is_naive(base):
        base = timezone.make_aware(base, UTC)
    return (base + _FALLBACK_TTL).astimezone(UTC)


def archive_expired_lots_for_user(user: User, *, now: datetime | None = None) -> int:
    """Archive user's active completed lots that have reached ``expires_at``."""
    current_time = now or timezone.now()
    return Lot.objects.filter(
        user=user,
        completed_at__isnull=False,
        deleted_at__isnull=True,
        is_archived=False,
        auto_archive_disabled=False,
        expires_at__isnull=False,
        expires_at__lte=current_time,
    ).update(
        is_archived=True,
        archived_reason=LotArchiveReason.EXPIRED,
        archived_at=F("expires_at"),
        updated_at=current_time,
    )


def _get_ready_user_lot(user: User, lot_id: uuid.UUID) -> Lot:
    try:
        return Lot.objects.select_for_update().get(
            id=lot_id,
            user=user,
            completed_at__isnull=False,
            deleted_at__isnull=True,
        )
    except Lot.DoesNotExist as exc:
        raise NotFoundProblemError("Лот не найден", title="Лот не найден") from exc


@transaction.atomic
def update_lot_lifecycle(
    user: User,
    lot_id: uuid.UUID,
    *,
    is_archived: bool,
) -> schemas.LotSummary:
    """Manually archive a lot or restore it to active without future auto-archiving."""
    from apps.lots.queries import _build_lot_summary

    now = timezone.now()
    archive_expired_lots_for_user(user, now=now)
    lot = _get_ready_user_lot(user, lot_id)

    if is_archived:
        lot.is_archived = True
        lot.archived_reason = LotArchiveReason.MANUAL
        lot.archived_at = now
    else:
        lot.is_archived = False
        lot.archived_at = None
        lot.archived_reason = None
        lot.expires_at = None
        lot.auto_archive_disabled = True

    lot.save(
        update_fields=[
            "is_archived",
            "archived_at",
            "archived_reason",
            "expires_at",
            "auto_archive_disabled",
            "updated_at",
        ]
    )
    return _build_lot_summary(lot)


@transaction.atomic
def delete_lot(user: User, lot_id: uuid.UUID) -> None:
    """Soft-delete a single completed lot owned by ``user``."""
    lot = _get_ready_user_lot(user, lot_id)
    lot.deleted_at = timezone.now()
    lot.save(update_fields=["deleted_at", "updated_at"])


@transaction.atomic
def bulk_delete_lots(user: User, lot_ids: list[uuid.UUID]) -> schemas.LotBulkDeleteResponse:
    """Idempotently soft-delete user's completed lots and report missing/inaccessible IDs."""
    unique_ids = list(dict.fromkeys(lot_ids))
    deletable_ids = set(
        Lot.objects.select_for_update()
        .filter(
            id__in=unique_ids,
            user=user,
            completed_at__isnull=False,
            deleted_at__isnull=True,
        )
        .values_list("id", flat=True)
    )
    if deletable_ids:
        now = timezone.now()
        Lot.objects.filter(id__in=deletable_ids).update(
            deleted_at=now,
            updated_at=now,
        )

    deleted_ids = [lot_id for lot_id in unique_ids if lot_id in deletable_ids]
    not_found_ids = [lot_id for lot_id in unique_ids if lot_id not in deletable_ids]
    return schemas.LotBulkDeleteResponse(
        deleted_ids=deleted_ids,
        not_found_ids=not_found_ids,
        deleted_count=len(deleted_ids),
    )

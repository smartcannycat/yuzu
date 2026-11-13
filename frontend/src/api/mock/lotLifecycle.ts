import type { LotSummary } from '@/types/api'

const DAY_MS = 24 * 60 * 60 * 1000
const FALLBACK_TTL_DAYS = 3
const JST_OFFSET_MS = 9 * 60 * 60 * 1000

/**
 * Formats a date in Japan Standard Time (UTC+9) as "DD.MM.YYYY" with a day offset from `nowMs`.
 */
export function formatJstAuctionDateWithOffset(daysFromNow: number, nowMs = Date.now()): string {
  const jstWall = new Date(nowMs + JST_OFFSET_MS + daysFromNow * DAY_MS)
  const day = String(jstWall.getUTCDate()).padStart(2, '0')
  const month = String(jstWall.getUTCMonth() + 1).padStart(2, '0')
  const year = String(jstWall.getUTCFullYear())
  return `${day}.${month}.${year}`
}

/**
 * Returns an ISO UTC timestamp shifted by `daysFromNow` and optional `hoursOffset` relative to `nowMs`.
 */
export function isoWithOffset(daysFromNow: number, hoursOffset = 0, nowMs = Date.now()): string {
  return new Date(nowMs + daysFromNow * DAY_MS + hoursOffset * 60 * 60 * 1000).toISOString()
}

/**
 * Computes auto-archive deadline (UTC ISO):
 * - if valid DD.MM.YYYY `auctionDate` is present: end of `auctionDate` in JST (23:59:59+09:00) + 24h;
 * - otherwise: `createdAtIso` + 3 days (72h).
 */
export function computeLotExpiresAt(createdAtIso: string, auctionDate: string | null): string {
  if (auctionDate) {
    const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(auctionDate.trim())
    if (match) {
      const day = Number(match[1])
      const month = Number(match[2])
      const year = Number(match[3])
      const utcCheck = new Date(Date.UTC(year, month - 1, day))
      const isValidCalendarDate =
        utcCheck.getUTCFullYear() === year &&
        utcCheck.getUTCMonth() === month - 1 &&
        utcCheck.getUTCDate() === day

      if (isValidCalendarDate) {
        const endOfDayJstUtcMs = Date.UTC(year, month - 1, day, 23, 59, 59) - JST_OFFSET_MS
        return new Date(endOfDayJstUtcMs + DAY_MS).toISOString()
      }
    }
  }

  const createdMs = Date.parse(createdAtIso)
  const baseMs = Number.isFinite(createdMs) ? createdMs : Date.now()
  return new Date(baseMs + FALLBACK_TTL_DAYS * DAY_MS).toISOString()
}

/**
 * Applies lazy auto-archival transition if an active lot has reached its `expires_at` deadline
 * and wasn't explicitly unarchived by the user.
 */
export function applyLotExpiry(
  lot: LotSummary,
  nowMs: number,
  suppressedAutoArchiveIds?: ReadonlySet<string>,
): { lot: LotSummary; didChange: boolean } {
  if (lot.is_archived || !lot.expires_at || suppressedAutoArchiveIds?.has(lot.lot_id)) {
    return { lot, didChange: false }
  }

  const expiresMs = Date.parse(lot.expires_at)
  if (!Number.isFinite(expiresMs) || nowMs < expiresMs) {
    return { lot, didChange: false }
  }

  return {
    didChange: true,
    lot: {
      ...lot,
      is_archived: true,
      archived_at: lot.expires_at,
      archived_reason: 'expired',
    },
  }
}

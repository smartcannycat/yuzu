import { createMockProblem, generateUuid } from '@/api/mock/helpers'
import { MOCK_IN_PROGRESS_SUMMARY, SEEDED_MOCK_LOTS } from '@/api/mock/lotsSeed'
import type {
  BatchCreateResponse,
  BatchItemStatus,
  BatchProgressResponse,
  BatchStatus,
  InProgressItemPreview,
  InProgressSummary,
  LotSummary,
  MascotState,
  TaskStep,
} from '@/types/api'
import {
  BATCH_MAX_FILES_PER_UPLOAD,
  BATCH_MAX_FILE_SIZE_BYTES,
  BATCH_MAX_TOTAL_FILES,
  isSupportedBatchFile,
} from '@/utils/batchFiles'
import { formatSheetCountRu } from '@/utils/formatters'

const DAG_STEPS: readonly TaskStep[] = [
  'gatekeeper',
  'fast_header_ocr',
  'gemini_ocr',
  'cross_audit',
  'customs_calc',
  'farpost_parts',
  'drom_market',
  'scoring',
]

const STEP_DURATION_MS = 650
const ITEM_STAGGER_MS = 700
const SEEDED_BATCH_GRACE_MS = 2400

interface JdmTemplateSeed {
  keywords: readonly string[]
  make: string
  model: string
  year: number
  engine_cc: number
  framePrefix: string
  auction_house: LotSummary['auction_house']
  lot_number: string
  overall_grade: string
  mileage_km: number
  turnkey_cost_rub: number
  market_price_rf_rub: number
  verdict: LotSummary['verdict']
  verdict_headline: string
  net_benefit_rub: number
  meti_sanction_risk: boolean
  has_anomaly: boolean
  anomaly_text: string | null
}

const JDM_TEMPLATES: readonly JdmTemplateSeed[] = [
  {
    keywords: ['corolla', 'touring', '3142'],
    make: 'Toyota',
    model: 'Corolla Touring',
    year: 2021,
    engine_cc: 1797,
    framePrefix: 'ZWE211',
    auction_house: 'TAA',
    lot_number: '3142',
    overall_grade: '4',
    mileage_km: 54000,
    turnkey_cost_rub: 1580000,
    market_price_rf_rub: 1860000,
    verdict: 'green',
    verdict_headline: 'Можно брать • +280 000 ₽ к рынку РФ',
    net_benefit_rub: 280000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
  },
  {
    keywords: ['harrier', '5541'],
    make: 'Toyota',
    model: 'Harrier',
    year: 2020,
    engine_cc: 1986,
    framePrefix: 'MXUA80',
    auction_house: 'USS',
    lot_number: '5541',
    overall_grade: '3.5',
    mileage_km: 71000,
    turnkey_cost_rub: 2540000,
    market_price_rf_rub: 2635000,
    verdict: 'yellow',
    verdict_headline: 'Под вопросом • окрас правой двери и ДВС >1.9 л',
    net_benefit_rub: 95000,
    meti_sanction_risk: true,
    has_anomaly: false,
    anomaly_text: null,
  },
  {
    keywords: ['vezel', '8412'],
    make: 'Honda',
    model: 'Vezel',
    year: 2021,
    engine_cc: 1496,
    framePrefix: 'RV5',
    auction_house: 'CAA',
    lot_number: '8412',
    overall_grade: '4.5',
    mileage_km: 39000,
    turnkey_cost_rub: 1910000,
    market_price_rf_rub: 2180000,
    verdict: 'green',
    verdict_headline: 'Можно брать • +270 000 ₽ и без санкций METI',
    net_benefit_rub: 270000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
  },
  {
    keywords: ['note', '1102'],
    make: 'Nissan',
    model: 'Note e-Power',
    year: 2022,
    engine_cc: 1198,
    framePrefix: 'E13',
    auction_house: 'JU',
    lot_number: '1102',
    overall_grade: '4',
    mileage_km: 47000,
    turnkey_cost_rub: 1320000,
    market_price_rf_rub: 1495000,
    verdict: 'green',
    verdict_headline: 'Можно брать • чистый лист без окрасов',
    net_benefit_rub: 175000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
  },
  {
    keywords: ['forester', '5190', 'subaru'],
    make: 'Subaru',
    model: 'Forester',
    year: 2019,
    engine_cc: 2498,
    framePrefix: 'SK9',
    auction_house: 'TAA',
    lot_number: '5190',
    overall_grade: 'R',
    mileage_km: 92000,
    turnkey_cost_rub: 2480000,
    market_price_rf_rub: 2390000,
    verdict: 'red',
    verdict_headline: 'Высокий риск • замена силового лонжерона XX',
    net_benefit_rub: -90000,
    meti_sanction_risk: true,
    has_anomaly: true,
    anomaly_text: 'На предыдущих торгах USS зафиксирована оценка R и ремонт передней панели',
  },
  {
    keywords: ['prius', '4419'],
    make: 'Toyota',
    model: 'Prius',
    year: 2020,
    engine_cc: 1797,
    framePrefix: 'ZVW51',
    auction_house: 'TAA',
    lot_number: '4419',
    overall_grade: '4',
    mileage_km: 64000,
    turnkey_cost_rub: 1740000,
    market_price_rf_rub: 1960000,
    verdict: 'green',
    verdict_headline: 'Можно брать • подтверждённый пробег TAA',
    net_benefit_rub: 220000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
  },
  {
    keywords: ['fit', '7820'],
    make: 'Honda',
    model: 'Fit e:HEV',
    year: 2021,
    engine_cc: 1496,
    framePrefix: 'GR3',
    auction_house: 'USS',
    lot_number: '7820',
    overall_grade: '4.5',
    mileage_km: 41000,
    turnkey_cost_rub: 1410000,
    market_price_rf_rub: 1580000,
    verdict: 'green',
    verdict_headline: 'Можно брать • экономия +170 000 ₽ к рынку РФ',
    net_benefit_rub: 170000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
  },
]

interface MockBatchItemRecord {
  lotId: string
  fileIndex: number
  originalFilename: string
  initialPreviewTitle?: string
  enqueuedAtMs: number
  startDelayMs: number
  initialStepIndex: number
  template: LotSummary
}

interface MockBatchRecord {
  batchId: string
  createdAtIso: string
  items: MockBatchItemRecord[]
}

function buildLotSummaryFromTemplate(
  seed: JdmTemplateSeed,
  lotId: string,
  sequenceSuffix: number,
  createdAtIso: string,
): LotSummary {
  const numericSuffix = String(100000 + ((sequenceSuffix * 7919) % 899999))
  return {
    lot_id: lotId,
    make: seed.make,
    model: seed.model,
    year: seed.year,
    engine_cc: seed.engine_cc,
    frame_id: `${seed.framePrefix}-${numericSuffix}`,
    auction_house: seed.auction_house,
    lot_number: seed.lot_number,
    overall_grade: seed.overall_grade,
    mileage_km: seed.mileage_km,
    turnkey_cost_rub: seed.turnkey_cost_rub,
    market_price_rf_rub: seed.market_price_rf_rub,
    verdict: seed.verdict,
    verdict_headline: seed.verdict_headline,
    net_benefit_rub: seed.net_benefit_rub,
    meti_sanction_risk: seed.meti_sanction_risk,
    has_anomaly: seed.has_anomaly,
    anomaly_text: seed.anomaly_text,
    thumbnail_url: null,
    created_at: createdAtIso,
  }
}

function pickTemplateForFilename(filename: string, fallbackIndex: number): JdmTemplateSeed {
  const lower = filename.toLowerCase()
  const matched = JDM_TEMPLATES.find((tpl) => tpl.keywords.some((kw) => lower.includes(kw)))
  if (matched) return matched
  const tpl = JDM_TEMPLATES[fallbackIndex % JDM_TEMPLATES.length]
  if (tpl) return tpl
  return JDM_TEMPLATES[0]!
}

function resolveItemSnapshot(item: MockBatchItemRecord, nowMs: number): BatchItemStatus {
  const elapsed = nowMs - item.enqueuedAtMs - item.startDelayMs
  if (elapsed < 0) {
    return {
      lot_id: item.lotId,
      file_index: item.fileIndex,
      original_filename: item.originalFilename,
      preview_title:
        item.initialPreviewTitle ??
        (item.initialStepIndex >= 1
          ? `${item.template.make} ${item.template.model} • Лот ${item.template.lot_number}`
          : null),
      status: item.initialStepIndex > 0 ? 'processing' : 'queued',
      current_step: DAG_STEPS[item.initialStepIndex] ?? 'gatekeeper',
      error_message: null,
      summary: null,
    }
  }

  const stepIndex = item.initialStepIndex + Math.floor(elapsed / STEP_DURATION_MS)
  if (stepIndex >= DAG_STEPS.length) {
    return {
      lot_id: item.lotId,
      file_index: item.fileIndex,
      original_filename: item.originalFilename,
      preview_title: `${item.template.make} ${item.template.model} #${item.template.lot_number}`,
      status: 'ready',
      current_step: 'completed',
      error_message: null,
      summary: item.template,
    }
  }

  const currentStep = DAG_STEPS[stepIndex] ?? 'gatekeeper'
  return {
    lot_id: item.lotId,
    file_index: item.fileIndex,
    original_filename: item.originalFilename,
    preview_title:
      stepIndex >= 1
        ? `${item.template.make} ${item.template.model} #${item.template.lot_number}`
        : null,
    status: stepIndex === 0 && elapsed < 250 ? 'queued' : 'processing',
    current_step: currentStep,
    error_message: null,
    summary: null,
  }
}

function buildMascotState(
  status: BatchStatus,
  totalCount: number,
  readyCount: number,
  failedCount: number,
): MascotState {
  if (status === 'completed') {
    return {
      mood: 'happy',
      phrase_ru: `Готово! Разобрано ${formatSheetCountRu(readyCount)}`,
      badge_text: `${readyCount} из ${totalCount} готово`,
    }
  }
  if (status === 'partial_failed') {
    return {
      mood: 'confused',
      phrase_ru: `Готово ${readyCount} из ${totalCount}, есть ошибки`,
      badge_text: `${readyCount} готово · ${failedCount} сбой`,
    }
  }
  if (status === 'failed') {
    return {
      mood: 'warning',
      phrase_ru: 'Не удалось распознать загруженные фото',
      badge_text: `Ошибок: ${failedCount}`,
    }
  }
  return {
    mood: 'thinking',
    phrase_ru: 'Анализируем аукционные листы...',
    badge_text: `${readyCount} из ${totalCount} готово`,
  }
}

function validateUploadFilesForMock(files: readonly File[], instancePath: string): void {
  if (files.length === 0 || files.length > BATCH_MAX_FILES_PER_UPLOAD) {
    throw createMockProblem({
      slug: 'invalid-batch-count',
      title: 'Некорректное количество файлов',
      status: 400,
      detail: `Можно загрузить от 1 до ${BATCH_MAX_FILES_PER_UPLOAD} изображений за один раз.`,
      instance: instancePath,
    })
  }

  for (const file of files) {
    if (!isSupportedBatchFile(file)) {
      throw createMockProblem({
        slug: 'unsupported-file-type',
        title: 'Неподдерживаемый формат файла',
        status: 400,
        detail: `Файл «${file.name}» не является изображением JPG, PNG, WEBP или HEIC.`,
        instance: instancePath,
      })
    }
    if (file.size > BATCH_MAX_FILE_SIZE_BYTES) {
      throw createMockProblem({
        slug: 'file-too-large',
        title: 'Превышен размер файла',
        status: 400,
        detail: `Файл «${file.name}» превышает лимит 15 МБ.`,
        instance: instancePath,
      })
    }
  }
}

export interface MockLotsWorkspace {
  getFeedSnapshot(): { lots: LotSummary[]; inProgress: InProgressSummary }
  createBatch(files: readonly File[]): BatchCreateResponse
  getBatch(batchId: string): BatchProgressResponse
  appendBatchItems(batchId: string, files: readonly File[]): BatchProgressResponse
}

export function createMockLotsWorkspace(): MockLotsWorkspace {
  const feedLots: LotSummary[] = [...SEEDED_MOCK_LOTS]
  const promotedLotIds = new Set(feedLots.map((lot) => lot.lot_id))
  const batches = new Map<string, MockBatchRecord>()
  let sequenceCounter = 10

  // Pre-seed the default in-progress batch so clicking items from the dashboard opens a live queue.
  const seededBatchId = MOCK_IN_PROGRESS_SUMMARY.items[0]?.batch_id
  if (seededBatchId) {
    const bootTimeMs = Date.now()
    const createdAtIso = new Date(bootTimeMs).toISOString()
    batches.set(seededBatchId, {
      batchId: seededBatchId,
      createdAtIso,
      items: MOCK_IN_PROGRESS_SUMMARY.items.map((seedItem, idx) => {
        const templateSeed = pickTemplateForFilename(seedItem.display_title, idx + 5)
        const stepIdx = Math.max(0, DAG_STEPS.indexOf(seedItem.current_step))
        const lotId = generateUuid()
        return {
          lotId,
          fileIndex: idx,
          originalFilename: `sheet_${templateSeed.lot_number}.jpg`,
          initialPreviewTitle: seedItem.display_title,
          enqueuedAtMs: bootTimeMs,
          startDelayMs: SEEDED_BATCH_GRACE_MS + idx * 1400,
          initialStepIndex: stepIdx,
          template: buildLotSummaryFromTemplate(
            templateSeed,
            lotId,
            ++sequenceCounter,
            createdAtIso,
          ),
        }
      }),
    })
  }

  function computeBatchProgress(record: MockBatchRecord, nowMs: number): BatchProgressResponse {
    const snapshots = record.items.map((item) => {
      const snap = resolveItemSnapshot(item, nowMs)
      if (snap.status === 'ready' && snap.summary && !promotedLotIds.has(snap.summary.lot_id)) {
        promotedLotIds.add(snap.summary.lot_id)
        feedLots.unshift(snap.summary)
      }
      return snap
    })

    const readyCount = snapshots.filter((item) => item.status === 'ready').length
    const failedCount = snapshots.filter((item) => item.status === 'failed').length
    const processedCount = readyCount + failedCount
    const totalCount = snapshots.length
    const hasActive = snapshots.some(
      (item) => item.status === 'queued' || item.status === 'processing',
    )

    let status: BatchStatus = 'processing'
    if (!hasActive) {
      if (failedCount === 0) status = 'completed'
      else if (readyCount === 0) status = 'failed'
      else status = 'partial_failed'
    } else if (snapshots.every((item) => item.status === 'queued')) {
      status = 'queued'
    }

    return {
      batch_id: record.batchId,
      status,
      mascot: buildMascotState(status, totalCount, readyCount, failedCount),
      total_count: totalCount,
      processed_count: processedCount,
      ready_count: readyCount,
      failed_count: failedCount,
      items: snapshots,
    }
  }

  function syncAllBatches(nowMs: number): InProgressSummary {
    let activeBatchesCount = 0
    const activeItems: InProgressItemPreview[] = []

    for (const record of batches.values()) {
      const progress = computeBatchProgress(record, nowMs)
      const pending = progress.items.filter(
        (item) => item.status === 'queued' || item.status === 'processing',
      )
      if (pending.length > 0) {
        activeBatchesCount += 1
        for (const item of pending) {
          activeItems.push({
            batch_id: record.batchId,
            lot_id: item.lot_id,
            display_title: item.preview_title || item.original_filename,
            status: item.status,
            current_step: item.current_step,
          })
        }
      }
    }

    return {
      active_batches_count: activeBatchesCount,
      total_processing_lots: activeItems.length,
      items: activeItems,
    }
  }

  return {
    getFeedSnapshot() {
      const inProgress = syncAllBatches(Date.now())
      return {
        lots: [...feedLots],
        inProgress,
      }
    },

    createBatch(files: readonly File[]): BatchCreateResponse {
      validateUploadFilesForMock(files, '/api/v1/lots/batches')
      const nowMs = Date.now()
      const createdAtIso = new Date(nowMs).toISOString()
      const batchId = generateUuid()

      const items: MockBatchItemRecord[] = files.map((file, idx) => {
        const lotId = generateUuid()
        const templateSeed = pickTemplateForFilename(file.name, idx + sequenceCounter)
        return {
          lotId,
          fileIndex: idx,
          originalFilename: file.name,
          enqueuedAtMs: nowMs,
          startDelayMs: idx * ITEM_STAGGER_MS,
          initialStepIndex: 0,
          template: buildLotSummaryFromTemplate(
            templateSeed,
            lotId,
            ++sequenceCounter,
            new Date(nowMs + idx * 1000).toISOString(),
          ),
        }
      })

      batches.set(batchId, { batchId, createdAtIso, items })

      return {
        batch_id: batchId,
        total_items: items.length,
        status: 'queued',
        created_at: createdAtIso,
        poll_interval_ms: 1500,
      }
    },

    getBatch(batchId: string): BatchProgressResponse {
      const record = batches.get(batchId)
      if (!record) {
        throw createMockProblem({
          slug: 'batch-not-found',
          title: 'Очередь не найдена',
          status: 404,
          detail: `Пачка ${batchId} не найдена в очереди обработки.`,
          instance: `/api/v1/lots/batches/${batchId}`,
        })
      }
      return computeBatchProgress(record, Date.now())
    },

    appendBatchItems(batchId: string, files: readonly File[]): BatchProgressResponse {
      const instancePath = `/api/v1/lots/batches/${batchId}/items`
      const record = batches.get(batchId)
      if (!record) {
        throw createMockProblem({
          slug: 'batch-not-found',
          title: 'Очередь не найдена',
          status: 404,
          detail: `Пачка ${batchId} не найдена в очереди обработки.`,
          instance: instancePath,
        })
      }

      const nowMs = Date.now()
      const currentProgress = computeBatchProgress(record, nowMs)
      if (
        currentProgress.status === 'completed' ||
        currentProgress.status === 'partial_failed' ||
        currentProgress.status === 'failed'
      ) {
        throw createMockProblem({
          slug: 'batch-already-completed',
          title: 'Очередь уже завершена',
          status: 409,
          detail: 'Эта пачка уже завершена. Создайте новую загрузку с главного экрана.',
          instance: instancePath,
        })
      }

      validateUploadFilesForMock(files, instancePath)
      if (record.items.length + files.length > BATCH_MAX_TOTAL_FILES) {
        throw createMockProblem({
          slug: 'batch-total-limit-exceeded',
          title: 'Превышен общий лимит пачки',
          status: 400,
          detail: `В одной пачке может быть максимум ${BATCH_MAX_TOTAL_FILES} файлов.`,
          instance: instancePath,
        })
      }

      const startIndex = record.items.length
      for (const [offset, file] of files.entries()) {
        const lotId = generateUuid()
        const templateSeed = pickTemplateForFilename(
          file.name,
          startIndex + offset + sequenceCounter,
        )
        record.items.push({
          lotId,
          fileIndex: startIndex + offset,
          originalFilename: file.name,
          enqueuedAtMs: nowMs,
          startDelayMs: offset * ITEM_STAGGER_MS,
          initialStepIndex: 0,
          template: buildLotSummaryFromTemplate(
            templateSeed,
            lotId,
            ++sequenceCounter,
            new Date(nowMs + offset * 1000).toISOString(),
          ),
        })
      }

      return computeBatchProgress(record, Date.now())
    },
  }
}

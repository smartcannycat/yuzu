import { createMockProblem } from '@/api/mock/helpers'
import type { MockBatchItemRecord, MockBatchRecord } from '@/api/mock/lotBatchTemplates'
import type {
  BatchItemStatus,
  BatchProgressResponse,
  BatchStatus,
  MascotState,
  TaskStep,
} from '@/types/api'
import {
  BATCH_MAX_FILES_PER_UPLOAD,
  BATCH_MAX_FILE_SIZE_BYTES,
  isSupportedBatchFile,
} from '@/utils/batchFiles'
import { formatSheetCountRu } from '@/utils/formatters'

export const DAG_STEPS: readonly TaskStep[] = [
  'gatekeeper',
  'gemini_ocr',
  'cross_audit',
  'customs_calc',
  'farpost_parts',
  'drom_market',
  'scoring',
]

export const STEP_DURATION_MS = 650
export const ITEM_STAGGER_MS = 700
export const SEEDED_BATCH_GRACE_MS = 2400

export function resolveItemSnapshot(
  item: MockBatchItemRecord,
  nowMs: number,
  deletedLotIds: ReadonlySet<string>,
): BatchItemStatus {
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
    const isDeleted = deletedLotIds.has(item.lotId)
    return {
      lot_id: isDeleted ? null : item.lotId,
      file_index: item.fileIndex,
      original_filename: item.originalFilename,
      preview_title: `${item.template.make} ${item.template.model} #${item.template.lot_number}`,
      status: 'ready',
      current_step: 'completed',
      error_message: null,
      summary: isDeleted ? null : item.template,
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

export function buildMascotState(
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

export function validateUploadFilesForMock(files: readonly File[], instancePath: string): void {
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
    if (file.size <= 0) {
      throw createMockProblem({
        slug: 'empty-file',
        title: 'Пустой или повреждённый файл',
        status: 400,
        detail: `Файл «${file.name}» пуст или повреждён.`,
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

export function buildBatchProgressSnapshot(
  record: MockBatchRecord,
  nowMs: number,
  deletedLotIds: ReadonlySet<string>,
): BatchProgressResponse {
  const snapshots = record.items.map((item) => resolveItemSnapshot(item, nowMs, deletedLotIds))
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

import { formatSheetCountRu } from '@/utils/formatters'

export const BATCH_MAX_FILES_PER_UPLOAD = 10
export const BATCH_MAX_TOTAL_FILES = 20
export const BATCH_MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024

export const BATCH_ALLOWED_MIME_TYPES = new Set([
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/webp',
  'image/heic',
  'image/heif',
])

const ALLOWED_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'])

export const BATCH_ACCEPT_ATTR =
  'image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif'

export type BatchFileValidationResult = { ok: true; files: File[] } | { ok: false; error: string }

function getLowerExtension(filename: string): string {
  const dotIndex = filename.lastIndexOf('.')
  if (dotIndex < 0) return ''
  return filename.slice(dotIndex).toLowerCase()
}

export function isSupportedBatchFile(file: File): boolean {
  const mime = file.type.trim().toLowerCase()
  if (mime) {
    if (BATCH_ALLOWED_MIME_TYPES.has(mime)) {
      return true
    }
    if (mime !== 'application/octet-stream') {
      return false
    }
  }
  return ALLOWED_EXTENSIONS.has(getLowerExtension(file.name))
}

export function isHeicFile(file: File): boolean {
  const mime = file.type.trim().toLowerCase()
  if (mime === 'image/heic' || mime === 'image/heif') {
    return true
  }
  const ext = getLowerExtension(file.name)
  return ext === '.heic' || ext === '.heif'
}

const SIGNATURE_HEAD_BYTES = 4096
const SIGNATURE_TAIL_BYTES = 2048

async function readBlobBytes(blob: Blob): Promise<Uint8Array> {
  if (typeof blob.arrayBuffer === 'function') {
    return new Uint8Array(await blob.arrayBuffer())
  }
  return new Uint8Array(await new Response(blob).arrayBuffer())
}

function hashBytesFnv1a64(head: Uint8Array, tail: Uint8Array, totalSize: number): string {
  let h1 = 0x811c9dc5
  let h2 = 0x9e3779b9

  const feed = (bytes: Uint8Array) => {
    for (const byte of bytes) {
      h1 ^= byte
      h1 = Math.imul(h1, 0x01000193)
      h2 ^= byte + 0x51
      h2 = Math.imul(h2, 0x85ebca6b)
    }
  }

  feed(head)
  feed(tail)

  return `${totalSize}:${(h1 >>> 0).toString(16).padStart(8, '0')}${(h2 >>> 0).toString(16).padStart(8, '0')}`
}

/**
 * Computes a content-based fingerprint using head/tail byte slices plus exact file size,
 * catching renamed duplicates while allowing distinct images with identical metadata.
 */
export async function getFileSignature(file: File): Promise<string> {
  const headSlice = file.slice(0, Math.min(file.size, SIGNATURE_HEAD_BYTES))
  const tailStart = Math.max(SIGNATURE_HEAD_BYTES, file.size - SIGNATURE_TAIL_BYTES)
  const tailSlice = file.size > SIGNATURE_HEAD_BYTES ? file.slice(tailStart, file.size) : new Blob()

  const [headBytes, tailBytes] = await Promise.all([
    readBlobBytes(headSlice),
    readBlobBytes(tailSlice),
  ])
  return hashBytesFnv1a64(headBytes, tailBytes, file.size)
}

export function formatFileSizeRu(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
  }
  const kb = Math.max(1, Math.round(bytes / 1024))
  return `${kb} КБ`
}

/**
 * Strictly validates an incoming batch of files before adding them to staged selection.
 * Any format, size, duplicate, or count violation rejects the entire incoming addition.
 */
export async function validateBatchFileAddition(
  currentFiles: readonly File[],
  incomingFiles: readonly File[],
  maxFiles: number = BATCH_MAX_FILES_PER_UPLOAD,
): Promise<BatchFileValidationResult> {
  if (incomingFiles.length === 0) {
    return { ok: false, error: 'Не выбрано ни одного файла.' }
  }

  if (maxFiles <= 0) {
    return {
      ok: false,
      error: 'Достигнут максимальный лимит очереди. Откройте новую пачку после завершения.',
    }
  }

  if (currentFiles.length + incomingFiles.length > maxFiles) {
    const remaining = Math.max(0, maxFiles - currentFiles.length)
    return {
      ok: false,
      error:
        remaining > 0
          ? `Можно выбрать максимум ${formatSheetCountRu(maxFiles)} (осталось мест: ${remaining}). Уберите лишние файлы или выберите меньше фото.`
          : `Достигнут лимит ${formatSheetCountRu(maxFiles)}. Удалите часть фото перед добавлением новых.`,
    }
  }

  const invalidTypeNames: string[] = []
  const emptyNames: string[] = []
  const oversizedNames: string[] = []
  const validFiles: File[] = []

  for (const file of incomingFiles) {
    if (!isSupportedBatchFile(file)) {
      invalidTypeNames.push(file.name)
      continue
    }
    if (file.size <= 0) {
      emptyNames.push(file.name)
      continue
    }
    if (file.size > BATCH_MAX_FILE_SIZE_BYTES) {
      oversizedNames.push(file.name)
      continue
    }
    validFiles.push(file)
  }

  if (invalidTypeNames.length > 0) {
    return {
      ok: false,
      error: `Неподдерживаемый формат (${invalidTypeNames.slice(0, 2).join(', ')}). Допустимы JPG, PNG, WEBP и HEIC — замените выбор.`,
    }
  }

  if (emptyNames.length > 0) {
    return {
      ok: false,
      error: `Пустой или повреждённый файл (${emptyNames.slice(0, 2).join(', ')}). Выберите другое фото.`,
    }
  }

  if (oversizedNames.length > 0) {
    return {
      ok: false,
      error: `Файл превышает 15 МБ (${oversizedNames.slice(0, 2).join(', ')}). Сожмите фото или выберите другое.`,
    }
  }

  const [existingSigs, incomingSigs] = await Promise.all([
    Promise.all(currentFiles.map(getFileSignature)),
    Promise.all(validFiles.map(getFileSignature)),
  ])
  const seenSignatures = new Set(existingSigs)
  const duplicateNames: string[] = []

  for (const [idx, file] of validFiles.entries()) {
    const sig = incomingSigs[idx]!
    if (seenSignatures.has(sig)) {
      duplicateNames.push(file.name)
      continue
    }
    seenSignatures.add(sig)
  }

  if (duplicateNames.length > 0) {
    return {
      ok: false,
      error: `Файл уже добавлен в список (${duplicateNames.slice(0, 2).join(', ')}). Уберите дубликаты из выбора.`,
    }
  }

  return { ok: true, files: [...incomingFiles] }
}

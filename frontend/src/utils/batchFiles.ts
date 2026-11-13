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

export function getFileSignature(file: File): string {
  return `${file.name}::${file.size}::${file.lastModified}`
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
export function validateBatchFileAddition(
  currentFiles: readonly File[],
  incomingFiles: readonly File[],
  maxFiles: number = BATCH_MAX_FILES_PER_UPLOAD,
): BatchFileValidationResult {
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
  const duplicateNames: string[] = []
  const seenSignatures = new Set(currentFiles.map(getFileSignature))

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
    const sig = getFileSignature(file)
    if (seenSignatures.has(sig)) {
      duplicateNames.push(file.name)
      continue
    }
    seenSignatures.add(sig)
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

  if (duplicateNames.length > 0) {
    return {
      ok: false,
      error: `Файл уже добавлен в список (${duplicateNames.slice(0, 2).join(', ')}). Уберите дубликаты из выбора.`,
    }
  }

  return { ok: true, files: [...incomingFiles] }
}

interface DemoSheetPreset {
  filename: string
  auction: string
  lotNumber: string
  title: string
  grade: string
  accent: string
}

const DEMO_SHEET_PRESETS: readonly DemoSheetPreset[] = [
  {
    filename: 'sheet_corolla_3142.jpg',
    auction: 'TAA CHUBU',
    lotNumber: '3142',
    title: 'TOYOTA COROLLA TOURING',
    grade: '4',
    accent: '#15803D',
  },
  {
    filename: 'sheet_harrier_5541.jpg',
    auction: 'USS TOKYO',
    lotNumber: '5541',
    title: 'TOYOTA HARRIER HYBRID',
    grade: '3.5',
    accent: '#B45309',
  },
  {
    filename: 'sheet_vezel_8412.jpg',
    auction: 'CAA CHUBU',
    lotNumber: '8412',
    title: 'HONDA VEZEL e:HEV',
    grade: '4.5',
    accent: '#FF6B00',
  },
]

async function renderDemoSheetFile(preset: DemoSheetPreset): Promise<File> {
  if (typeof document !== 'undefined') {
    const canvas = document.createElement('canvas')
    canvas.width = 420
    canvas.height = 580
    const ctx = canvas.getContext('2d')

    if (ctx) {
      ctx.fillStyle = '#FFFDF7'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      ctx.strokeStyle = '#1F2937'
      ctx.lineWidth = 3
      ctx.strokeRect(18, 18, canvas.width - 36, canvas.height - 36)

      ctx.fillStyle = '#111827'
      ctx.fillRect(18, 18, canvas.width - 36, 52)
      ctx.fillStyle = '#FFFFFF'
      ctx.font = 'bold 20px sans-serif'
      ctx.fillText(`${preset.auction}  #${preset.lotNumber}`, 32, 51)

      ctx.fillStyle = '#111827'
      ctx.font = 'bold 17px sans-serif'
      ctx.fillText(preset.title, 32, 102)

      ctx.strokeStyle = '#D1D5DB'
      ctx.lineWidth = 2
      ctx.strokeRect(32, 124, canvas.width - 64, 96)
      ctx.fillStyle = '#6B7280'
      ctx.font = '14px sans-serif'
      ctx.fillText('GRADE', 46, 152)
      ctx.fillStyle = preset.accent
      ctx.font = 'bold 42px sans-serif'
      ctx.fillText(preset.grade, 46, 202)

      // Stylized car diagram box
      ctx.strokeStyle = '#374151'
      ctx.lineWidth = 2
      ctx.strokeRect(32, 244, canvas.width - 64, 210)
      ctx.strokeRect(110, 274, 200, 150)
      ctx.fillStyle = '#9CA3AF'
      ctx.font = '13px sans-serif'
      ctx.fillText('A1   U2   W1', 160, 355)

      ctx.fillStyle = '#6B7280'
      ctx.font = '13px sans-serif'
      ctx.fillText('YUZU DEMO AUCTION SHEET', 32, 520)

      const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob((result) => resolve(result), 'image/jpeg', 0.88)
      })
      if (blob) {
        return new File([blob], preset.filename, { type: 'image/jpeg' })
      }
    }
  }

  return new File([`DEMO:${preset.auction}:${preset.lotNumber}`], preset.filename, {
    type: 'image/jpeg',
  })
}

export async function createDemoAuctionSheetFiles(
  maxCount: number = DEMO_SHEET_PRESETS.length,
): Promise<File[]> {
  const count = Math.max(0, Math.min(maxCount, DEMO_SHEET_PRESETS.length))
  return Promise.all(DEMO_SHEET_PRESETS.slice(0, count).map(renderDemoSheetFile))
}

import { describe, expect, it } from 'vitest'

import {
  BATCH_MAX_FILE_SIZE_BYTES,
  createDemoAuctionSheetFiles,
  formatFileSizeRu,
  isHeicFile,
  validateBatchFileAddition,
} from './batchFiles'

function makeFile(name: string, type: string, sizeBytes = 1024): File {
  const content = new Uint8Array(Math.min(sizeBytes, 32))
  const file = new File([content], name, { type, lastModified: 1700000000000 })
  if (sizeBytes !== content.byteLength) {
    Object.defineProperty(file, 'size', { value: sizeBytes })
  }
  return file
}

describe('batchFiles utilities', () => {
  it('accepts valid image formats including HEIC with empty MIME', () => {
    const valid = [
      makeFile('sheet_1.jpg', 'image/jpeg', 2048),
      makeFile('sheet_2.png', 'image/png', 4096),
      makeFile('sheet_3.webp', 'image/webp', 8192),
      makeFile('IMG_5190.HEIC', '', 1024 * 500),
    ]

    const result = validateBatchFileAddition([], valid)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.files).toHaveLength(4)
    }
    expect(isHeicFile(valid[3]!)).toBe(true)
    expect(isHeicFile(valid[0]!)).toBe(false)
  })

  it('strictly rejects entire addition if any file has unsupported format or exceeds 15 MB', () => {
    const mixedBadType = [
      makeFile('valid.jpg', 'image/jpeg', 2048),
      makeFile('doc.pdf', 'application/pdf', 2048),
    ]
    const badTypeResult = validateBatchFileAddition([], mixedBadType)
    expect(badTypeResult.ok).toBe(false)
    if (!badTypeResult.ok) {
      expect(badTypeResult.error).toContain('doc.pdf')
    }

    const oversized = [
      makeFile('valid.png', 'image/png', 2048),
      makeFile('huge.jpg', 'image/jpeg', BATCH_MAX_FILE_SIZE_BYTES + 1),
    ]
    const oversizedResult = validateBatchFileAddition([], oversized)
    expect(oversizedResult.ok).toBe(false)
    if (!oversizedResult.ok) {
      expect(oversizedResult.error).toContain('15 МБ')
    }
  })

  it('strictly rejects when adding files exceeds max limit or includes duplicates', () => {
    const existing = Array.from({ length: 8 }, (_, idx) =>
      makeFile(`sheet_${idx}.jpg`, 'image/jpeg', 2048 + idx),
    )

    const tooMany = validateBatchFileAddition(existing, [
      makeFile('extra_1.jpg', 'image/jpeg', 2048),
      makeFile('extra_2.jpg', 'image/jpeg', 2049),
      makeFile('extra_3.jpg', 'image/jpeg', 2050),
    ])
    expect(tooMany.ok).toBe(false)
    if (!tooMany.ok) {
      expect(tooMany.error).toContain('осталось мест: 2')
    }

    const dupResult = validateBatchFileAddition(existing, [
      makeFile('sheet_0.jpg', 'image/jpeg', 2048),
    ])
    expect(dupResult.ok).toBe(false)
    if (!dupResult.ok) {
      expect(dupResult.error).toContain('sheet_0.jpg')
    }
  })

  it('formats sizes in KB/MB and creates demo sheets within requested limit', async () => {
    expect(formatFileSizeRu(512 * 1024)).toBe('512 КБ')
    expect(formatFileSizeRu(2.5 * 1024 * 1024)).toBe('2.5 МБ')

    const demos = await createDemoAuctionSheetFiles(2)
    expect(demos).toHaveLength(2)
    expect(demos[0]?.type).toBe('image/jpeg')
  })
})

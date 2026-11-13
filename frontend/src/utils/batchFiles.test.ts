import { describe, expect, it } from 'vitest'

import { createDemoAuctionSheetFiles } from './batchDemo'
import {
  BATCH_MAX_FILE_SIZE_BYTES,
  formatFileSizeRu,
  isHeicFile,
  validateBatchFileAddition,
} from './batchFiles'

function makeFile(name: string, type: string, sizeBytes = 1024, seed = name): File {
  const bytes = new Uint8Array(Math.min(sizeBytes, 64))
  for (let i = 0; i < bytes.length; i += 1) {
    bytes[i] = (seed.charCodeAt(i % seed.length) + i * 17) & 0xff
  }
  const file = new File([bytes], name, { type, lastModified: 1700000000000 })
  if (sizeBytes !== bytes.byteLength) {
    Object.defineProperty(file, 'size', { value: sizeBytes })
  }
  return file
}

describe('batchFiles utilities', () => {
  it('accepts valid image formats including HEIC with empty MIME', async () => {
    const valid = [
      makeFile('sheet_1.jpg', 'image/jpeg', 2048),
      makeFile('sheet_2.png', 'image/png', 4096),
      makeFile('sheet_3.webp', 'image/webp', 8192),
      makeFile('IMG_5190.HEIC', '', 1024 * 500),
    ]

    const result = await validateBatchFileAddition([], valid)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.files).toHaveLength(4)
    }
    expect(isHeicFile(valid[3]!)).toBe(true)
    expect(isHeicFile(valid[0]!)).toBe(false)
  })

  it('strictly rejects entire addition if any file has unsupported format or exceeds 15 MB', async () => {
    const mixedBadType = [
      makeFile('valid.jpg', 'image/jpeg', 2048),
      makeFile('doc.pdf', 'application/pdf', 2048),
    ]
    const badTypeResult = await validateBatchFileAddition([], mixedBadType)
    expect(badTypeResult.ok).toBe(false)
    if (!badTypeResult.ok) {
      expect(badTypeResult.error).toContain('doc.pdf')
    }

    const spoofedExtension = [makeFile('renamed.jpg', 'application/pdf', 2048)]
    expect((await validateBatchFileAddition([], spoofedExtension)).ok).toBe(false)

    const oversized = [
      makeFile('valid.png', 'image/png', 2048),
      makeFile('huge.jpg', 'image/jpeg', BATCH_MAX_FILE_SIZE_BYTES + 1),
    ]
    const oversizedResult = await validateBatchFileAddition([], oversized)
    expect(oversizedResult.ok).toBe(false)
    if (!oversizedResult.ok) {
      expect(oversizedResult.error).toContain('15 МБ')
    }
  })

  it('strictly rejects excess files and catches content duplicates while allowing same metadata', async () => {
    const existing = Array.from({ length: 8 }, (_, idx) =>
      makeFile(`sheet_${idx}.jpg`, 'image/jpeg', 2048 + idx),
    )

    const tooMany = await validateBatchFileAddition(existing, [
      makeFile('extra_1.jpg', 'image/jpeg', 2048),
      makeFile('extra_2.jpg', 'image/jpeg', 2049),
      makeFile('extra_3.jpg', 'image/jpeg', 2050),
    ])
    expect(tooMany.ok).toBe(false)
    if (!tooMany.ok) {
      expect(tooMany.error).toContain('осталось мест: 2')
    }

    // Renamed copy of sheet_0.jpg (identical content + size) must still be caught as duplicate.
    const renamedDupResult = await validateBatchFileAddition(existing, [
      makeFile('copied_name.jpg', 'image/jpeg', 2048, 'sheet_0.jpg'),
    ])
    expect(renamedDupResult.ok).toBe(false)
    if (!renamedDupResult.ok) {
      expect(renamedDupResult.error).toContain('copied_name.jpg')
    }

    // Distinct camera bytes sharing identical name, size, and lastModified must be allowed.
    const firstShot = makeFile('IMG_0001.jpg', 'image/jpeg', 3072, 'shot-a')
    const secondShot = makeFile('IMG_0001.jpg', 'image/jpeg', 3072, 'shot-b')
    const distinctShots = await validateBatchFileAddition([firstShot], [secondShot])
    expect(distinctShots.ok).toBe(true)
  })

  it('formats sizes in KB/MB and creates demo sheets within requested limit', async () => {
    expect(formatFileSizeRu(512 * 1024)).toBe('512 КБ')
    expect(formatFileSizeRu(2.5 * 1024 * 1024)).toBe('2.5 МБ')

    const demos = await createDemoAuctionSheetFiles(2)
    expect(demos).toHaveLength(2)
    expect(demos[0]?.type).toBe('image/jpeg')
  })
})

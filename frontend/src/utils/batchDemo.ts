import { BATCH_MAX_FILES_PER_UPLOAD } from '@/utils/batchFiles'

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
  const limit = Math.max(
    0,
    Math.min(maxCount, BATCH_MAX_FILES_PER_UPLOAD, DEMO_SHEET_PRESETS.length),
  )
  const selected = DEMO_SHEET_PRESETS.slice(0, limit)
  return Promise.all(selected.map((preset) => renderDemoSheetFile(preset)))
}

import type { LotSummary, NormalizedSheet } from '@/types/api'

function stripXmlControlChars(value: string): string {
  let result = ''
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i)
    const isValidXmlChar =
      code === 0x09 || code === 0x0a || code === 0x0d || (code >= 0x20 && code !== 0x7f)
    if (isValidXmlChar) {
      result += value[i]
    }
  }
  return result
}

/**
 * Escapes arbitrary strings for safe interpolation into XML/SVG text and attributes.
 */
export function escapeXml(value: unknown): string {
  const raw = value === null || value === undefined ? '' : String(value)
  return stripXmlControlChars(raw)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

/**
 * Builds an inline SVG auction sheet scan preview so Lightbox works offline in mock mode.
 */
export function buildMockSheetSvgDataUrl(summary: LotSummary, sheet: NormalizedSheet): string {
  const title = escapeXml(`${summary.auction_house} #${summary.lot_number}`)
  const carName = escapeXml(`${summary.make} ${summary.model}`)
  const frame = escapeXml(summary.frame_id)
  const grade = escapeXml(summary.overall_grade)
  const yearAndEngine = escapeXml(`${summary.year ?? '—'} · ${summary.engine_cc ?? '—'} cc`)
  const strictness = escapeXml(sheet.auction_strictness_index.toFixed(2))
  const mileage = escapeXml(
    summary.mileage_km ? `${summary.mileage_km.toLocaleString('ru-RU')} km` : '—',
  )
  const defectsText = escapeXml(
    sheet.defects.map((defect) => `${defect.panel_id}:${defect.raw_code}`).join('  ·  ') ||
      'NO MAJOR DEFECTS',
  )
  const note1 = escapeXml(sheet.inspector_notes_raw[0] ?? '外装小キズ・補修跡')
  const note2 = escapeXml(sheet.inspector_notes_raw[1] ?? '機関・電装チェック済み')

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1220" viewBox="0 0 900 1220">
    <rect width="900" height="1220" fill="#F8F6EE"/>
    <rect x="34" y="34" width="832" height="1152" rx="12" fill="#FFFDF7" stroke="#22252A" stroke-width="3"/>
    <rect x="34" y="34" width="832" height="106" fill="#1F242D"/>
    <text x="64" y="88" font-family="ui-monospace, monospace" font-size="30" font-weight="700" fill="#FFFFFF">${title}</text>
    <text x="64" y="122" font-family="system-ui, sans-serif" font-size="18" fill="#D1D5DB">JAPANESE AUCTION INSPECTION SHEET · ${frame}</text>
    <rect x="726" y="48" width="114" height="78" rx="10" fill="#FF6B00"/>
    <text x="783" y="74" text-anchor="middle" font-family="system-ui, sans-serif" font-size="14" font-weight="700" fill="#FFF7ED">GRADE</text>
    <text x="783" y="114" text-anchor="middle" font-family="ui-monospace, monospace" font-size="38" font-weight="700" fill="#FFFFFF">${grade}</text>

    <rect x="64" y="168" width="772" height="148" rx="8" fill="#FFFFFF" stroke="#D1D5DB" stroke-width="2"/>
    <line x1="450" y1="168" x2="450" y2="316" stroke="#D1D5DB" stroke-width="2"/>
    <line x1="64" y1="242" x2="836" y2="242" stroke="#D1D5DB" stroke-width="2"/>
    <text x="84" y="196" font-family="system-ui, sans-serif" font-size="14" fill="#6B7280">MODEL / 車名</text>
    <text x="84" y="226" font-family="system-ui, sans-serif" font-size="24" font-weight="700" fill="#111827">${carName}</text>
    <text x="470" y="196" font-family="system-ui, sans-serif" font-size="14" fill="#6B7280">CHASSIS / 車台番号</text>
    <text x="470" y="226" font-family="ui-monospace, monospace" font-size="22" font-weight="700" fill="#111827">${frame}</text>
    <text x="84" y="270" font-family="system-ui, sans-serif" font-size="14" fill="#6B7280">ODOMETER / 走行距離</text>
    <text x="84" y="300" font-family="ui-monospace, monospace" font-size="22" font-weight="700" fill="#111827">${mileage}</text>
    <text x="470" y="270" font-family="system-ui, sans-serif" font-size="14" fill="#6B7280">ENGINE &amp; YEAR / 排気量</text>
    <text x="470" y="300" font-family="ui-monospace, monospace" font-size="22" font-weight="700" fill="#111827">${yearAndEngine}</text>

    <rect x="64" y="346" width="772" height="390" rx="8" fill="#FFFFFF" stroke="#D1D5DB" stroke-width="2"/>
    <text x="84" y="382" font-family="system-ui, sans-serif" font-size="16" font-weight="700" fill="#374151">EXTERIOR BODY DIAGRAM / 展開図</text>
    <rect x="240" y="420" width="420" height="230" rx="46" fill="#F3F4F6" stroke="#4B5563" stroke-width="3"/>
    <rect x="330" y="458" width="240" height="154" rx="18" fill="#E5E7EB" stroke="#6B7280" stroke-width="2"/>
    <line x1="330" y1="535" x2="570" y2="535" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="6 4"/>
    <text x="450" y="698" text-anchor="middle" font-family="ui-monospace, monospace" font-size="15" fill="#4B5563">${defectsText}</text>

    <rect x="64" y="766" width="772" height="384" rx="8" fill="#FFFFFF" stroke="#D1D5DB" stroke-width="2"/>
    <text x="84" y="804" font-family="system-ui, sans-serif" font-size="16" font-weight="700" fill="#374151">INSPECTOR NOTES / 注意事項</text>
    <text x="84" y="852" font-family="ui-monospace, monospace" font-size="20" fill="#111827">• ${note1}</text>
    <text x="84" y="896" font-family="ui-monospace, monospace" font-size="20" fill="#111827">• ${note2}</text>
    <text x="84" y="946" font-family="system-ui, sans-serif" font-size="18" fill="#4B5563">YUZU OCR VERIFIED · STRICTNESS ${strictness}</text>
    <text x="84" y="1116" font-family="ui-monospace, monospace" font-size="15" fill="#9CA3AF">MOCK SCAN PREVIEW FOR ${frame}</text>
  </svg>`

  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

import { describe, expect, it } from 'vitest'

import { buildMockLotDetail } from '@/api/mock/lotDetails'
import { buildMockSheetSvgDataUrl, escapeXml } from '@/api/mock/lotSheetSvg'
import { SEEDED_MOCK_LOTS } from '@/api/mock/lotsSeed'

describe('lotSheetSvg', () => {
  it('escapes XML special characters including single quotes and strips control chars', () => {
    expect(escapeXml(`<script>alert('xss' & "1")</script>\u0000\u0007`)).toBe(
      '&lt;script&gt;alert(&#39;xss&#39; &amp; &quot;1&quot;)&lt;/script&gt;',
    )
  })

  it('prevents raw SVG/script tag injection when lot fields contain markup', () => {
    const baseSummary = SEEDED_MOCK_LOTS[0]!
    const detail = buildMockLotDetail(baseSummary)

    const taintedSummary = {
      ...baseSummary,
      make: '</text><script>alert(1)</script><text>',
      model: `"onload='alert(2)'`,
      frame_id: `ZWE211<svg onload="evil()">`,
      overall_grade: `4.5'&"`,
    }
    const taintedSheet = {
      ...detail.passport,
      inspector_notes_raw: ['</text><foreignObject><body onload=alert(1)/></foreignObject>'],
    }

    const dataUrl = buildMockSheetSvgDataUrl(taintedSummary, taintedSheet)
    expect(dataUrl.startsWith('data:image/svg+xml;charset=utf-8,')).toBe(true)

    const decodedSvg = decodeURIComponent(dataUrl.replace('data:image/svg+xml;charset=utf-8,', ''))
    expect(decodedSvg).not.toContain('<script>')
    expect(decodedSvg).not.toContain('<foreignObject>')
    expect(decodedSvg).toContain('&lt;/text&gt;&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(decodedSvg).toContain('&quot;onload=&#39;alert(2)&#39;')
    expect(decodedSvg).toContain('ZWE211&lt;svg onload=&quot;evil()&quot;&gt;')
  })
})

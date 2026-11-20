import { describe, expect, it } from 'vitest'

import {
  isSafeRelativePath,
  sanitizeExternalUrl,
  sanitizeImageUrl,
  sanitizeNavigationHref,
} from '@/utils/url'

describe('url sanitizers', () => {
  describe('isSafeRelativePath', () => {
    it('allows single-slash app paths and rejects backslash/protocol-relative/external bypasses', () => {
      expect(isSafeRelativePath('/')).toBe(true)
      expect(isSafeRelativePath('/lots/123?tab=economics')).toBe(true)

      expect(isSafeRelativePath('/\\evil.com')).toBe(false)
      expect(isSafeRelativePath('/foo\\bar')).toBe(false)
      expect(isSafeRelativePath('//evil.com')).toBe(false)
      expect(isSafeRelativePath('///evil.com')).toBe(false)
      expect(isSafeRelativePath('https://evil.com/lots')).toBe(false)
      expect(isSafeRelativePath('javascript:alert(1)')).toBe(false)
      expect(isSafeRelativePath('/lots\n/evil')).toBe(false)
      expect(isSafeRelativePath('')).toBe(false)
    })
  })

  describe('sanitizeExternalUrl', () => {
    it('allows valid http and https URLs', () => {
      expect(sanitizeExternalUrl('https://auto.drom.ru/all/?q=Toyota')).toBe(
        'https://auto.drom.ru/all/?q=Toyota',
      )
      expect(sanitizeExternalUrl('  http://example.com/path  ')).toBe('http://example.com/path')
    })

    it('rejects javascript, vbscript, data, relative, and control-char URLs', () => {
      expect(sanitizeExternalUrl('javascript:alert(1)')).toBeUndefined()
      expect(sanitizeExternalUrl('JaVaScRiPt:alert(1)')).toBeUndefined()
      expect(sanitizeExternalUrl('java\tscript:alert(1)')).toBeUndefined()
      expect(sanitizeExternalUrl('vbscript:msgbox(1)')).toBeUndefined()
      expect(sanitizeExternalUrl('data:text/html,<script>alert(1)</script>')).toBeUndefined()
      expect(sanitizeExternalUrl('//evil.example/phish')).toBeUndefined()
      expect(sanitizeExternalUrl('/lots/123')).toBeUndefined()
      expect(sanitizeExternalUrl('')).toBeUndefined()
      expect(sanitizeExternalUrl(null)).toBeUndefined()
    })
  })

  describe('sanitizeNavigationHref', () => {
    it('allows single-slash relative paths and http(s) URLs', () => {
      expect(sanitizeNavigationHref('/lots/abc')).toBe('/lots/abc')
      expect(sanitizeNavigationHref('https://auto.drom.ru/')).toBe('https://auto.drom.ru/')
    })

    it('rejects protocol-relative, backslash, and dangerous scheme URLs', () => {
      expect(sanitizeNavigationHref('//evil.example')).toBeUndefined()
      expect(sanitizeNavigationHref('/\\evil.com')).toBeUndefined()
      expect(sanitizeNavigationHref('javascript:void(0)')).toBeUndefined()
      expect(sanitizeNavigationHref('data:text/html,hi')).toBeUndefined()
      expect(sanitizeNavigationHref('/lots/abc\nfoo')).toBeUndefined()
    })
  })

  describe('sanitizeImageUrl', () => {
    it('allows safe image sources including mock SVG data URLs', () => {
      expect(sanitizeImageUrl('/og-image.png')).toBe('/og-image.png')
      expect(sanitizeImageUrl('/api/v1/lots/123/media/thumbnail')).toBe(
        '/api/v1/lots/123/media/thumbnail',
      )
      expect(sanitizeImageUrl('https://cdn.example.com/sheet.webp')).toBe(
        'https://cdn.example.com/sheet.webp',
      )
      expect(sanitizeImageUrl('blob:https://yuzu.local/1234')).toBe('blob:https://yuzu.local/1234')
      expect(sanitizeImageUrl('data:image/svg+xml;charset=utf-8,%3Csvg%3E%3C/svg%3E')).toBe(
        'data:image/svg+xml;charset=utf-8,%3Csvg%3E%3C/svg%3E',
      )
      expect(sanitizeImageUrl('data:image/png;base64,iVBORw0KGgo=')).toBe(
        'data:image/png;base64,iVBORw0KGgo=',
      )
    })

    it('rejects non-image data URIs, javascript URIs, backslash paths, and protocol-relative URLs', () => {
      expect(sanitizeImageUrl('data:text/html,<script>alert(1)</script>')).toBeUndefined()
      expect(sanitizeImageUrl('data:image/svg+xml;charset=utf-8,')).toBeUndefined()
      expect(sanitizeImageUrl('javascript:alert(1)')).toBeUndefined()
      expect(sanitizeImageUrl('file:///etc/passwd')).toBeUndefined()
      expect(sanitizeImageUrl('//evil.example/img.png')).toBeUndefined()
      expect(sanitizeImageUrl('/\\evil.com/img.png')).toBeUndefined()
    })
  })
})

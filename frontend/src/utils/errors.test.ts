import { describe, expect, it } from 'vitest'

import { ApiError } from '@/types/common'
import { extractApiErrorMessage, getErrorMessage } from '@/utils/errors'

describe('extractApiErrorMessage', () => {
  it('returns detail from ApiError when non-empty', () => {
    const err = new ApiError({
      type: 'about:blank',
      title: 'Bad Request',
      status: 400,
      detail: 'Неверный формат файла',
    })
    expect(extractApiErrorMessage(err, 'Fallback')).toBe('Неверный формат файла')
    expect(getErrorMessage(err, 'Fallback')).toBe('Неверный формат файла')
  })

  it('falls back to title/message when ApiError detail is empty or whitespace', () => {
    const emptyDetailErr = new ApiError({
      type: 'about:blank',
      title: 'Ошибка валидации',
      status: 422,
      detail: '',
    })
    expect(emptyDetailErr.message).toBe('Ошибка валидации')
    expect(extractApiErrorMessage(emptyDetailErr, 'Fallback')).toBe('Ошибка валидации')

    const whitespaceErr = new ApiError({
      type: 'about:blank',
      title: '   ',
      status: 500,
      detail: '   ',
    })
    expect(extractApiErrorMessage(whitespaceErr, 'Fallback')).toBe('Ошибка запроса')
  })

  it('handles standard Error and unknown thrown values cleanly', () => {
    expect(extractApiErrorMessage(new Error('Network timeout'), 'Fallback')).toBe('Network timeout')
    expect(extractApiErrorMessage(new Error('   '), 'Fallback')).toBe('Fallback')
    expect(extractApiErrorMessage('raw string', 'Fallback')).toBe('Fallback')
    expect(extractApiErrorMessage(null, 'Fallback')).toBe('Fallback')
  })
})

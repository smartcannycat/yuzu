import type { components } from '@/types/api.generated'

type Schemas = components['schemas']

export type InvalidParamDetail = Schemas['InvalidParamDetail']
export type ProblemDetail = Schemas['ProblemDetail']

export class ApiError extends Error {
  readonly status: number
  readonly title: string
  readonly detail: string
  readonly type: string
  readonly instance: string | null
  readonly invalidParams: InvalidParamDetail[]

  constructor(problem: ProblemDetail) {
    const normalizedDetail = problem.detail.trim()
    const normalizedTitle = problem.title.trim()
    super(normalizedDetail || normalizedTitle || 'Ошибка запроса')
    this.name = 'ApiError'
    this.status = problem.status
    this.title = problem.title
    this.detail = problem.detail
    this.type = problem.type
    this.instance = problem.instance ?? null
    this.invalidParams = problem.invalid_params ?? []
  }

  getFieldError(fieldName: string): string | undefined {
    return this.invalidParams.find((param) => param.name === fieldName)?.reason
  }
}

export interface InvalidParamDetail {
  name: string
  reason: string
}

export interface ProblemDetail {
  type: string
  title: string
  status: number
  detail: string
  instance?: string | null
  invalid_params?: InvalidParamDetail[]
  timestamp?: string
}

export class ApiError extends Error {
  readonly status: number
  readonly title: string
  readonly detail: string
  readonly type: string
  readonly instance: string | null
  readonly invalidParams: InvalidParamDetail[]

  constructor(problem: ProblemDetail) {
    super(problem.detail || problem.title)
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

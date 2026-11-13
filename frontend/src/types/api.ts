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

export interface UserRegisterRequest {
  email: string
  password: string
  name?: string | null
}

export interface UserLoginRequest {
  email: string
  password: string
}

export interface TokenRefreshRequest {
  refresh_token: string
}

export interface UserProfileResponse {
  user_id: string
  email: string
  name: string | null
  created_at: string
}

export interface AuthTokensResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in_sec: number
  user: UserProfileResponse
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

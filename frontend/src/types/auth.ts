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

import type { components } from '@/types/api.generated'

type Schemas = components['schemas']

export type UserRegisterRequest = Schemas['UserRegisterRequest']
export type UserLoginRequest = Schemas['UserLoginRequest']
export type UserProfileResponse = Schemas['UserProfileResponse']
export type AuthTokensResponse = Schemas['AuthTokensResponse']

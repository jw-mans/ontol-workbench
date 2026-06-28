import { api } from './client'
import type { User } from './types'

/** Текущий пользователь. 401 (не авторизован) пробрасывается вызывающему. */
export async function getMe(): Promise<User> {
  const { data } = await api.get<User>('/users/me')
  return data
}

/**
 * Вход. fastapi-users ждёт OAuth2-форму (x-www-form-urlencoded) с полями
 * `username` (у нас это email) и `password`; в ответ ставит httpOnly-cookie.
 */
export async function login(email: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username: email, password })
  await api.post('/auth/cookie/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
}

export async function logout(): Promise<void> {
  await api.post('/auth/cookie/logout')
}

export interface RegisterPayload {
  email: string
  password: string
  display_name?: string
}

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await api.post<User>('/auth/register', payload)
  return data
}

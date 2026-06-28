import { createContext, useContext, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AxiosError } from 'axios'

import * as authApi from '../api/auth'
import type { User } from '../api/types'

interface AuthContextValue {
  user: User | null
  /** Идёт первичная проверка сессии (GET /users/me). */
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (payload: authApi.RegisterPayload) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: authApi.getMe,
    retry: (count, error) => {
      // 401 — это "не залогинен", повторять бессмысленно.
      if (error instanceof AxiosError && error.response?.status === 401) {
        return false
      }
      return count < 2
    },
    staleTime: Infinity,
  })

  async function login(email: string, password: string) {
    await authApi.login(email, password)
    await queryClient.invalidateQueries({ queryKey: ['me'] })
  }

  async function register(payload: authApi.RegisterPayload) {
    await authApi.register(payload)
    await authApi.login(payload.email, payload.password)
    await queryClient.invalidateQueries({ queryKey: ['me'] })
  }

  async function logout() {
    await authApi.logout()
    queryClient.clear()
  }

  const value: AuthContextValue = {
    user: data ?? null,
    loading: isLoading,
    login,
    register,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within <AuthProvider>')
  }
  return ctx
}

import { AxiosError } from 'axios'

export function errorMessage(error: unknown, fallback = 'Что-то пошло не так'): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
    if (error.message) return error.message
  }
  if (error instanceof Error) return error.message
  return fallback
}

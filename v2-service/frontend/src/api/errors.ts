import { AxiosError } from 'axios'

/** Достать человекочитаемое сообщение из ошибки API (FastAPI `detail`). */
export function errorMessage(error: unknown, fallback = 'Что-то пошло не так'): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    // Ошибки валидации Pydantic приходят списком объектов.
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
    if (error.message) return error.message
  }
  if (error instanceof Error) return error.message
  return fallback
}

import axios, { AxiosError } from 'axios'

export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

// Сессия (JWT-cookie) истекла/отозвана: при 401 уводим на /login жёстким
// переходом — full reload надёжно сбрасывает кэш RQ, который иначе держит
// «старого» залогиненного пользователя. Пробник /users/me пропускаем (его 401
// обрабатывает useQuery в AuthProvider), гард по pathname — от петли на /login.
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const url = error.config?.url ?? ''
    const isMeProbe = url.endsWith('/users/me')
    if (
      error.response?.status === 401 &&
      !isMeProbe &&
      window.location.pathname !== '/login'
    ) {
      window.location.assign('/login')
    }
    return Promise.reject(error)
  },
)

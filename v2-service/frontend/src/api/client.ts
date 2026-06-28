import axios from 'axios'

// Один общий axios-инстанс. baseURL пустой — все пути относительные, а в dev
// их подхватывает прокси Vite (см. vite.config.ts) на тот же origin, поэтому
// httpOnly-cookie авторизации ходит автоматически. withCredentials оставляем на
// случай, если фронт и API всё же окажутся на разных origin.
export const api = axios.create({
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

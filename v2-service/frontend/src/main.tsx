import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { AxiosError } from 'axios'

import './index.css'
import './App.css'
import './ontol-lang/monaco-setup.ts'
import App from './App.tsx'
import { AuthProvider } from './auth/AuthContext.tsx'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      // 401 повторять бессмысленно (сессия истекла) — иначе «долгая загрузка»
      // из-за ретраев перед тем, как показать ошибку/увести на вход.
      retry: (count, error) =>
        error instanceof AxiosError && error.response?.status === 401
          ? false
          : count < 2,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)

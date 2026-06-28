import { useState, type SyntheticEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { errorMessage } from '../api/errors'

export default function RegisterPage() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/projects" replace />

  async function onSubmit(e: SyntheticEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await register({
        email,
        password,
        display_name: displayName.trim() || undefined,
      })
      navigate('/projects', { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Не удалось зарегистрироваться'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen">
      <form className="card auth-card" onSubmit={onSubmit}>
        <h1>Регистрация</h1>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>
        <label>
          Имя <span className="muted">(необязательно)</span>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            autoComplete="name"
          />
        </label>
        <label>
          Пароль
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={6}
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Создаём…' : 'Создать аккаунт'}
        </button>
        <p className="muted">
          Уже есть аккаунт? <Link to="/login">Войти</Link>
        </p>
      </form>
    </div>
  )
}

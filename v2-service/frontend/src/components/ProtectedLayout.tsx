import { Navigate, Outlet, Link } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

export default function ProtectedLayout() {
  const { user, loading, logout } = useAuth()

  if (loading) return <div className="center-screen muted">Загрузка…</div>
  if (!user) return <Navigate to="/login" replace />

  async function onLogout() {
    try {
      await logout()
    } catch {
      // сессия уже недействительна — всё равно уходим на вход
    }
    window.location.assign('/login')
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/projects" className="brand">
          Ontol
        </Link>
        <div className="spacer" />
        <span className="muted">{user.display_name || user.email}</span>
        <button type="button" className="btn" onClick={onLogout}>
          Выйти
        </button>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}

import { useState, type SyntheticEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as projectsApi from '../api/projects'
import { errorMessage } from '../api/errors'
import type { Project } from '../api/types'

export default function ProjectsPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.listProjects,
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['projects'] })

  const createMutation = useMutation({
    mutationFn: (n: string) => projectsApi.createProject(n),
    onSuccess: () => {
      setName('')
      setError(null)
      invalidate()
    },
    onError: (err) => setError(errorMessage(err)),
  })

  const renameMutation = useMutation({
    mutationFn: ({ id, n }: { id: string; n: string }) =>
      projectsApi.renameProject(id, n),
    onSuccess: invalidate,
    onError: (err) => setError(errorMessage(err)),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => projectsApi.deleteProject(id),
    onSuccess: invalidate,
    onError: (err) => setError(errorMessage(err)),
  })

  function onCreate(e: SyntheticEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (trimmed) createMutation.mutate(trimmed)
  }

  function onRename(p: Project) {
    const next = window.prompt('Новое имя проекта', p.name)
    if (next && next.trim() && next.trim() !== p.name) {
      renameMutation.mutate({ id: p.id, n: next.trim() })
    }
  }

  function onDelete(p: Project) {
    if (window.confirm(`Удалить проект «${p.name}» со всеми файлами?`)) {
      deleteMutation.mutate(p.id)
    }
  }

  return (
    <div className="page projects-page">
      <h1>Мои проекты</h1>

      <form className="row create-row" onSubmit={onCreate}>
        <input
          type="text"
          placeholder="Название нового проекта"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={100}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={createMutation.isPending || !name.trim()}
        >
          Создать
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {projectsQuery.isLoading && <p className="muted">Загрузка…</p>}
      {projectsQuery.isError && (
        <p className="error">{errorMessage(projectsQuery.error)}</p>
      )}

      {projectsQuery.data && projectsQuery.data.length === 0 && (
        <p className="muted empty">
          Пока нет ни одного проекта. Создайте первый выше.
        </p>
      )}

      <ul className="project-list">
        {projectsQuery.data?.map((p) => (
          <li key={p.id} className="card project-item">
            <Link to={`/projects/${p.id}`} className="project-link">
              {p.name}
            </Link>
            <div className="spacer" />
            <button type="button" className="btn" onClick={() => onRename(p)}>
              Переименовать
            </button>
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => onDelete(p)}
            >
              Удалить
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

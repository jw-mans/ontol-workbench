import { useState, type SyntheticEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as projectsApi from '../api/projects'
import { errorMessage } from '../api/errors'
import type { Project } from '../api/types'
import { ConfirmDialog, PromptDialog } from '../components/Modal'

export default function ProjectsPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [renaming, setRenaming] = useState<Project | null>(null)
  const [deleting, setDeleting] = useState<Project | null>(null)

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
    setRenaming(p)
  }

  function onDelete(p: Project) {
    setDeleting(p)
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

      {renaming && (
        <PromptDialog
          title="Переименовать проект"
          initialValue={renaming.name}
          confirmLabel="Сохранить"
          onCancel={() => setRenaming(null)}
          onSubmit={(next) => {
            if (next !== renaming.name) {
              renameMutation.mutate({ id: renaming.id, n: next })
            }
            setRenaming(null)
          }}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title="Удалить проект?"
          message={`Проект «${deleting.name}» будет удалён со всеми файлами. Действие необратимо.`}
          onCancel={() => setDeleting(null)}
          onConfirm={() => {
            deleteMutation.mutate(deleting.id)
            setDeleting(null)
          }}
        />
      )}
    </div>
  )
}

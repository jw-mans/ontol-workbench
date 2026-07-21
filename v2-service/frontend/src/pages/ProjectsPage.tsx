import { useEffect, useMemo, useState, type SyntheticEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as projectsApi from '../api/projects'
import { errorMessage } from '../api/errors'
import type { Project } from '../api/types'
import { ConfirmDialog, PromptDialog } from '../components/Modal'
import { ProjectTree } from '../components/ProjectTree'
import { ContextMenu } from '../components/ContextMenu'

const ENGINE_LABEL: Record<string, string> = {
  v1: 'Ontol v1',
  v3: 'TDL v3',
}

export default function ProjectsPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [engine, setEngine] = useState<'v1' | 'v3'>('v1')
  const [error, setError] = useState<string | null>(null)
  const [renaming, setRenaming] = useState<Project | null>(null)
  const [deleting, setDeleting] = useState<Project | null>(null)
  const [menu, setMenu] = useState<{ x: number; y: number; project: Project } | null>(null)

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.listProjects,
  })

  const roots = useMemo(
    () => (projectsQuery.data ?? []).filter((p) => p.parent_id === null),
    [projectsQuery.data],
  )

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['projects'] })

  const createMutation = useMutation({
    mutationFn: ({ n, eng }: { n: string; eng: 'v1' | 'v3' }) =>
      projectsApi.createProject(n, null, eng),
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
    if (trimmed) createMutation.mutate({ n: trimmed, eng: engine })
  }

  const handleProjectContextMenu = (project: Project, e: React.MouseEvent) => {
    e.preventDefault()
    setMenu({ x: e.clientX, y: e.clientY, project })
  }

  const menuItems = useMemo(() => {
    if (!menu) return []
    
    return [
      {
        label: 'Создать подпроект',
        onClick: () => {
          setName('')
          setEngine('v1')
          setMenu(null)
        },
      },
      {
        label: 'Переименовать',
        onClick: () => {
          setRenaming(menu.project)
          setMenu(null)
        },
      },
      {
        label: 'Удалить',
        danger: true,
        onClick: () => {
          setDeleting(menu.project)
          setMenu(null)
        },
      },
    ]
  }, [menu])

  // Скрыть контекстное меню при клике вне его
  useEffect(() => {
    if (menu) {
      const closeMenu = () => setMenu(null)
      document.addEventListener('click', closeMenu)
      return () => document.removeEventListener('click', closeMenu)
    }
  }, [menu])

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
        <div className="row seg-control">
          {(['v1', 'v3'] as const).map((e) => (
            <button
              key={e}
              type="button"
              className={`btn ${e === engine ? 'btn-primary' : ''}`}
              onClick={() => setEngine(e)}
            >
              {ENGINE_LABEL[e]}
            </button>
          ))}
        </div>
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

      {projectsQuery.data && roots.length === 0 && (
        <p className="muted empty">
          Пока нет ни одного проекта. Создайте первый выше.
        </p>
      )}

      <ProjectTree
        items={roots}
        getKey={(p) => p.id}
        getChildren={(p) =>
          (projectsQuery.data ?? []).filter((child) => child.parent_id === p.id)
        }
        renderRow={(p, isExpanded, toggle) => (
          <Link to={`/projects/${p.id}`} className="project-link">
            <button
              type="button"
              className="tree-toggle"
              onClick={(e) => {
                e.stopPropagation()
                toggle()
              }}
              style={{ visibility: isExpanded || (projectsQuery.data ?? []).some(c => c.parent_id === p.id) ? 'visible' : 'hidden' }}
            >
              {isExpanded ? '▼' : '▶'}
            </button>
            <span className="tree-row-name">
              {p.name}
            </span>
            <span className="badge engine-badge">
              {ENGINE_LABEL[p.engine] ?? p.engine}
            </span>
          </Link>
        )}
        onContextMenu={handleProjectContextMenu}
      />

      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          onClose={() => setMenu(null)}
          items={menuItems}
        />
      )}

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
          message={`Проект «${deleting.name}» будет удалён со всеми файлами и подпроектами. Действие необратимо.`}
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

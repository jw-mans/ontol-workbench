import { useMemo, useState, type SyntheticEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as projectsApi from '../api/projects'
import { errorMessage } from '../api/errors'
import type { Project } from '../api/types'
import { ConfirmDialog, PromptDialog } from '../components/Modal'

/** Проект с уже разложенными детьми — узел дерева. */
interface TreeNode extends Project {
  children: TreeNode[]
}

/** Плоский список проектов -> дерево по parent_id (дети отсортированы по имени). */
function buildTree(projects: Project[]): TreeNode[] {
  const byId = new Map<string, TreeNode>()
  projects.forEach((p) => byId.set(p.id, { ...p, children: [] }))

  const roots: TreeNode[] = []
  byId.forEach((node) => {
    const parent = node.parent_id ? byId.get(node.parent_id) : undefined
    if (parent) parent.children.push(node)
    else roots.push(node)
  })

  const sortRec = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.name.localeCompare(b.name))
    nodes.forEach((n) => sortRec(n.children))
  }
  sortRec(roots)
  return roots
}

interface NodeProps {
  node: TreeNode
  onAddChild: (p: Project) => void
  onRename: (p: Project) => void
  onDelete: (p: Project) => void
}

function ProjectNode({ node, onAddChild, onRename, onDelete }: NodeProps) {
  return (
    <li className="project-node">
      <div className="card project-item">
        <Link to={`/projects/${node.id}`} className="project-link">
          {node.name}
        </Link>
        <div className="spacer" />
        <button type="button" className="btn" onClick={() => onAddChild(node)}>
          + Подпроект
        </button>
        <button type="button" className="btn" onClick={() => onRename(node)}>
          Переименовать
        </button>
        <button
          type="button"
          className="btn btn-danger"
          onClick={() => onDelete(node)}
        >
          Удалить
        </button>
      </div>
      {node.children.length > 0 && (
        <ul className="project-list subtree" style={{ marginLeft: '1.5rem' }}>
          {node.children.map((child) => (
            <ProjectNode
              key={child.id}
              node={child}
              onAddChild={onAddChild}
              onRename={onRename}
              onDelete={onDelete}
            />
          ))}
        </ul>
      )}
    </li>
  )
}

export default function ProjectsPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [addingChildTo, setAddingChildTo] = useState<Project | null>(null)
  const [renaming, setRenaming] = useState<Project | null>(null)
  const [deleting, setDeleting] = useState<Project | null>(null)

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.listProjects,
  })

  const tree = useMemo(
    () => buildTree(projectsQuery.data ?? []),
    [projectsQuery.data],
  )

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['projects'] })

  const createMutation = useMutation({
    mutationFn: ({ n, parentId }: { n: string; parentId: string | null }) =>
      projectsApi.createProject(n, parentId),
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

  function onCreateRoot(e: SyntheticEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (trimmed) createMutation.mutate({ n: trimmed, parentId: null })
  }

  return (
    <div className="page projects-page">
      <h1>Мои проекты</h1>

      <form className="row create-row" onSubmit={onCreateRoot}>
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
        {tree.map((node) => (
          <ProjectNode
            key={node.id}
            node={node}
            onAddChild={setAddingChildTo}
            onRename={setRenaming}
            onDelete={setDeleting}
          />
        ))}
      </ul>

      {addingChildTo && (
        <PromptDialog
          title={`Новый подпроект в «${addingChildTo.name}»`}
          initialValue=""
          confirmLabel="Создать"
          onCancel={() => setAddingChildTo(null)}
          onSubmit={(childName) => {
            const trimmed = childName.trim()
            if (trimmed) {
              createMutation.mutate({ n: trimmed, parentId: addingChildTo.id })
            }
            setAddingChildTo(null)
          }}
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

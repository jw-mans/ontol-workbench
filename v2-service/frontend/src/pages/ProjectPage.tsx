import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as projectsApi from '../api/projects'
import * as filesApi from '../api/files'
import * as buildApi from '../api/build'
import type { BuildResult } from '../api/build'
import * as aiApi from '../api/ai'
import type { AIHierarchyResult } from '../api/ai'
import type { FileListItem } from '../api/types'
import { errorMessage } from '../api/errors'
import { downloadDataUrl, downloadText } from '../utils/download'
import OntolEditor from '../components/OntolEditor'
import { ConfirmDialog, PromptDialog } from '../components/Modal'
import { CreateFileDialog } from '../components/CreateFileDialog'
import { ContextMenu } from '../components/ContextMenu'

const AUTOSAVE_DEBOUNCE_MS = 800

export default function ProjectPage() {
  const { projectId = '' } = useParams()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [build, setBuild] = useState<BuildResult | null>(null)
  const [ai, setAi] = useState<AIHierarchyResult | null>(null)
  
  const [openIds, setOpenIds] = useState<string[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [creatingFile, setCreatingFile] = useState(false)
  const [renamingFile, setRenamingFile] = useState<FileListItem | null>(null)
  const [deletingFile, setDeletingFile] = useState<{
    id: string
    name: string
  } | null>(null)
  const [menu, setMenu] = useState<{
    x: number
    y: number
    file: FileListItem
  } | null>(null)

  // Какие опциональные фичи включены на бэкенде (напр. AI-генерация связей).
  const configQuery = useQuery({
    queryKey: ['config'],
    queryFn: aiApi.getConfig,
    staleTime: Infinity,
  })

  const projectQuery = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.getProject(projectId),
  })

  const filesQuery = useQuery({
    queryKey: ['files', projectId],
    queryFn: () => filesApi.listFiles(projectId),
  })

  const files = filesQuery.data
  const activeName = files?.find((f) => f.id === activeId)?.name ?? null
  // Движок активного файла: .tdl → v3 (Graphviz/SVG), иначе v1 (Ontol/PlantUML).
  const activeIsTdl = activeName?.endsWith('.tdl') ?? false

  if (files) {
    const ids = new Set(files.map((f) => f.id))
    const pruned = openIds.filter((id) => ids.has(id))
    if (pruned.length !== openIds.length) {
      setOpenIds(pruned)
    } else if (openIds.length === 0 && files.length > 0) {
      setOpenIds([files[0].id])
    }
  }
  
  if (activeId !== null && !openIds.includes(activeId)) {
    setActiveId(openIds.length > 0 ? openIds[openIds.length - 1] : null)
  } else if (activeId === null && openIds.length > 0) {
    setActiveId(openIds[openIds.length - 1])
  }

  function openFile(id: string) {
    setOpenIds((prev) => (prev.includes(id) ? prev : [...prev, id]))
    setActiveId(id)
  }

  function closeTab(id: string) {
    const idx = openIds.indexOf(id)
    const next = openIds.filter((x) => x !== id)
    setOpenIds(next)
    if (activeId === id) setActiveId(next[idx] ?? next[idx - 1] ?? null)
  }

  const fileQuery = useQuery({
    queryKey: ['file', projectId, activeId],
    queryFn: () => filesApi.getFile(projectId, activeId as string),
    enabled: !!activeId,
  })

  const [draft, setDraft] = useState('')
  const [syncedId, setSyncedId] = useState<string | null>(null)
  if (fileQuery.data && fileQuery.data.id !== syncedId) {
    setSyncedId(fileQuery.data.id)
    setDraft(fileQuery.data.content)
  }

  const saveMutation = useMutation({
    mutationFn: (content: string) =>
      filesApi.updateFile(projectId, activeId as string, content),
    onSuccess: (updated) => {
      setError(null)
      queryClient.setQueryData(['file', projectId, activeId], updated)
      queryClient.invalidateQueries({ queryKey: ['files', projectId] })
    },
    onError: (err) => setError(errorMessage(err)),
  })
  const { mutate: saveFile, mutateAsync: saveFileAsync } = saveMutation

  const createMutation = useMutation({
    mutationFn: (name: string) => filesApi.createFile(projectId, name),
    onSuccess: (created) => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['files', projectId] })
      openFile(created.id)
    },
    onError: (err) => setError(errorMessage(err)),
  })

  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      filesApi.renameFile(projectId, id, name),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['files', projectId] })
    },
    onError: (err) => setError(errorMessage(err)),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => filesApi.deleteFile(projectId, id),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['files', projectId] })
    },
    onError: (err) => setError(errorMessage(err)),
  })

  const buildMutation = useMutation({
    mutationFn: () =>
      buildApi.buildProject(projectId, activeName ?? undefined),
    onSuccess: (res) => {
      setError(null)
      setBuild(res)
    },
    onError: (err) => setError(errorMessage(err)),
  })

  const aiMutation = useMutation({
    mutationFn: () =>
      aiApi.generateHierarchy(projectId, activeName ?? undefined),
    onSuccess: (res) => {
      setError(null)
      setAi(res)
    },
    onError: (err) => setError(errorMessage(err)),
  })

  // Debounced-автосейв: PUT контента через паузу после остановки ввода.
  // Это синхронизация внешней системы (сервера) с состоянием — корректный
  // случай useEffect; setTimeout снимается при каждом изменении.
  useEffect(() => {
    if (!activeId || fileQuery.data === undefined) return
    if (draft === fileQuery.data.content) return
    const timer = setTimeout(() => saveFile(draft), AUTOSAVE_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [draft, activeId, fileQuery.data, saveFile])

  async function onBuild() {
    // Собираем сохранённую версию — сначала дожимаем pending-черновик.
    if (activeId && fileQuery.data && draft !== fileQuery.data.content) {
      try {
        await saveFileAsync(draft)
      } catch {
        return
      }
    }
    buildMutation.mutate()
  }

  function onCreateFile() {
    setCreatingFile(true)
  }

  if (projectQuery.isError) {
    return (
      <div className="page">
        <p className="error">
          {errorMessage(projectQuery.error, 'Проект не найден')}
        </p>
        <Link to="/projects">← К проектам</Link>
      </div>
    )
  }

  const dirty = fileQuery.data !== undefined && draft !== fileQuery.data.content
  const saveStatus = saveMutation.isPending
    ? 'Сохранение…'
    : dirty
      ? 'Изменения не сохранены'
      : fileQuery.data
        ? 'Сохранено'
        : ''

  return (
    <div className="page project-page">
      <div className="row project-head">
        <Link to="/projects" className="muted">
          ← Проекты
        </Link>
        <h1>{projectQuery.data?.name ?? '…'}</h1>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="workspace">
        <aside className="file-explorer">
          <div className="explorer-head">
            <span className="explorer-title">Файлы</span>
            <button type="button" className="btn tab-add" onClick={onCreateFile}>
              + файл
            </button>
          </div>
          {files && files.length === 0 ? (
            <p className="muted empty-explorer">Файлов пока нет</p>
          ) : (
            <ul className="file-list-nav">
              {files?.map((f) => (
                <li
                  key={f.id}
                  className={`file-row ${f.id === activeId ? 'active' : ''}`}
                  onClick={() => openFile(f.id)}
                  onContextMenu={(e) => {
                    e.preventDefault()
                    setMenu({ x: e.clientX, y: e.clientY, file: f })
                  }}
                >
                  <span className="file-row-name">{f.name}</span>
                  <button
                    type="button"
                    className="file-row-menu"
                    title="Действия"
                    onClick={(e) => {
                      e.stopPropagation()
                      const r = e.currentTarget.getBoundingClientRect()
                      setMenu({ x: r.left, y: r.bottom, file: f })
                    }}
                  >
                    ⋮
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <div className="editor-area">
          {openIds.length > 0 && (
            <div className="tabs">
              {openIds.map((id) => {
                const f = files?.find((x) => x.id === id)
                if (!f) return null
                return (
                  <div
                    key={id}
                    className={`tab ${id === activeId ? 'active' : ''}`}
                  >
                    <button
                      type="button"
                      className="tab-name"
                      onClick={() => setActiveId(id)}
                    >
                      {f.name}
                    </button>
                    <button
                      type="button"
                      className="tab-close"
                      title="Закрыть вкладку"
                      onClick={() => closeTab(id)}
                    >
                      ×
                    </button>
                  </div>
                )
              })}
            </div>
          )}

          {activeId ? (
            <div className="editor-pane">
              <div className="editor-host">
                <OntolEditor
                  value={draft}
                  onChange={setDraft}
                  language={activeIsTdl ? 'tdl' : 'ontol'}
                />
              </div>
              <div className="row editor-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={buildMutation.isPending}
                  onClick={onBuild}
                >
                  {buildMutation.isPending ? 'Собираем…' : 'Собрать'}
                </button>
                {configQuery.data?.ai_enabled && !activeIsTdl && (
                  <button
                    type="button"
                    className="btn"
                    disabled={aiMutation.isPending}
                    onClick={() => aiMutation.mutate()}
                    title="Предложить связи между терминами через LLM"
                  >
                    {aiMutation.isPending ? 'Генерация…' : 'Связи (AI)'}
                  </button>
                )}
                <span className="muted save-status">{saveStatus}</span>
              </div>
            </div>
          ) : (
            <p className="muted empty">
              {files && files.length === 0
                ? 'В проекте пока нет файлов. Создайте первый.'
                : 'Выберите файл слева, чтобы открыть.'}
            </p>
          )}
        </div>
      </div>

      {build && (
        <BuildPanel
          build={build}
          baseName={(activeName ?? 'diagram').replace(/\.(ontol|tdl)$/, '')}
          onClose={() => setBuild(null)}
        />
      )}

      {ai && (
        <AIPanel
          ai={ai}
          baseName={(activeName ?? 'hierarchy').replace(/\.ontol$/, '')}
          onClose={() => setAi(null)}
        />
      )}

      {creatingFile && (
        <CreateFileDialog
          onCancel={() => setCreatingFile(false)}
          onSubmit={(name) => {
            createMutation.mutate(name)
            setCreatingFile(false)
          }}
        />
      )}

      {renamingFile && (
        <PromptDialog
          title="Переименовать файл"
          initialValue={renamingFile.name}
          confirmLabel="Сохранить"
          onCancel={() => setRenamingFile(null)}
          onSubmit={(name) => {
            if (name !== renamingFile.name) {
              renameMutation.mutate({ id: renamingFile.id, name })
            }
            setRenamingFile(null)
          }}
        />
      )}

      {deletingFile && (
        <ConfirmDialog
          title="Удалить файл?"
          message={`Файл «${deletingFile.name}» будет удалён.`}
          onCancel={() => setDeletingFile(null)}
          onConfirm={() => {
            deleteMutation.mutate(deletingFile.id)
            setDeletingFile(null)
          }}
        />
      )}

      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          onClose={() => setMenu(null)}
          items={[
            {
              label: 'Переименовать',
              onClick: () => setRenamingFile(menu.file),
            },
            {
              label: 'Удалить',
              danger: true,
              onClick: () =>
                setDeletingFile({ id: menu.file.id, name: menu.file.name }),
            },
          ]}
        />
      )}
    </div>
  )
}

function AIPanel({
  ai,
  baseName,
  onClose,
}: {
  ai: AIHierarchyResult
  baseName: string
  onClose: () => void
}) {
  return (
    <section className="build-panel card">
      <div className="row build-head">
        <h2>Предложенные связи (AI)</h2>
        <div className="spacer" />
        <button type="button" className="btn" onClick={onClose}>
          Скрыть
        </button>
      </div>

      {ai.error && <p className="error">{ai.error}</p>}

      {ai.ok && ai.relationships.length === 0 && (
        <p className="muted">LLM не предложил новых связей.</p>
      )}

      {ai.snippet && (
        <>
          <p className="muted">
            Скопируйте фрагмент в свой `.ontol` (раздел hierarchy) — файл не
            изменён автоматически.
          </p>
          <pre className="code-block">{ai.snippet}</pre>
          <div className="row">
            <button
              type="button"
              className="btn"
              onClick={() => navigator.clipboard?.writeText(ai.snippet ?? '')}
            >
              Копировать
            </button>
            <button
              type="button"
              className="btn"
              onClick={() =>
                downloadText(`${baseName}.hierarchy.ontol`, ai.snippet ?? '')
              }
            >
              Скачать
            </button>
          </div>
        </>
      )}
    </section>
  )
}

function BuildPanel({
  build,
  baseName,
  onClose,
}: {
  build: BuildResult
  baseName: string
  onClose: () => void
}) {
  return (
    <section className="build-panel card">
      <div className="row build-head">
        <h2>Результат сборки</h2>
        <div className="spacer" />
        <button type="button" className="btn" onClick={onClose}>
          Скрыть
        </button>
      </div>

      {build.error && <p className="error">{build.error}</p>}

      {build.warnings.length > 0 && (
        <ul className="warnings">
          {build.warnings.map((w, i) => (
            <li key={i} className="muted">
              ⚠ {w}
            </li>
          ))}
        </ul>
      )}

      {/* ontol-v3: SVG-диаграмма (Graphviz). Рендерим инлайн — SVG отдаёт наш
          backend из dot, без скриптов. */}
      {build.svg && (
        <div className="diagram">
          <div
            className="svg-diagram"
            dangerouslySetInnerHTML={{ __html: build.svg }}
          />
          <div className="row">
            <button
              type="button"
              className="btn"
              onClick={() =>
                downloadText(`${baseName}.svg`, build.svg!, 'image/svg+xml')
              }
            >
              Скачать SVG
            </button>
          </div>
        </div>
      )}

      {build.png_url ? (
        <div className="diagram">
          <img src={build.png_url} alt="Диаграмма" />
          <div className="row">
            <button
              type="button"
              className="btn"
              onClick={() => downloadDataUrl(`${baseName}.png`, build.png_url!)}
            >
              Скачать PNG
            </button>
          </div>
        </div>
      ) : (
        !build.error &&
        !build.svg && (
          <p className="muted">
            PNG недоступен (нужен PlantUML-сервер) — JSON и PlantUML ниже.
          </p>
        )
      )}

      {build.json && (
        <details open>
          <summary>JSON</summary>
          <pre className="code-block">{build.json}</pre>
          <button
            type="button"
            className="btn"
            onClick={() =>
              downloadText(`${baseName}.json`, build.json!, 'application/json')
            }
          >
            Скачать JSON
          </button>
        </details>
      )}

      {build.puml && (
        <details>
          <summary>PlantUML</summary>
          <pre className="code-block">{build.puml}</pre>
          <button
            type="button"
            className="btn"
            onClick={() => downloadText(`${baseName}.puml`, build.puml!)}
          >
            Скачать .puml
          </button>
        </details>
      )}
    </section>
  )
}

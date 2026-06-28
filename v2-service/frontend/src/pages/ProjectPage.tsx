import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as projectsApi from '../api/projects'
import * as filesApi from '../api/files'
import * as buildApi from '../api/build'
import type { BuildResult } from '../api/build'
import { errorMessage } from '../api/errors'
import { downloadDataUrl, downloadText } from '../utils/download'
import OntolEditor from '../components/OntolEditor'

const AUTOSAVE_DEBOUNCE_MS = 800

export default function ProjectPage() {
  const { projectId = '' } = useParams()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [build, setBuild] = useState<BuildResult | null>(null)

  const projectQuery = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.getProject(projectId),
  })

  const filesQuery = useQuery({
    queryKey: ['files', projectId],
    queryFn: () => filesApi.listFiles(projectId),
  })

  // Активный файл выводим из списка: выбранный, если он ещё существует, иначе
  // первый. Так не нужен useEffect для авто-выбора.
  const files = filesQuery.data
  const activeId =
    selectedId && files?.some((f) => f.id === selectedId)
      ? selectedId
      : files?.[0]?.id ?? null
  const activeName = files?.find((f) => f.id === activeId)?.name ?? null

  const fileQuery = useQuery({
    queryKey: ['file', projectId, activeId],
    queryFn: () => filesApi.getFile(projectId, activeId as string),
    enabled: !!activeId,
  })

  // Сброс черновика при смене активного файла — корректировка состояния прямо
  // в рендере (паттерн react.dev/you-might-not-need-an-effect), а не в эффекте.
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
      setSelectedId(created.id)
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
    const name = window.prompt('Имя файла (расширение .ontol добавится само)')
    if (name && name.trim()) createMutation.mutate(name.trim())
  }

  function onDeleteFile(id: string, name: string) {
    if (window.confirm(`Удалить файл «${name}»?`)) {
      deleteMutation.mutate(id)
    }
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

      <div className="tabs">
        {filesQuery.data?.map((f) => (
          <div key={f.id} className={`tab ${f.id === activeId ? 'active' : ''}`}>
            <button
              type="button"
              className="tab-name"
              onClick={() => setSelectedId(f.id)}
            >
              {f.name}
            </button>
            <button
              type="button"
              className="tab-close"
              title="Удалить файл"
              onClick={() => onDeleteFile(f.id, f.name)}
            >
              ×
            </button>
          </div>
        ))}
        <button type="button" className="btn tab-add" onClick={onCreateFile}>
          + файл
        </button>
      </div>

      {filesQuery.data && filesQuery.data.length === 0 && (
        <p className="muted empty">В проекте пока нет файлов. Создайте первый.</p>
      )}

      {activeId && (
        <div className="editor-pane">
          <div className="editor-host">
            <OntolEditor value={draft} onChange={setDraft} />
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
            <span className="muted save-status">{saveStatus}</span>
          </div>
        </div>
      )}

      {build && (
        <BuildPanel
          build={build}
          baseName={(activeName ?? 'diagram').replace(/\.ontol$/, '')}
          onClose={() => setBuild(null)}
        />
      )}
    </div>
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
        !build.error && (
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

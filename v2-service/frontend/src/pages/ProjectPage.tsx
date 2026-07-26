import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as projectsApi from '../api/projects'
import * as filesApi from '../api/files'
import * as buildApi from '../api/build'
import type { BuildResult } from '../api/build'
import * as aiApi from '../api/ai'
import type { AIHierarchyResult } from '../api/ai'
import * as ontologiesApi from '../api/ontologies'
import type { SemanticCheckResult } from '../api/ontologies'
import type { Directory, FileListItem } from '../api/types'
import { errorMessage } from '../api/errors'
import { downloadDataUrl, downloadText } from '../utils/download'
import OntolEditor from '../components/OntolEditor'
import { ConfirmDialog, PromptDialog } from '../components/Modal'
import { CreateFileDialog } from '../components/CreateFileDialog'
import { CreateDirectoryDialog } from '../components/CreateDirectoryDialog'
import { ContextMenu } from '../components/ContextMenu'
import { FileTree } from '../components/FileTree'
import { buildFileTree } from '../utils/fileTree'
import { OntologyConstructor } from '../components/OntologyConstructor'

const AUTOSAVE_DEBOUNCE_MS = 800

export default function ProjectPage() {
  const { projectId = '' } = useParams()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [build, setBuild] = useState<BuildResult | null>(null)
  const [ai, setAi] = useState<AIHierarchyResult | null>(null)
  const [analysis, setAnalysis] = useState<SemanticCheckResult | null>(null)
  
  const [openIds, setOpenIds] = useState<string[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [menu, setMenu] = useState<{
    x: number
    y: number
    item: { type: 'file'; id: string; name: string } | { type: 'folder'; id?: string; name: string }
  } | null>(null)
  
  const [creatingFile, setCreatingFile] = useState(false)
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [creatingFolderParentId, setCreatingFolderParentId] = useState<string | null>(null)
  const [renamingItem, setRenamingItem] = useState<{ type: 'file' | 'folder'; id: string; name: string } | null>(null)
  const [deletingItem, setDeletingItem] = useState<
    | { type: 'file'; id: string; name: string }
    | { type: 'folder'; id: string; name: string }
    | null
  >(null)
  const [menuJustOpened, setMenuJustOpened] = useState(false)
  const [ontologyConstructorOpen, setOntologyConstructorOpen] = useState(false)
  const [ontologyConstructorDirectoryId, setOntologyConstructorDirectoryId] = useState<string | null>(null)
  
  // Список закрытых вкладок (не отображаем их, даже если файл существует)
  const [closedIds, setClosedIds] = useState<Set<string>>(new Set())

  // Проверяем параметр ?import=true из URL
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

  const engine = projectQuery.data?.engine ?? 'v1'

  const files = filesQuery.data
  const activeName = files?.find((f) => f.id === activeId)?.name ?? null
  const activeIsTdl = activeName?.endsWith('.tdl') ?? false

  // Фильтруем openIds, исключая закрытые вкладки
  const effectiveOpenIds = useMemo(() => {
    return openIds.filter(id => !closedIds.has(id))
  }, [openIds, closedIds])
  
  // Если активная вкладка была закрыта, сбросить её
  if (activeId && closedIds.has(activeId)) {
    setActiveId(null)
  }
  
  // Проверяем, какие файлы остались в проекте
  if (files) {
    const fileIds = new Set(files.map((f) => f.id))
    // Очищаем closedIds от файлов, которых больше нет в проекте
    const validClosedIds = new Set(closedIds)
    fileIds.forEach(id => validClosedIds.delete(id))
    if (validClosedIds.size !== closedIds.size) {
      setClosedIds(validClosedIds)
    }
  }

  function openFile(id: string) {
    // Удаляем из закрытых, если был закрыт
    if (closedIds.has(id)) {
      const newClosed = new Set(closedIds)
      newClosed.delete(id)
      setClosedIds(newClosed)
    }
    setOpenIds((prev) => (prev.includes(id) ? prev : [...prev, id]))
    setActiveId(id)
  }

  function closeTab(id: string) {
    // Добавляем в закрытые
    setClosedIds(prev => new Set(prev).add(id))
    // Удаляем из openIds
    const newOpenIds = openIds.filter(x => x !== id)
    setOpenIds(newOpenIds)
    // Сбросить activeId, если закрыт текущий файл
    if (activeId === id) {
      // Если остались другие файлы, выбрать последний, иначе сбросить
      setActiveId(newOpenIds.length > 0 ? newOpenIds[newOpenIds.length - 1] : null)
    }
  }

  // Получить уникальное имя файла с путём, если есть дубликаты во вкладках
  const getUniqueFileName = (fileId: string, fileName: string): string => {
    const file = files?.find((f) => f.id === fileId)
    if (!file) return fileName
    
    // Если нет directory_id, возвращаем только имя
    if (!file.directory_id) return fileName
    
    // Ищем другие ОТКРЫТЫЕ файлы с таким же именем (используем effectiveOpenIds)
    const otherOpenFilesWithSameName = effectiveOpenIds
      .filter((id) => id !== fileId)
      .map((id) => files?.find((f) => f.id === id))
      .filter((f): f is FileListItem => !!f && f.name === fileName)
    
    const hasOpenDuplicates = otherOpenFilesWithSameName.length > 0
    
    // Если есть дубликаты во вкладках, показываем полный путь
    if (hasOpenDuplicates) {
      // Найти путь к директории
      const rootDir = projectDirectories.data?.find((d) => d.id === file.directory_id)
      if (rootDir) {
        // Построить путь от корня к директории
        const pathParts: string[] = []
        let currentDir: Directory | undefined = rootDir
        while (currentDir !== undefined) {
          pathParts.unshift(currentDir!.name)
          if (currentDir!.parent_directory_id) {
            currentDir = projectDirectories.data?.find((d) => d.id === currentDir!.parent_directory_id)
          } else {
            currentDir = undefined
          }
        }
        if (pathParts.length > 0) {
          return `${pathParts.join('/')}/${fileName}`
        }
      }
    }
    
    // Возвращаем только имя файла (короткое)
    return fileName
  }

  // Загрузка директорий
  const projectDirectories = useQuery({
    queryKey: ['directories', projectId],
    queryFn: () => filesApi.listAllDirectories(projectId),
    enabled: !!projectId,
  })

  // Построить дерево файлов из плоского списка
  const fileTree = useMemo(() => {
    if (!files) return null
    const tree = buildFileTree(files, projectQuery.data?.name ?? 'Проект', projectDirectories.data)
    return tree
  }, [files, projectQuery.data?.name, projectDirectories.data])

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
    mutationFn: ({ name, directoryId }: { name: string; directoryId?: string | null }) =>
      filesApi.createFile(projectId, name, '', directoryId),
    onSuccess: (created) => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['files', projectId] })
      openFile(created.id)
    },
    onError: (err) => {
      console.error('Mutation onError for createFile:', err)
      setError(errorMessage(err))
    },
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

  const deleteFolderMutation = useMutation({
    mutationFn: (id: string) => filesApi.deleteDirectory(projectId, id),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['files', projectId] })
      queryClient.invalidateQueries({ queryKey: ['directories', projectId] })
    },
    onError: (err) => setError(errorMessage(err)),
  })

  const renameDirectoryMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      filesApi.renameDirectory(projectId, id, name),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['directories', projectId] })
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

  // Анализ диаграммы относительно корневой директории (для TDL файлов)
  const analysisMutation = useMutation({
    mutationFn: async () => {
      // Получаем directory_id для активного файла
      const file = files?.find((f) => f.id === activeId)
      if (!file) {
        throw new Error('Файл не найден')
      }
      console.log('Analysis: Active file', { fileId: activeId, fileName: file.name, directoryId: file.directory_id })
      // Для корневых файлов (directory_id === null) не передаем его
      // Backend обработает это как "корневая директория"
      return ontologiesApi.analyzeDiagramInDirectory(projectId, file.directory_id || null)
    },
    onSuccess: (res) => {
      setError(null)
      setAnalysis(res)
    },
    onError: (err) => setError(errorMessage(err)),
  })

  // Debounced-автосейв: PUT контента через паузу после остановки ввода.
  useEffect(() => {
    if (!activeId || fileQuery.data === undefined) return
    if (draft === fileQuery.data.content) return
    const timer = setTimeout(() => saveFile(draft), AUTOSAVE_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [draft, activeId, fileQuery.data, saveFile])

  async function onBuild() {
    if (activeId && fileQuery.data && draft !== fileQuery.data.content) {
      try {
        await saveFileAsync(draft)
      } catch {
        return
      }
    }
    buildMutation.mutate()
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

  // Обработчик клика для открытия файла при двойном клике
  const handleFileDoubleClick = (id: string) => {
    openFile(id)
  }

  // Обработчик клика для открытия контекстного меню на пустом месте
  const handleEmptySpaceContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    // Для корневой папки id будет undefined
    setCreatingFolderParentId(null)
    setMenu({ x: e.clientX, y: e.clientY, item: { type: 'folder', name: '' } })
  }

  // Показать контекстное меню
  const showMenu = (
    e: React.MouseEvent,
    item: { type: 'file'; id: string; name: string } | { type: 'folder'; id?: string; name: string },
  ) => {
    e.preventDefault()
    e.stopPropagation()
    setMenuJustOpened(true)
    setMenu({ x: e.clientX, y: e.clientY, item })
    // Если кликнули на папку, запоминаем её id как родителя для новых элементов
    if (item.type === 'folder' && item.id) {
      setCreatingFolderParentId(item.id)
    } else {
      setCreatingFolderParentId(null)
    }
  }

  // Скрыть контекстное меню при клике вне его
  useEffect(() => {
    if (menu) {
      const closeMenu = (e: MouseEvent) => {
        // Игнорировать клик, который открыл меню
        if (menuJustOpened) {
          setMenuJustOpened(false)
          return
        }
        // Закрыть меню, если клик был вне контекстного меню
        if (!e.target || !(e.target as Element).closest('.context-menu')) {
          setMenu(null)
          // Сбросить parentId при закрытии меню
          setCreatingFolderParentId(null)
        }
      }
      document.addEventListener('mousedown', closeMenu)
      return () => document.removeEventListener('mousedown', closeMenu)
    } else {
      // Сбросить флаг, когда меню закрыто
      setMenuJustOpened(false)
    }
  }, [menu, menuJustOpened])

  const menuItems = useMemo(() => {
    if (!menu) return []
    
    const item = menu.item
    
    switch (item.type) {
      case 'file':
        const fileItem = item as { type: 'file'; id: string; name: string }
        return [
          { 
            label: 'Переименовать', 
            onClick: () => {
              setRenamingItem({ type: 'file', id: fileItem.id, name: fileItem.name })
              setMenu(null)
            }
          },
          { 
            label: 'Удалить', 
            danger: true,
            onClick: () => {
              setDeletingItem({ type: 'file', id: fileItem.id, name: fileItem.name })
              setMenu(null)
            }
          },
        ]
      case 'folder':
        const folderItem = item as { type: 'folder'; id?: string; name: string }
        // Если name пустой - кликнули на пустое место (корень)
        if (!folderItem.name || folderItem.name === '') {
          return [
            { 
              label: 'Создать файл', 
              onClick: () => {
                setCreatingFile(true)
                setMenu(null)
              }
            },
            { 
              label: 'Создать папку', 
              onClick: () => {
                setCreatingFolder(true)
                setMenu(null)
              }
            },
          ]
        }
        return [
          { 
            label: 'Переименовать', 
            onClick: () => {
              if (folderItem.id) {
                setRenamingItem({ type: 'folder', id: folderItem.id, name: folderItem.name })
              }
              setMenu(null)
            }
          },
          { 
            label: 'Создать файл', 
            onClick: () => {
              setCreatingFile(true)
              setMenu(null)
            }
          },
          { 
            label: 'Создать папку', 
            onClick: () => {
              setCreatingFolder(true)
              setMenu(null)
            }
          },
          { 
            label: 'Конструктор онтологий', 
            onClick: () => {
              if (folderItem.id) {
                setOntologyConstructorDirectoryId(folderItem.id)
                setOntologyConstructorOpen(true)
              }
              setMenu(null)
            }
          },
            { 
              label: 'Удалить', 
              danger: true,
              onClick: () => {
                if (folderItem.id) {
                  setDeletingItem({ type: 'folder', id: folderItem.id, name: folderItem.name })
                } else {
                  // Корневая папка не может быть удалена
                }
                setMenu(null)
              }
            },
        ]
      default:
        return []
    }
  }, [menu])

  return (
    <div className="page project-page">
      <div className="row project-head">
        <Link to="/projects" className="muted">
          ← Проекты
        </Link>
        <h1>{projectQuery.data?.name ?? '…'}</h1>
        <span className="badge engine-badge">{engine}</span>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="workspace">
        <aside className="file-explorer" onContextMenu={handleEmptySpaceContextMenu}>
          <div className="explorer-head">
            <span className="explorer-title">Файлы</span>
          </div>
          {fileTree && fileTree.children.length > 0 ? (
            <FileTree
              tree={fileTree}
              activeId={activeId}
              onOpenFile={openFile}
              onDoubleClick={handleFileDoubleClick}
              onContextMenu={showMenu}
            />
          ) : (
            <p className="muted empty-explorer">Файлов и папок пока нет. Кликните правой кнопкой мыши, чтобы создать первую папку или файл.</p>
          )}
        </aside>

        <div className="editor-area">
          {effectiveOpenIds.length > 0 && (
            <div className="tabs">
              {effectiveOpenIds.map((id) => {
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
                      {getUniqueFileName(id, f.name)}
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
                {activeIsTdl && (
                  <button
                    type="button"
                    className="btn"
                    disabled={analysisMutation.isPending}
                    onClick={() => analysisMutation.mutate()}
                    title="Анализировать диаграмму относительно корневой директории"
                  >
                    {analysisMutation.isPending ? 'Анализ…' : 'Анализ (директория)'}
                  </button>
                )}
                <span className="muted save-status">{saveStatus}</span>
              </div>
            </div>
          ) : (
            <p className="muted empty">
              {fileTree && fileTree.children.length === 0
                ? 'В проекте пока нет файлов и папок. Создайте первую через контекстное меню.'
                : 'Откройте любой файл слева, чтобы редактировать.'}
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

      {analysis && (
        <AnalysisPanel
          analysis={analysis}
          onClose={() => setAnalysis(null)}
        />
      )}

      {ontologyConstructorOpen && (
        <OntologyConstructorWrapper
          projectId={projectId}
          directoryId={ontologyConstructorDirectoryId}
          onClose={() => setOntologyConstructorOpen(false)}
          onSubmit={(_, fileId) => {
            setOntologyConstructorOpen(false)
            // Файл уже создан через buildOntology в конструкторе
            // Открыть его для редактирования
            if (fileId) {
              openFile(fileId)
            }
          }}
        />
      )}

      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          onClose={() => setMenu(null)}
          items={menuItems}
          skipCloseOnNextClick={menuJustOpened}
        />
      )}

      {creatingFile && (
        <CreateFileDialog
          engine={engine}
          projectId={projectId}
          parentId={creatingFolderParentId ?? undefined}
          onCancel={() => setCreatingFile(false)}
          onSubmit={(name, parentId) => {
            // Если есть parentId, передаём его в createFile
            const directoryId = parentId ?? undefined
            createMutation.mutate({ name, directoryId })
            setCreatingFile(false)
            // Сбросить parentId после успешного создания
            setCreatingFolderParentId(null)
          }}
        />
      )}

      {creatingFolder && (
        <CreateDirectoryDialog
          parentId={creatingFolderParentId ?? undefined}
          onCancel={() => {
            setCreatingFolder(false)
            setCreatingFolderParentId(null)
          }}
          onSubmit={(name, parentId) => {
            // Создать папку через API
            filesApi.createDirectory(projectId, name, parentId ?? null)
              .then(() => {
                setError(null)
                // Инвалидировать как файлы, так и директории
                queryClient.invalidateQueries({ queryKey: ['files', projectId] })
                queryClient.invalidateQueries({ queryKey: ['directories', projectId] })
                // Сбросить parentId после успешного создания
                setCreatingFolderParentId(null)
              })
              .catch((err) => {
                setError(errorMessage(err))
              })
            setCreatingFolder(false)
            setCreatingFolderParentId(null)
          }}
        />
      )}

      {renamingItem && renamingItem.type === 'file' && (
        <PromptDialog
          title="Переименовать файл"
          initialValue={renamingItem.name}
          confirmLabel="Сохранить"
          onCancel={() => setRenamingItem(null)}
          onSubmit={(name) => {
            if (name !== renamingItem.name) {
              renameMutation.mutate({ id: renamingItem.id, name })
            }
            setRenamingItem(null)
          }}
        />
      )}

      {renamingItem && renamingItem.type === 'folder' && (
        <PromptDialog
          title="Переименовать папку"
          initialValue={renamingItem.name}
          confirmLabel="Сохранить"
          onCancel={() => setRenamingItem(null)}
          onSubmit={(name) => {
            if (name !== renamingItem.name) {
              renameDirectoryMutation.mutate({ id: renamingItem.id, name })
            }
            setRenamingItem(null)
          }}
        />
      )}

      {deletingItem && deletingItem.type === 'file' && (
        <ConfirmDialog
          title="Удалить файл?"
          message={`Файл «${deletingItem.name}» будет удалён.`}
          onCancel={() => setDeletingItem(null)}
          onConfirm={() => {
            if (deletingItem.id) {
              deleteMutation.mutate(deletingItem.id)
            }
            setDeletingItem(null)
          }}
        />
      )}

      {deletingItem && deletingItem.type === 'folder' && (
        <ConfirmDialog
          title="Удалить папку?"
          message={`Папка «${deletingItem.name}» будет удалена (только если пустая).`}
          onCancel={() => setDeletingItem(null)}
          onConfirm={() => {
            if (deletingItem.id) {
              deleteFolderMutation.mutate(deletingItem.id)
            }
            setDeletingItem(null)
          }}
        />
      )}
    </div>
  )
}

function OntologyConstructorWrapper({
  projectId,
  directoryId,
  onClose,
  onSubmit,
}: {
  projectId: string
  directoryId: string | null
  onClose: () => void
  onSubmit: (fileName: string, fileId?: string) => void
}) {
  if (!directoryId) {
    return null
  }
  return (
    <OntologyConstructor
      projectId={projectId}
      directoryId={directoryId}
      onCancel={onClose}
      onSubmit={onSubmit}
    />
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
  const [ackPlanarity, setAckPlanarity] = useState(false)
  const [ackedBuild, setAckedBuild] = useState<BuildResult | null>(null)
  if (ackedBuild !== build) {
    setAckedBuild(build)
    setAckPlanarity(false)
  }

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
      
      {build.svg && (
        <div className="diagram">
          {build.planarity && !ackPlanarity && (
            <div className="planarity-banner">
              <div className="planarity-body">
                {build.planarity.subgraphs.length > 1 ? (
                  <>
                    <span>
                      ⚠ Граф не планарен: найдено подграфов-нарушителей — 
                      {build.planarity.count}
                    </span>
                    <ul className="planarity-list">
                      {build.planarity.subgraphs.map((s, i) => (
                        <li key={i}>
                          <strong>{s.kind ?? 'подграф Куратовского'}</strong>: 
                          {s.labels.join(', ')}
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <span>⚠ {build.planarity.message}</span>
                )}
              </div>
              <button
                type="button"
                className="btn"
                onClick={() => setAckPlanarity(true)}
              >
                Продолжить рисование
              </button>
            </div>
          )}
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

function AnalysisPanel({
  analysis,
  onClose,
}: {
  analysis: ontologiesApi.SemanticCheckResult
  onClose: () => void
}) {
  return (
    <section className="build-panel card">
      <div className="row build-head">
        <h2>Анализ диаграммы (директория)</h2>
        <div className="spacer" />
        <button type="button" className="btn" onClick={onClose}>
          Скрыть
        </button>
      </div>

      {analysis.error && <p className="error">{analysis.error}</p>}

      {analysis.warnings.length > 0 && (
        <ul className="warnings">
          {analysis.warnings.map((w, i) => (
            <li key={i} className="muted">
              ⚠ {w}
            </li>
          ))}
        </ul>
      )}
      
      {analysis.planarity && (
        <div className="planarity-info">
          <h3>Планарность</h3>
          {analysis.planarity.kind ? (
            <p className="muted">
              Тип нарушения: <strong>{analysis.planarity.kind}</strong>
            </p>
          ) : (
            <p className="muted">Граф планарен</p>
          )}
          
          {analysis.planarity.labels && analysis.planarity.labels.length > 0 && (
            <div className="row">
              <strong>Затронутые классы:</strong>
              <span>{analysis.planarity.labels.join(', ')}</span>
            </div>
          )}
          
          {analysis.planarity.subgraphs && analysis.planarity.subgraphs.length > 0 && (
            <div className="planarity-list">
              <strong>Подграфы-нарушители:</strong>
              {analysis.planarity.subgraphs.map((s, i) => (
                <div key={i} className="planarity-subgraph">
                  <span>{s.kind ?? 'подграф'}: {s.labels?.join(', ')}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}


import { useState, type SyntheticEvent } from 'react'

import { Modal } from './Modal'
import { OntologyConstructor } from './OntologyConstructor'

const ENGINE_EXT: Record<'v1' | 'v3', string> = {
  v1: '.ontol',
  v3: '.tdl',
}

/** Создание файла. Расширение задаётся языком проекта: v1 → .ontol, v3 → .tdl. */
export function CreateFileDialog({
  engine,
  projectId,
  parentId,
  onSubmit,
  onCancel,
  queryClient,
}: {
  engine: 'v1' | 'v3'
  projectId: string
  parentId?: string
  onSubmit: (fullName: string, parentId?: string, fileId?: string) => void
  onCancel: () => void
  queryClient?: any
}) {
  const [name, setName] = useState('')
  const [showConstructor, setShowConstructor] = useState(false)
  const ext = ENGINE_EXT[engine]
  // Убираем расширение, если пользователь ввёл его сам — добавим нужное.
  const base = name.trim().replace(/\.(ontol|tdl)$/i, '')

  function submit(e: SyntheticEvent) {
    e.preventDefault()
    if (base) onSubmit(base + ext, parentId, undefined)
  }

  // Если выбран конструктор онтологий для v3
  if (engine === 'v3' && showConstructor) {
    return (
      <OntologyConstructor
        projectId={projectId}
        directoryId={parentId ?? ''}
        onCancel={() => setShowConstructor(false)}
        onSubmit={async (fileName, fileId) => {
          setShowConstructor(false)
          // Передать результат родителю
          onSubmit(fileName, parentId, fileId)
          // Инвалидировать кэш файлов для обновления списка
          if (queryClient && fileId) {
            await queryClient.invalidateQueries({ queryKey: ['files', projectId] })
          }
        }}
        queryClient={queryClient}
      />
    )
  }

  return (
    <Modal title="Новый файл" onClose={onCancel}>
      <form onSubmit={submit} className="modal-form">
        <span className="modal-label">Имя файла</span>
        <input
          type="text"
          value={name}
          placeholder="например, main"
          onChange={(e) => setName(e.target.value)}
          maxLength={255}
          autoFocus
        />
        <span className="muted">
          Расширение <code>{ext}</code> — по языку проекта
        </span>
        {engine === 'v3' && (
          <button
            type="button"
            className="btn"
            onClick={() => setShowConstructor(true)}
            style={{ marginTop: '10px' }}
          >
            🏗 Конструктор онтологий
          </button>
        )}
        <div className="row modal-actions">
          <div className="spacer" />
          <button type="button" className="btn" onClick={onCancel}>
            Отмена
          </button>
          <button type="submit" className="btn btn-primary" disabled={!base}>
            Создать
          </button>
        </div>
      </form>
    </Modal>
  )
}

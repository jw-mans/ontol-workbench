import { useState, type SyntheticEvent } from 'react'

import { Modal } from './Modal'

const ENGINE_EXT: Record<'v1' | 'v3', string> = {
  v1: '.ontol',
  v3: '.tdl',
}

/** Создание файла. Расширение задаётся языком проекта: v1 → .ontol, v3 → .tdl. */
export function CreateFileDialog({
  engine,
  onSubmit,
  onCancel,
}: {
  engine: 'v1' | 'v3'
  onSubmit: (fullName: string) => void
  onCancel: () => void
}) {
  const [name, setName] = useState('')
  const ext = ENGINE_EXT[engine]
  // Убираем расширение, если пользователь ввёл его сам — добавим нужное.
  const base = name.trim().replace(/\.(ontol|tdl)$/i, '')

  function submit(e: SyntheticEvent) {
    e.preventDefault()
    if (base) onSubmit(base + ext)
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

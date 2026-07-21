import { useState, type SyntheticEvent } from 'react'

import { Modal } from './Modal'

/** Создание директории. */
export function CreateDirectoryDialog({
  parentId,
  onSubmit,
  onCancel,
}: {
  parentId?: string
  onSubmit: (name: string, parentId?: string) => void
  onCancel: () => void
}) {
  const [name, setName] = useState('')
  const base = name.trim().replace(/\//g, '/')

  function submit(e: SyntheticEvent) {
    e.preventDefault()
    if (base) onSubmit(base, parentId)
  }

  return (
    <Modal title="Новая папка" onClose={onCancel}>
      <form onSubmit={submit} className="modal-form">
        <span className="modal-label">Имя папки</span>
        <input
          type="text"
          value={name}
          placeholder="например, utils"
          onChange={(e) => setName(e.target.value)}
          maxLength={255}
          autoFocus
        />
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

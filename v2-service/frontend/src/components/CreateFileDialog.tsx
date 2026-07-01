import { useState, type SyntheticEvent } from 'react'

import { Modal } from './Modal'

const EXTS = ['.ontol', '.tdl'] as const
type Ext = (typeof EXTS)[number]

const LABEL: Record<Ext, string> = {
  '.ontol': 'Ontol v1 (.ontol)',
  '.tdl': 'TDL v3 (.tdl)',
}

/** Создание файла с выбором движка по расширению: .ontol (v1) или .tdl (v3). */
export function CreateFileDialog({
  onSubmit,
  onCancel,
}: {
  onSubmit: (fullName: string) => void
  onCancel: () => void
}) {
  const [name, setName] = useState('')
  const [ext, setExt] = useState<Ext>('.ontol')
  // Убираем расширение, если пользователь ввёл его сам — добавим выбранное.
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
        <div className="row seg-control">
          {EXTS.map((x) => (
            <button
              key={x}
              type="button"
              className={`btn ${x === ext ? 'btn-primary' : ''}`}
              onClick={() => setExt(x)}
            >
              {LABEL[x]}
            </button>
          ))}
        </div>
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

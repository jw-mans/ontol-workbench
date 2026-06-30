import {
  useEffect,
  useState,
  type ReactNode,
  type SyntheticEvent,
} from 'react'

/** Базовая модалка: затемнение, карточка по центру, закрытие по Esc и клику вне. */
export function Modal({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal card"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="modal-title">{title}</h2>
        {children}
      </div>
    </div>
  )
}

/** Подтверждение действия (замена window.confirm). */
export function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Удалить',
  danger = true,
  onConfirm,
  onCancel,
}: {
  title: string
  message?: string
  confirmLabel?: string
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <Modal title={title} onClose={onCancel}>
      {message && <p className="muted">{message}</p>}
      <div className="row modal-actions">
        <div className="spacer" />
        <button type="button" className="btn" onClick={onCancel}>
          Отмена
        </button>
        <button
          type="button"
          className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
          onClick={onConfirm}
          autoFocus
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  )
}

/** Ввод одной строки (замена window.prompt). */
export function PromptDialog({
  title,
  label,
  initialValue = '',
  placeholder,
  confirmLabel = 'OK',
  onSubmit,
  onCancel,
}: {
  title: string
  label?: string
  initialValue?: string
  placeholder?: string
  confirmLabel?: string
  onSubmit: (value: string) => void
  onCancel: () => void
}) {
  const [value, setValue] = useState(initialValue)
  const trimmed = value.trim()

  function submit(e: SyntheticEvent) {
    e.preventDefault()
    if (trimmed) onSubmit(trimmed)
  }

  return (
    <Modal title={title} onClose={onCancel}>
      <form onSubmit={submit} className="modal-form">
        {label && <span className="modal-label">{label}</span>}
        <input
          type="text"
          value={value}
          placeholder={placeholder}
          onChange={(e) => setValue(e.target.value)}
          maxLength={255}
          autoFocus
        />
        <div className="row modal-actions">
          <div className="spacer" />
          <button type="button" className="btn" onClick={onCancel}>
            Отмена
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!trimmed}
          >
            {confirmLabel}
          </button>
        </div>
      </form>
    </Modal>
  )
}

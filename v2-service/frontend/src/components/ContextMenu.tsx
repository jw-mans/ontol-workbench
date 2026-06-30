import { useEffect } from 'react'

export interface MenuItem {
  label: string
  onClick: () => void
  danger?: boolean
}

export function ContextMenu({
  x,
  y,
  items,
  onClose,
}: {
  x: number
  y: number
  items: MenuItem[]
  onClose: () => void
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="context-overlay"
      onClick={onClose}
      onContextMenu={(e) => {
        e.preventDefault()
        onClose()
      }}
      onWheel={onClose}
    >
      <ul
        className="context-menu card"
        style={{ top: y, left: x }}
        onClick={(e) => e.stopPropagation()}
      >
        {items.map((it) => (
          <li key={it.label}>
            <button
              type="button"
              className={`context-item ${it.danger ? 'danger' : ''}`}
              onClick={() => {
                it.onClick()
                onClose()
              }}
            >
              {it.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

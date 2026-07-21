import { useEffect, useRef } from 'react'

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
  skipCloseOnNextClick = false,
}: {
  x: number
  y: number
  items: MenuItem[]
  onClose: () => void
  skipCloseOnNextClick?: boolean
}) {
  const menuRef = useRef<HTMLUListElement>(null)
  const closeHandlerRef = useRef(onClose)
  
  // Update ref when onClose changes
  useEffect(() => {
    closeHandlerRef.current = onClose
  }, [onClose])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    
    let clickedOnce = false
    function handleClick(e: MouseEvent) {
      // Пропустить первый клик, если установлен флаг skipCloseOnNextClick
      if (skipCloseOnNextClick && !clickedOnce) {
        clickedOnce = true
        return
      }
      
      // Закрыть меню при клике на любой элемент, кроме самого меню
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        closeHandlerRef.current()
      }
    }
    document.addEventListener('mousedown', handleClick)
    
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', handleClick)
    }
  }, [onClose, skipCloseOnNextClick])

  return (
    <div
      className="context-overlay"
      style={{ position: 'fixed', inset: 0, zIndex: 110, pointerEvents: 'none' }}
    >
      <ul
        ref={menuRef}
        className="context-menu card"
        style={{ top: y, left: x, pointerEvents: 'auto' }}
        onClick={(e) => e.stopPropagation()}
      >
        {items.map((it) => (
          <li key={it.label}>
            <button
              type="button"
              className={`context-item ${it.danger ? 'danger' : ''}`}
              onClick={(e) => {
                e.stopPropagation()
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

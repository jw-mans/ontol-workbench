import { useState } from 'react'

interface TreeViewProps<T> {
  items: T[]
  getKey: (item: T) => string
  getChildren: (item: T) => T[]
  renderRow: (item: T, isExpanded: boolean, toggle: () => void) => React.ReactNode
  indentSize?: number
}

export function TreeView<T>({
  items,
  getKey,
  getChildren,
  renderRow,
  indentSize = 20,
}: TreeViewProps<T>) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const toggle = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const renderNode = (item: T, depth: number) => {
    const key = getKey(item)
    const children = getChildren(item)
    const isExpanded = expanded.has(key)
    const hasChildren = children.length > 0

    return (
      <div key={key} className="tree-node">
        <div
          className="tree-node-content"
          style={{ paddingLeft: depth * indentSize }}
        >
          <button
            type="button"
            className="tree-toggle"
            onClick={(e) => {
              e.stopPropagation()
              if (hasChildren) toggle(key)
            }}
            style={{ visibility: hasChildren ? 'visible' : 'hidden' }}
          >
            {isExpanded ? '▼' : '▶'}
          </button>
          {renderRow(item, isExpanded, () => hasChildren && toggle(key))}
        </div>
        {isExpanded && hasChildren && (
          <div className="tree-children">
            {children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="tree-view">
      {items.map((item) => renderNode(item, 0))}
    </div>
  )
}

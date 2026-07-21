import { useEffect, useState } from 'react'
import type { FileTreeNode } from '../api/types'

interface FileTreeProps {
  tree: FileTreeNode
  activeId: string | null
  onOpenFile: (id: string) => void
  onDoubleClick?: (id: string) => void
  onContextMenu?: (e: React.MouseEvent, item: { type: 'file'; id: string; name: string } | { type: 'folder'; name: string }) => void
  indentSize?: number
}

export function FileTree({
  tree,
  activeId,
  onOpenFile,
  onDoubleClick,
  onContextMenu,
  indentSize = 20,
}: FileTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    setExpanded(new Set([tree.name]))
  }, [tree.name])

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

  const renderNode = (node: FileTreeNode, depth: number, path: string): React.ReactNode => {
    const currentPath = path ? `${path}/${node.name}` : node.name
    // Директория: id === null (не файл), но есть directoryId (UUID папки)
    // Файл: id !== null (UUID файла)
    // Пустой корень (имя === '') не является ни файлом ни папкой
    const isEmptyRoot = node.name === ''
    const isDirectory = !isEmptyRoot && node.id === null && node.directoryId !== undefined
    const hasChildren = node.children.length > 0
    const isExpanded = expanded.has(currentPath)
    const isActive = node.id === activeId

    const handleClick = () => {
      if (isActive) return
      if (isDirectory && hasChildren) {
        toggle(currentPath)
      } else if (!isDirectory && node.id) {
        onOpenFile(node.id)
      }
    }

    const handleDoubleClick = () => {
      if (node.id && !isDirectory) {
        onDoubleClick?.(node.id)
      }
    }

    const handleContextMenu = (e: React.MouseEvent) => {
      e.preventDefault()
      if (onContextMenu) {
        const item = isDirectory
          ? { type: 'folder' as const, id: node.directoryId || node.id, name: node.name }
          : { type: 'file' as const, id: node.id!, name: node.name }
        onContextMenu(e, item)
      }
    }

    let firstFileType = '📁'
    if (isDirectory) {
      firstFileType = '📁'
    } else if (node.name.endsWith('.tdl')) {
      firstFileType = '📄'
    } else {
      firstFileType = '📄'
    }

    return (
      <div key={currentPath} className={`tree-node ${isActive ? 'active' : ''}`}>
        <div
          className="tree-node-content"
          style={{ paddingLeft: depth * indentSize }}
          onClick={handleClick}
          onDoubleClick={handleDoubleClick}
          onContextMenu={handleContextMenu}
        >
          <button
            type="button"
            className="tree-toggle"
            onClick={(e) => {
              e.stopPropagation()
              if (isDirectory && hasChildren) toggle(currentPath)
            }}
            style={{ visibility: hasChildren ? 'visible' : 'hidden' }}
          >
            {isDirectory && isExpanded ? '▼' : isDirectory ? '▶' : ''}
          </button>
          <span className="tree-row-name">
            {firstFileType} {node.name}
          </span>
        </div>
        {(isDirectory || node.id === null) && isExpanded && hasChildren && (
          <div className="tree-children">
            {node.children.map((child) => renderNode(child, depth + 1, currentPath))}
          </div>
        )}
      </div>
    )
  }

  const findFirstFile = (node: FileTreeNode): FileTreeNode | null => {
    for (const child of node.children) {
      if (child.id !== null) {
        return child
      }
      const found = findFirstFile(child)
      if (found) {
        return found
      }
    }
    return null
  }

  // Если корень имеет пустое имя, рендерим только его детей
  const renderChildrenOnly = tree.name === ''

  return (
    <div className="tree-view">
      {renderChildrenOnly
        ? tree.children.map((child) => renderNode(child, 0, ''))
        : renderNode(tree, 0, '')}
    </div>
  )
}

import type { Directory, FileListItem, FileTreeNode } from '../api/types'

export function buildFileTree(
  files: FileListItem[],
  projectName: string,
  directories?: Directory[],
): FileTreeNode {
  const root: FileTreeNode = {
    id: null,
    name: '',
    children: [],
    project_id: null,
    project_name: projectName,
  }

  if (!directories || directories.length === 0) {
    // Если нет директорий, просто добавляем файлы в корень
    for (const file of files) {
      if (file.directory_id === null) {
        const node: FileTreeNode = {
          id: file.id,
          name: file.name,
          children: [],
          project_id: null,
          project_name: projectName,
        }
        root.children.push(node)
      }
    }
    return root
  }

  // Создаём карту директорий для быстрого доступа по ID
  const directoryMap = new Map<string, Directory>()
  for (const dir of directories) {
    directoryMap.set(dir.id, dir)
  }

  // Сначала строим полную иерархию директорий
  // Создаём карту: parentId -> список директорий
  const directoryChildrenMap = new Map<string | null, Directory[]>()
  for (const dir of directories) {
    const parentId = dir.parent_directory_id
    if (!directoryChildrenMap.has(parentId)) {
      directoryChildrenMap.set(parentId, [])
    }
    directoryChildrenMap.get(parentId)?.push(dir)
  }

  // Рекурсивная функция для добавления директорий в дерево
  const addDirectoryToTree = (node: FileTreeNode, dir: Directory) => {
    const existing = node.children.find((c) => c.name === dir.name)
    if (existing) {
      // Если узел уже существует, обновляем его directoryId
      if (!existing.directoryId) {
        existing.directoryId = dir.id
      }
      return existing
    }

    // Директория имеет id=null, чтобы отличать от файлов
    const newNode: FileTreeNode = {
      id: null, // Директория не имеет id файла
      directoryId: dir.id, // Но имеет свой UUID в directoryId
      name: dir.name,
      children: [],
      project_id: null,
      project_name: null,
    }
    node.children.push(newNode)
    return newNode
  }

  const buildDirectorySubtree = (parentTreeNode: FileTreeNode, parentId: string | null) => {
    const children = directoryChildrenMap.get(parentId) || []
    
    for (const dir of children) {
      const dirNode = addDirectoryToTree(parentTreeNode, dir)
      // Рекурсивно добавляем дочерние директории
      buildDirectorySubtree(dirNode, dir.id)
    }
  }

  // Сначала добавляем корневые директории (у которых parent_directory_id === null)
  buildDirectorySubtree(root, null)

  // Создаём карту файлов по directory_id для эффективного добавления
  const filesByDirectory = new Map<string | null, FileListItem[]>()
  for (const file of files) {
    const dirId = file.directory_id
    if (!filesByDirectory.has(dirId)) {
      filesByDirectory.set(dirId, [])
    }
    filesByDirectory.get(dirId)?.push(file)
  }

  // Рекурсивная функция для добавления файлов в дерево
  const addFilesToTree = (node: FileTreeNode, directoryId: string | null) => {
    const filesInDir = filesByDirectory.get(directoryId)
    if (!filesInDir) return

    for (const file of filesInDir) {
      const existing = node.children.find((c) => c.name === file.name)
      if (existing) {
        // Файл уже добавлен (директория), обновляем id
        if (existing.id === null) {
          existing.id = file.id
        }
        continue
      }

      const fileNode: FileTreeNode = {
        id: file.id,
        name: file.name,
        children: [],
        project_id: null,
        project_name: projectName,
      }
      node.children.push(fileNode)
    }
  }

  // Добавляем файлы в соответствующие директории
  const addFilesRecursively = (node: FileTreeNode, directoryId: string | null) => {
    // Добавляем файлы в текущую директорию
    addFilesToTree(node, directoryId)

    // Рекурсивно обрабатываем дочерние директории
    const childDirs = directoryChildrenMap.get(directoryId)
    if (childDirs) {
      for (const dir of childDirs) {
        const childNode = node.children.find((c) => c.directoryId === dir.id)
        if (childNode) {
          addFilesRecursively(childNode, dir.id)
        }
      }
    }
  }

  addFilesRecursively(root, null)

  // Сортировка детей: сначала папки, потом файлы
  const sortTree = (node: FileTreeNode) => {
    node.children.sort((a, b) => {
      const aIsDir = a.directoryId !== undefined
      const bIsDir = b.directoryId !== undefined
      if (aIsDir && !bIsDir) return -1
      if (!aIsDir && bIsDir) return 1
      return a.name.localeCompare(b.name)
    })
    node.children.forEach(sortTree)
  }

  sortTree(root)
  return root
}

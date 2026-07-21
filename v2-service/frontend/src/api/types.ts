export interface User {
  id: string
  email: string
  is_active: boolean
  is_superuser: boolean
  is_verified: boolean
  display_name: string | null
}

export interface Project {
  id: string
  parent_id: string | null
  engine: 'v1' | 'v3'
  name: string
  created_at: string
  updated_at: string
}

/** Элемент списка файлов — без контента (FileListItem). */
export interface FileListItem {
  id: string
  name: string
  updated_at: string
  directory_id: string | null
}

/** Полный файл с контентом (FileRead). */
export interface FileDetail extends FileListItem {
  content: string
}

/** Узел дерева файлов. */
export interface FileTreeNode {
  id: string | null
  name: string
  children: FileTreeNode[]
  project_id: string | null
  project_name: string | null
  directoryId?: string // ID директории, если это папка
}

/** Директория. */
export interface Directory {
  id: string
  project_id: string
  parent_directory_id: string | null
  name: string
  created_at: string
}

/** Элемент списка файлов с поддержкой директории. */
export interface FileListItemWithDirectory extends FileListItem {
  directory_id: string | null
}

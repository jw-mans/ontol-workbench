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
  name: string
  created_at: string
  updated_at: string
}

/** Элемент списка файлов — без контента (FileListItem). */
export interface FileListItem {
  id: string
  name: string
  updated_at: string
}

/** Полный файл с контентом (FileRead). */
export interface FileDetail extends FileListItem {
  content: string
}

import { api } from './client'
import type { Directory, FileDetail, FileListItem } from './types'

export async function listFiles(projectId: string): Promise<FileListItem[]> {
  const { data } = await api.get<FileListItem[]>(`/projects/${projectId}/files`)
  return data
}

export async function listDirectories(
  projectId: string,
  parentId: string | null = null,
): Promise<Directory[]> {
  const { data } = await api.get<Directory[]>(`/projects/${projectId}/directories`, {
    params: { parent_id: parentId },
  })
  return data
}

// Рекурсивная функция для загрузки всех директорий с полной иерархией
export async function listAllDirectories(
  projectId: string,
  parentId: string | null = null,
): Promise<Directory[]> {
  const directChildren = await listDirectories(projectId, parentId)
  let allDirectories = [...directChildren]
  
  // Для каждой найденной директории загружаем её дочерние элементы
  for (const dir of directChildren) {
    const children = await listAllDirectories(projectId, dir.id)
    allDirectories = allDirectories.concat(children)
  }
  
  return allDirectories
}

export async function createFile(
  projectId: string,
  name: string,
  content = '',
  directoryId?: string | null,
): Promise<FileDetail> {
  const { data } = await api.post<FileDetail>(`/projects/${projectId}/files`, {
    name,
    content,
  }, {
    params: { directory_id: directoryId || undefined },
  })
  return data
}

export async function createDirectory(
  projectId: string,
  name: string,
  parentId: string | null = null,
): Promise<Directory> {
  const { data } = await api.post<Directory>(`/projects/${projectId}/directories`, {
    name,
  }, {
    params: { parent_id: parentId },
  })
  return data
}

export async function getFile(
  projectId: string,
  fileId: string,
): Promise<FileDetail> {
  const { data } = await api.get<FileDetail>(
    `/projects/${projectId}/files/${fileId}`,
  )
  return data
}

export async function updateFile(
  projectId: string,
  fileId: string,
  content: string,
): Promise<FileDetail> {
  const { data } = await api.put<FileDetail>(
    `/projects/${projectId}/files/${fileId}`,
    { content },
  )
  return data
}

export async function renameFile(
  projectId: string,
  fileId: string,
  name: string,
): Promise<FileDetail> {
  const { data } = await api.patch<FileDetail>(
    `/projects/${projectId}/files/${fileId}`,
    { name },
  )
  return data
}

export async function deleteFile(
  projectId: string,
  fileId: string,
): Promise<void> {
  await api.delete(`/projects/${projectId}/files/${fileId}`)
}

export async function renameDirectory(
  projectId: string,
  directoryId: string,
  name: string,
): Promise<Directory> {
  const { data } = await api.patch<Directory>(
    `/projects/${projectId}/directories/${directoryId}`,
    { name },
  )
  return data
}

export async function deleteDirectory(
  projectId: string,
  directoryId: string,
): Promise<void> {
  await api.delete(`/projects/${projectId}/directories/${directoryId}`)
}

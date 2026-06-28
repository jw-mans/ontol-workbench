import { api } from './client'
import type { FileDetail, FileListItem } from './types'

export async function listFiles(projectId: string): Promise<FileListItem[]> {
  const { data } = await api.get<FileListItem[]>(`/projects/${projectId}/files`)
  return data
}

export async function createFile(
  projectId: string,
  name: string,
  content = '',
): Promise<FileDetail> {
  const { data } = await api.post<FileDetail>(`/projects/${projectId}/files`, {
    name,
    content,
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

export async function deleteFile(
  projectId: string,
  fileId: string,
): Promise<void> {
  await api.delete(`/projects/${projectId}/files/${fileId}`)
}

import { api } from './client'
import type { Project } from './types'

export async function listProjects(): Promise<Project[]> {
  const { data } = await api.get<Project[]>('/projects')
  return data
}

export async function createProject(
  name: string,
  parentId: string | null = null,
  engine: 'v1' | 'v3' = 'v3',
): Promise<Project> {
  const { data } = await api.post<Project>('/projects', {
    name,
    parent_id: parentId,
    engine,
  })
  return data
}

export async function getProject(id: string): Promise<Project> {
  const { data } = await api.get<Project>(`/projects/${id}`)
  return data
}

export async function renameProject(id: string, name: string): Promise<Project> {
  const { data } = await api.patch<Project>(`/projects/${id}`, { name })
  return data
}

export async function deleteProject(id: string): Promise<void> {
  await api.delete(`/projects/${id}`)
}

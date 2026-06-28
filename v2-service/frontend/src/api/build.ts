import { api } from './client'

export interface BuildResult {
  ok: boolean
  json: string | null
  puml: string | null
  png_url: string | null
  warnings: string[]
  error: string | null
}

export async function buildProject(
  projectId: string,
  entry?: string,
): Promise<BuildResult> {
  const { data } = await api.post<BuildResult>(
    `/projects/${projectId}/build`,
    { entry: entry ?? null },
  )
  return data
}

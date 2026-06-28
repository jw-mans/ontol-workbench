import { api } from './client'

export interface BuildResult {
  ok: boolean
  json: string | null
  puml: string | null
  /** PNG как data:image/png;base64,… — годится прямо в <img src>. */
  png_url: string | null
  warnings: string[]
  error: string | null
}

/** Собрать проект. `entry` — точка входа; если не задана, сервер выберет сам. */
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

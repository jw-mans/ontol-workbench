import { api } from './client'

export interface AppConfig {
  ai_enabled: boolean
}

/** Публичные флаги бэкенда (какие опциональные фичи включены). */
export async function getConfig(): Promise<AppConfig> {
  const { data } = await api.get<AppConfig>('/config')
  return data
}

export interface AIRelationship {
  parent: string
  child: string
  relationship: string
  title: string | null
  bidirectional: boolean
  comment: string
}

export interface AIHierarchyResult {
  ok: boolean
  relationships: AIRelationship[]
  /** Готовый к вставке фрагмент `.ontol` (раздел hierarchy). */
  snippet: string | null
  error: string | null
}

/** Предложить связи (hierarchy) для проекта через LLM. Точка входа — `entry`. */
export async function generateHierarchy(
  projectId: string,
  entry?: string,
  model?: string,
): Promise<AIHierarchyResult> {
  const { data } = await api.post<AIHierarchyResult>(
    `/projects/${projectId}/ai/hierarchy`,
    { entry: entry ?? null, model: model ?? null },
  )
  return data
}

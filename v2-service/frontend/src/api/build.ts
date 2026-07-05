import { api } from './client'

export interface KuratowskiSubgraph {
  kind: string | null // 'K5' | 'K3,3'
  labels: string[] // «узловые» классы этого подграфа (5 для K5, 6 для K3,3)
}

export interface PlanarityInfo {
  kind: string | null // тип основного подграфа
  labels: string[] // объединение классов всех подграфов (для подсветки)
  message: string | null
  subgraphs: KuratowskiSubgraph[] // разбивка по каждому подграфу-нарушителю
  count: number // число найденных подграфов
}

export interface BuildResult {
  ok: boolean
  json: string | null
  puml: string | null
  png_url: string | null
  svg_url: string | null // ontol-v3: presigned-ссылка на SVG в MinIO
  svg: string | null // фолбэк: инлайн-SVG, если заливка в S3 не удалась
  planarity: PlanarityInfo | null // непланарный граф v3 (иначе null)
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

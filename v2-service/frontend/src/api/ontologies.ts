import { api } from './client'

// Схемы для онтологий
export interface OntologyConcept {
  name: string
  type: 'class' | 'interface' | 'data_type' | 'enum' | 'template'
  is_abstract?: boolean
  attributes?: string[]
  operations?: string[]
}

export interface OntologyRelation {
  relation_type: 'generalization' | 'association' | 'aggregation' | 'composition' | 'dependency' | 'realization'
  from_concept: string
  to_concept: string
  name?: string
  multiplicity_from?: string
  multiplicity_to?: string
}

export interface SemanticCheckResult {
  warnings: string[]
  planarity: {
    kind: string | null
    labels: string[]
    message: string | null
    subgraphs: { kind: string | null; labels: string[] }[]
    count: number
  } | null
  error: string | null
}

// Создание TDL файла из понятий и связей
export interface TDLFileCreateRequest {
  directory_id: string
  concepts: OntologyConcept[]
  relations: OntologyRelation[]
  file_name: string
  template?: 'empty' | 'from_relations'
}

// Создание онтологии (директории с файлами)
export interface OntologyBuildRequest {
  directory_id: string
  concepts: OntologyConcept[]
  relations: OntologyRelation[]
  file_name?: string
  template?: 'empty' | 'from_relations'
}

export interface OntologyBuildResponse {
  success: boolean
  message: string
  file_path?: string
  tdl_content?: string
  svg_content?: string
}

// Генерация TDL из понятий и связей
export async function generateTDL(request: TDLFileCreateRequest): Promise<string> {
  const { data } = await api.post<string>('/ontologies/generate_tdl', request)
  return data
}

// Проверка семантической целостности TDL-контента
export async function checkTDLContent(tdl_content: string): Promise<SemanticCheckResult> {
  const { data } = await api.post<SemanticCheckResult>('/ontologies/check', { tdl_content })
  return data
}

// Проверка семантической целостности директории
export async function checkDirectorySemantics(directory_id?: string | null): Promise<SemanticCheckResult> {
  console.log('API: checkDirectorySemantics', { directory_id })
  const { data } = await api.post<SemanticCheckResult>('/ontologies/check_directory', directory_id ? { directory_id } : {})
  return data
}

// Анализ диаграммы относительно корневой директории (для TDL файлов)
export async function analyzeDiagramInDirectory(projectId: string, directory_id?: string | null): Promise<SemanticCheckResult> {
  console.log('API: analyzeDiagramInDirectory', { projectId, directory_id })
  const { data } = await api.post<SemanticCheckResult>(
    `/projects/${projectId}/ontologies/analyze_directory`,
    directory_id ? { directory_id } : {}
  )
  return data
}

// Создание онтологии (с генерацией TDL и рендером)
export async function buildOntology(request: OntologyBuildRequest): Promise<OntologyBuildResponse> {
  const { data } = await api.post<OntologyBuildResponse>('/ontologies/build', request)
  return data
}

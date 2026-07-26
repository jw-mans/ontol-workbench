import { useState, useEffect, useMemo } from 'react'
import { Modal } from './Modal'
import * as ontologiesApi from '../api/ontologies'

// Пагинация для понятий
function ConceptPagination({
  currentPage,
  totalPages,
  onPageChange,
  totalCount
}: {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  totalCount: number
}) {
  return (
    <div className="pagination">
      <button
        type="button"
        className="btn"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 0}
      >
        ←
      </button>
      <span className="page-info">
        Страница {currentPage + 1} из {totalPages || 1}
      </span>
      <button
        type="button"
        className="btn"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage >= totalPages - 1}
      >
        →
      </button>
      <span className="page-info">
        Всего: {totalCount}
      </span>
    </div>
  )
}

// Пагинация для отношений
function RelationPagination({
  currentPage,
  totalPages,
  onPageChange,
  totalCount
}: {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  totalCount: number
}) {
  return (
    <div className="pagination">
      <button
        type="button"
        className="btn"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 0}
      >
        ←
      </button>
      <span className="page-info">
        Страница {currentPage + 1} из {totalPages || 1}
      </span>
      <button
        type="button"
        className="btn"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage >= totalPages - 1}
      >
        →
      </button>
      <span className="page-info">
        Всего: {totalCount}
      </span>
    </div>
  )
}

// Навигация по фазам
function PhaseSelector({
  currentPhase,
  onPhaseChange,
  selectedConceptsCount,
  availableConceptsCount
}: {
  currentPhase: 1 | 2
  onPhaseChange: (phase: 1 | 2) => void
  selectedConceptsCount: number
  availableConceptsCount: number
}) {
  return (
    <div className="phase-controls">
      <span
        className={`phase-indicator ${currentPhase === 1 ? 'active' : ''}`}
        onClick={() => onPhaseChange(1)}
      >
        Фаза 1: Понятия
      </span>
      <span className="phase-separator">/</span>
      <span
        className={`phase-indicator ${currentPhase === 2 ? 'active' : ''}`}
        onClick={() => onPhaseChange(2)}
        style={{ opacity: selectedConceptsCount === 0 ? 0.5 : 1, cursor: selectedConceptsCount === 0 ? 'not-allowed' : 'pointer' }}
      >
        Фаза 2: Отношения
      </span>
      <span className="phase-description">
        {currentPhase === 1
          ? `Доступно понятий: ${availableConceptsCount}`
          : `Выбрано понятий: ${selectedConceptsCount} | Выберите отношения между ними`}
      </span>
    </div>
  )
}

interface ConceptSelectorProps {
  availableConcepts: ontologiesApi.OntologyConcept[]
  selectedConcepts: string[] // имена выбранных понятий
  onSelect: (conceptName: string) => void
  onDeselect: (conceptName: string) => void
}

function ConceptSelector({
  availableConcepts,
  selectedConcepts,
  onSelect,
  onDeselect,
  showPagination,
  paginationProps
}: ConceptSelectorProps & {
  showPagination?: boolean
  paginationProps?: Parameters<typeof ConceptPagination>[0]
}) {
  return (
    <div className="concept-selector card">
      <div className="row">
        <h3>Доступные понятия</h3>
      </div>
      
      <div className="concept-list">
        {availableConcepts.map(concept => {
          const isSelected = selectedConcepts.includes(concept.name)
          return (
            <div 
              key={concept.name} 
              className={`concept-item ${isSelected ? 'selected' : ''}`}
              onClick={() => isSelected ? onDeselect(concept.name) : onSelect(concept.name)}
            >
              <div className="concept-name">{concept.name}</div>
              <div className="concept-type">{concept.type}</div>
            </div>
          )
        })}
        
        {availableConcepts.length === 0 && (
          <p className="muted">Нет доступных понятий</p>
        )}
      </div>
      
      {showPagination && paginationProps && (
        <div className="card">
          <ConceptPagination {...paginationProps} />
        </div>
      )}
    </div>
  )
}

interface SelectedConceptsListProps {
  selectedConcepts: ontologiesApi.OntologyConcept[]
  onDelete: (conceptName: string) => void
}

function SelectedConceptsList({ selectedConcepts, onDelete, totalCount }: SelectedConceptsListProps & { totalCount?: number }) {
  return (
    <div className="selected-concepts-list card">
      <div className="row">
        <h3>Выбранные понятия ({selectedConcepts.length})</h3>
        {totalCount !== undefined && <span className="muted">из {totalCount} понятий</span>}
      </div>
      
      {selectedConcepts.map((concept) => (
        <div key={concept.name} className="selected-concept-item">
          <div className="concept-info">
            <span className="concept-name">{concept.name}</span>
            <span className="concept-type">{concept.type}</span>
          </div>
          <div className="concept-controls">
            <button 
              type="button" 
              className="btn btn-small"
              onClick={() => onDelete(concept.name)}
            >
              Удалить
            </button>
          </div>
        </div>
      ))}
      
      {selectedConcepts.length === 0 && (
        <p className="muted">Нет выбранных понятий. Выберите понятия слева.</p>
      )}
    </div>
  )
}

interface RelationSelectorProps {
  availableRelations: ontologiesApi.OntologyRelation[]
  selectedConceptNames: string[]
  selectedRelations: string[] // строки "from_concept->to_concept"
  onSelect: (relation: ontologiesApi.OntologyRelation) => void
  onDeselect: (relation: ontologiesApi.OntologyRelation) => void
}

function RelationSelector({
  availableRelations,
  selectedConceptNames,
  selectedRelations,
  onSelect,
  onDeselect,
  showPagination,
  paginationProps
}: RelationSelectorProps & {
  showPagination?: boolean
  paginationProps?: Parameters<typeof RelationPagination>[0]
}) {
  // Фильтруем связи, которые связывают только выбранные понятия
  const filteredRelations = useMemo(() => availableRelations.filter(rel => 
    selectedConceptNames.includes(rel.from_concept) && 
    selectedConceptNames.includes(rel.to_concept)
  ), [availableRelations, selectedConceptNames])

  const relationKey = (rel: ontologiesApi.OntologyRelation) => `${rel.from_concept}->${rel.to_concept}`

  return (
    <div className="relation-selector card">
      <div className="row">
        <h3>Доступные связи</h3>
      </div>
      
      <div className="relation-list">
        {filteredRelations.map(relation => {
          const key = relationKey(relation)
          const isSelected = selectedRelations.includes(key)
          
          return (
            <div 
              key={key}
              className={`relation-item ${isSelected ? 'selected' : ''}`}
              onClick={() => isSelected ? onDeselect(relation) : onSelect(relation)}
            >
              <div className="relation-arrow">
                <span>{relation.from_concept}</span>
                <span className="arrow">→</span>
                <span>{relation.to_concept}</span>
              </div>
              <div className="relation-type">{relation.relation_type}</div>
            </div>
          )
        })}
        
        {filteredRelations.length === 0 && (
          <p className="muted">Нет доступных связей между выбранными понятиями</p>
        )}
      </div>
      
      {showPagination && paginationProps && (
        <div className="card">
          <RelationPagination {...paginationProps} />
        </div>
      )}
    </div>
  )
}

interface SelectedRelationsListProps {
  selectedRelations: ontologiesApi.OntologyRelation[]
  onDelete: (relation: ontologiesApi.OntologyRelation) => void
}

function SelectedRelationsList({ selectedRelations, onDelete, totalCount }: SelectedRelationsListProps & { totalCount?: number }) {
  return (
    <div className="selected-relations-list card">
      <div className="row">
        <h3>Выбранные связи ({selectedRelations.length})</h3>
        {totalCount !== undefined && <span className="muted">из {totalCount} связей</span>}
      </div>
      
      {selectedRelations.map((relation) => {
        const key = `${relation.from_concept}->${relation.to_concept}`
        return (
          <div key={key} className="selected-relation-item">
            <div className="relation-info">
              <span className="relation-from">{relation.from_concept}</span>
              <span className="relation-arrow">→</span>
              <span className="relation-to">{relation.to_concept}</span>
              <span className="relation-type">{relation.relation_type}</span>
            </div>
            <div className="relation-controls">
              <button 
                type="button" 
                className="btn btn-small"
                onClick={() => onDelete(relation)}
              >
                Удалить
              </button>
            </div>
          </div>
        )
      })}
      
      {selectedRelations.length === 0 && (
        <p className="muted">Нет выбранных связей.</p>
      )}
    </div>
  )
}

interface OntologyConstructorProps {
  projectId: string
  directoryId: string
  onCancel: () => void
  onSubmit: (fileName: string) => void
}

export function OntologyConstructor({ projectId, directoryId, onCancel, onSubmit }: OntologyConstructorProps) {
  // Данные из директории
  const [availableConcepts, setAvailableConcepts] = useState<ontologiesApi.OntologyConcept[]>([])
  const [availableRelations, setAvailableRelations] = useState<ontologiesApi.OntologyRelation[]>([])
  
  // Выбранные данные
  const [selectedConceptNames, setSelectedConceptNames] = useState<string[]>([])
  const [selectedRelations, setSelectedRelations] = useState<string[]>([])
  
  // Состояние модалки
  const [phase, setPhase] = useState<1 | 2>(1) // Текущая фаза: 1 - понятия, 2 - отношения
  const [conceptPage, setConceptPage] = useState(0) // Текущая страница понятий
  const [relationPage, setRelationPage] = useState(0) // Текущая страница отношений
  const itemsPerPage = 10 // Элементов на страницу (фиксировано)
  
  const [fileName, setFileName] = useState('ontology.tdl')
  const [showPreview, setShowPreview] = useState(false)
  const [tdlPreview, setTdlPreview] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Загрузить понятия и связи из директории при открытии
  useEffect(() => {
    const loadConcepts = async () => {
      setLoading(true)
      try {
        const data = await ontologiesApi.getAllConcepts(projectId, directoryId)
        if (data.error) {
          setError(data.error)
        } else {
          setAvailableConcepts(data.concepts)
          setAvailableRelations(data.relations)
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err)
        setError(`Ошибка загрузки данных: ${message}`)
      } finally {
        setLoading(false)
      }
    }
    
    loadConcepts()
  }, [projectId, directoryId])

  // Получить объекты выбранных понятий
  const selectedConcepts = availableConcepts.filter(c => selectedConceptNames.includes(c.name))

  // Пагинация понятий
  const paginatedConcepts = useMemo(() => {
    const startIndex = conceptPage * itemsPerPage
    const endIndex = startIndex + itemsPerPage
    return availableConcepts.slice(startIndex, endIndex)
  }, [availableConcepts, conceptPage, itemsPerPage])

  const totalConceptPages = Math.ceil(availableConcepts.length / itemsPerPage)

  // Пагинация отношений (только между выбранными понятиями)
  const relationsBetweenSelected = useMemo(() => {
    return availableRelations.filter(rel => 
      selectedConceptNames.includes(rel.from_concept) && 
      selectedConceptNames.includes(rel.to_concept)
    )
  }, [availableRelations, selectedConceptNames])

  const paginatedRelations = useMemo(() => {
    const startIndex = relationPage * itemsPerPage
    const endIndex = startIndex + itemsPerPage
    return relationsBetweenSelected.slice(startIndex, endIndex)
  }, [relationsBetweenSelected, relationPage, itemsPerPage])

  const totalRelationPages = Math.ceil(relationsBetweenSelected.length / itemsPerPage)

  // Обработчики выбора понятий
  function handleSelectConcept(conceptName: string) {
    setSelectedConceptNames(prev => [...prev, conceptName])
  }

  function handleDeselectConcept(conceptName: string) {
    // Удалить понятие и все связи с ним
    setSelectedConceptNames(prev => prev.filter(name => name !== conceptName))
    setSelectedRelations(prev => prev.filter(key => {
      const [from, to] = key.split('->')
      return from !== conceptName && to !== conceptName
    }))
  }

  // Обработчики выбора связей
  function handleSelectRelation(relation: ontologiesApi.OntologyRelation) {
    const key = `${relation.from_concept}->${relation.to_concept}`
    if (!selectedRelations.includes(key)) {
      setSelectedRelations(prev => [...prev, key])
    }
  }

  function handleDeselectRelation(relation: ontologiesApi.OntologyRelation) {
    const key = `${relation.from_concept}->${relation.to_concept}`
    setSelectedRelations(prev => prev.filter(k => k !== key))
  }

  // Обновить selectedRelations при изменении selectedConceptNames
  useEffect(() => {
    const validRelations = availableRelations.filter(rel => 
      selectedConceptNames.includes(rel.from_concept) && 
      selectedConceptNames.includes(rel.to_concept)
    )
    const validKeys = validRelations.map(r => `${r.from_concept}->${r.to_concept}`)
    
    // Удаляем связи, которые больше не валидны
    setSelectedRelations(prev => prev.filter(key => validKeys.includes(key)))
  }, [selectedConceptNames, availableRelations])

  // Показать превью при изменении
  useEffect(() => {
    if (showPreview) {
      ontologiesApi
        .generateTDL({
          directory_id: directoryId,
          concepts: selectedConcepts,
          relations: selectedRelations.map(key => {
            const [from, to] = key.split('->')
            const rel = availableRelations.find(r => `${r.from_concept}->${r.to_concept}` === key)
            return rel || {
              relation_type: 'association',
              from_concept: from,
              to_concept: to,
            }
          }),
          file_name: fileName,
        })
        .then(tdl => setTdlPreview(tdl))
        .catch((err: unknown) => {
          const message = err instanceof Error ? err.message : String(err)
          setError(message)
        })
    }
  }, [selectedConcepts, selectedRelations, showPreview, directoryId, fileName, availableRelations])

  async function handleGenerate() {
    setShowPreview(true)
  }

  async function handleSave() {
    try {
      // Генерируем TDL и создаём файл через API
      await ontologiesApi.generateTDL({
        directory_id: directoryId,
        concepts: selectedConcepts,
        relations: selectedRelations.map(key => {
          const [from, to] = key.split('->')
          const rel = availableRelations.find(r => `${r.from_concept}->${r.to_concept}` === key)
          return rel || {
            relation_type: 'association',
            from_concept: from,
            to_concept: to,
          }
        }),
        file_name: fileName,
      })
      
      // Создаём файл с сгенерированным TDL-контентом
      let is_valid = false
      let error_message: string | null = null
      if (directoryId) {
        const result = await ontologiesApi.buildOntology(projectId, {
          directory_id: directoryId,
          concepts: selectedConcepts,
          relations: selectedRelations.map(key => {
            const [from, to] = key.split('->')
            const rel = availableRelations.find(r => `${r.from_concept}->${r.to_concept}` === key)
            return rel || {
              relation_type: 'association',
              from_concept: from,
              to_concept: to,
            }
          }),
          file_name: fileName,
          template: 'from_relations',
        })
        is_valid = result.is_valid
        error_message = result.error
      }
      
      if (is_valid) {
        onSubmit(fileName)
      } else {
        setError(error_message || 'Failed to create ontology')
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      setError(message)
    }
  }

  return (
    <Modal title="Конструктор онтологий" onClose={onCancel} className="large">
      {error && <p className="error">{error}</p>}
      
      <div className="ontology-constructor">
        {/* Загрузка данных */}
        {loading && (
          <div className="loading-overlay">
            <p>Загрузка понятий и связей из директории...</p>
          </div>
        )}
        
        {/* Навигация по фазам */}
        {!loading && (
          <PhaseSelector
            currentPhase={phase}
            onPhaseChange={setPhase}
            selectedConceptsCount={selectedConceptNames.length}
            availableConceptsCount={availableConcepts.length}
          />
        )}
        
        {/* Фаза 1: Выбор понятий */}
        {phase === 1 && (
          <div className="phase1-container">
            <div className="row">
              <div className="concepts-selector-section" style={{ flex: 1 }}>
                <ConceptSelector
                  availableConcepts={paginatedConcepts}
                  selectedConcepts={selectedConceptNames}
                  onSelect={handleSelectConcept}
                  onDeselect={handleDeselectConcept}
                  showPagination={true}
                  paginationProps={{
                    currentPage: conceptPage,
                    totalPages: totalConceptPages,
                    onPageChange: setConceptPage,
                    totalCount: availableConcepts.length
                  }}
                />
              </div>
              
              <div className="concepts-list-section" style={{ flex: 1 }}>
                <SelectedConceptsList
                  selectedConcepts={selectedConcepts}
                  onDelete={handleDeselectConcept}
                  totalCount={availableConcepts.length}
                />
              </div>
            </div>
          </div>
        )}
        
        {/* Фаза 2: Выбор отношений */}
        {phase === 2 && (
          <div className="phase2-container">
            <div className="row">
              <div className="relations-selector-section" style={{ flex: 1 }}>
                <RelationSelector
                  availableRelations={paginatedRelations}
                  selectedConceptNames={selectedConceptNames}
                  selectedRelations={selectedRelations}
                  onSelect={handleSelectRelation}
                  onDeselect={handleDeselectRelation}
                  showPagination={true}
                  paginationProps={{
                    currentPage: relationPage,
                    totalPages: totalRelationPages,
                    onPageChange: setRelationPage,
                    totalCount: relationsBetweenSelected.length
                  }}
                />
              </div>
              
              <div className="relations-list-section" style={{ flex: 1 }}>
                <SelectedRelationsList
                  selectedRelations={selectedRelations.map(key => {
                    const [from, to] = key.split('->')
                    return availableRelations.find(r => `${r.from_concept}->${r.to_concept}` === key) || {
                      relation_type: 'association',
                      from_concept: from,
                      to_concept: to,
                    }
                  })}
                  onDelete={handleDeselectRelation}
                  totalCount={relationsBetweenSelected.length}
                />
              </div>
            </div>
          </div>
        )}
        
        {/* Поля ввода */}
        <div className="form-group">
          <label>Имя файла</label>
          <input
            type="text"
            value={fileName}
            onChange={(e) => setFileName(e.target.value)}
            placeholder="ontology.tdl"
          />
        </div>
        
        {/* Превью TDL */}
        {showPreview && (
          <div className="tdl-preview">
            <div className="row">
              <h3>Превью TDL</h3>
              <button type="button" className="btn" onClick={() => setShowPreview(false)}>
                Скрыть
              </button>
            </div>
            <pre className="code-block">{tdlPreview}</pre>
            <div className="row">
              <button
                type="button"
                className="btn"
                onClick={() => navigator.clipboard?.writeText(tdlPreview)}
              >
                Копировать в буфер
              </button>
            </div>
          </div>
        )}
        
        {/* Кнопки действий */}
        <div className="row modal-actions">
          <div className="spacer" />
          <button type="button" className="btn" onClick={onCancel}>
            Отмена
          </button>
          <button type="button" className="btn" onClick={handleGenerate}>
            Сгенерировать TDL
          </button>
          <button type="button" className="btn btn-primary" onClick={handleSave}>
            Создать файл
          </button>
        </div>
      </div>
    </Modal>
  )
}

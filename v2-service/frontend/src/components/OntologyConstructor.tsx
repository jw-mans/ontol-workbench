import { useState, useEffect } from 'react'
import { Modal } from './Modal'
import * as ontologiesApi from '../api/ontologies'
import type { OntologyRelation } from '../api/ontologies'

interface ConceptEditorProps {
  concept: ontologiesApi.OntologyConcept
  onChange: (concept: ontologiesApi.OntologyConcept) => void
  onDelete: () => void
}

function ConceptEditor({ concept, onChange, onDelete }: ConceptEditorProps) {
  return (
    <div className="concept-editor card">
      <div className="row">
        <h3>Концепт: {concept.name}</h3>
        <button type="button" className="btn btn-danger" onClick={onDelete}>
          Удалить
        </button>
      </div>
      
      <div className="form-group">
        <label>Тип</label>
        <select
          value={concept.type}
          onChange={(e) => onChange({ ...concept, type: e.target.value as 'class' | 'interface' })}
        >
          <option value="class">Класс</option>
          <option value="interface">Интерфейс</option>
        </select>
      </div>
      
      <div className="form-group">
        <label>Абстрактный</label>
        <input
          type="checkbox"
          checked={concept.is_abstract || false}
          onChange={(e) => onChange({ ...concept, is_abstract: e.target.checked })}
        />
      </div>
      
      <div className="form-group">
        <label>Атрибуты (по строке)</label>
        <textarea
          value={concept.attributes?.join('\n') || ''}
          onChange={(e) => onChange({ ...concept, attributes: e.target.value.split('\n').filter(line => line.trim()) })}
          rows={3}
        />
      </div>
      
      <div className="form-group">
        <label>Операции (по строке)</label>
        <textarea
          value={concept.operations?.join('\n') || ''}
          onChange={(e) => onChange({ ...concept, operations: e.target.value.split('\n').filter(line => line.trim()) })}
          rows={3}
        />
      </div>
    </div>
  )
}

interface RelationEditorProps {
  relation: ontologiesApi.OntologyRelation
  allConcepts: ontologiesApi.OntologyConcept[]
  onChange: (relation: ontologiesApi.OntologyRelation) => void
  onDelete: () => void
}

function RelationEditor({ relation, allConcepts, onChange, onDelete }: RelationEditorProps) {
  return (
    <div className="relation-editor card">
      <div className="row">
        <h3>Связь</h3>
        <button type="button" className="btn btn-danger" onClick={onDelete}>
          Удалить
        </button>
      </div>
      
      <div className="form-group">
        <label>Тип связи</label>
        <select
          value={relation.relation_type}
          onChange={(e) => onChange({ ...relation, relation_type: e.target.value as OntologyRelation['relation_type'] })}
        >
          <option value="generalization">Обобщение (наследование)</option>
          <option value="association">Ассоциация</option>
          <option value="aggregation">Агрегация</option>
          <option value="composition">Композиция</option>
        </select>
      </div>
      
      <div className="form-row">
        <div className="form-group">
          <label>От</label>
          <select
            value={relation.from_concept}
            onChange={(e) => onChange({ ...relation, from_concept: e.target.value })}
          >
            {allConcepts.map(c => (
              <option key={c.name} value={c.name}>{c.name}</option>
            ))}
          </select>
        </div>
        
        <div className="form-group">
          <label>К</label>
          <select
            value={relation.to_concept}
            onChange={(e) => onChange({ ...relation, to_concept: e.target.value })}
          >
            {allConcepts.map(c => (
              <option key={c.name} value={c.name}>{c.name}</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  )
}

interface OntologyConstructorProps {
  directoryId: string
  onCancel: () => void
  onSubmit: (fileName: string) => void
}

export function OntologyConstructor({ directoryId, onCancel, onSubmit }: OntologyConstructorProps) {
  const [concepts, setConcepts] = useState<ontologiesApi.OntologyConcept[]>([
    { name: 'Класс1', type: 'class' },
    { name: 'Класс2', type: 'class' },
  ])
  const [relations, setRelations] = useState<ontologiesApi.OntologyRelation[]>([])
  const [fileName, setFileName] = useState('ontology.tdl')
  const [showPreview, setShowPreview] = useState(false)
  const [tdlPreview, setTdlPreview] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Показать превью при изменении
  useEffect(() => {
    if (showPreview) {
      ontologiesApi
        .generateTDL({
          directory_id: directoryId,
          concepts,
          relations,
          file_name: fileName,
        })
        .then(tdl => setTdlPreview(tdl))
        .catch((err: unknown) => {
          const message = err instanceof Error ? err.message : String(err)
          setError(message)
        })
    }
  }, [concepts, relations, showPreview, directoryId, fileName])

  function addConcept() {
    const name = `Класс${concepts.length + 1}`
    setConcepts([...concepts, { name, type: 'class' }])
  }

  function updateConcept(index: number, concept: ontologiesApi.OntologyConcept) {
    const newConcepts = [...concepts]
    newConcepts[index] = concept
    setConcepts(newConcepts)
  }

  function deleteConcept(index: number) {
    setConcepts(concepts.filter((_, i) => i !== index))
  }

  function addRelation() {
    if (concepts.length >= 2) {
      setRelations([
        ...relations,
        {
          relation_type: 'generalization',
          from_concept: concepts[1].name,
          to_concept: concepts[0].name,
        },
      ])
    }
  }

  function updateRelation(index: number, relation: ontologiesApi.OntologyRelation) {
    const newRelations = [...relations]
    newRelations[index] = relation
    setRelations(newRelations)
  }

  function deleteRelation(index: number) {
    setRelations(relations.filter((_, i) => i !== index))
  }

  async function handleGenerate() {
    setShowPreview(true)
  }

  async function handleSave() {
    try {
      if (!showPreview || !tdlPreview) {
        await ontologiesApi.generateTDL({
          directory_id: directoryId,
          concepts,
          relations,
          file_name: fileName,
        })
      }
      
      onSubmit(fileName)
      // В реальном приложении здесь можно сохранить TDL в файл
      // через filesApi.createFile(projectId, fileName, tdl, directoryId)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      setError(message)
    }
  }

  return (
    <Modal title="Конструктор онтологий" onClose={onCancel}>
      {error && <p className="error">{error}</p>}
      
      <div className="ontology-constructor">
        {/* Секция понятий */}
        <div className="concepts-section">
          <div className="row">
            <h3>Понятия</h3>
            <button type="button" className="btn" onClick={addConcept}>
              + Добавить понятие
            </button>
          </div>
          
          {concepts.map((concept, index) => (
            <ConceptEditor
              key={index}
              concept={concept}
              onChange={(c) => updateConcept(index, c)}
              onDelete={() => deleteConcept(index)}
            />
          ))}
          
          {concepts.length === 0 && (
            <p className="muted">Понятий пока нет. Добавьте первое понятие.</p>
          )}
        </div>
        
        {/* Секция связей */}
        <div className="relations-section">
          <div className="row">
            <h3>Связи</h3>
            <button type="button" className="btn" onClick={addRelation} disabled={concepts.length < 2}>
              + Добавить связь
            </button>
          </div>
          
          {relations.map((relation, index) => (
            <RelationEditor
              key={index}
              relation={relation}
              allConcepts={concepts}
              onChange={(r) => updateRelation(index, r)}
              onDelete={() => deleteRelation(index)}
            />
          ))}
          
          {relations.length === 0 && (
            <p className="muted">Связей пока нет.</p>
          )}
        </div>
        
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

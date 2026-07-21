import { useState, useRef } from 'react'

import { Modal } from './Modal'

/** Диалог импорта файлов из локальной папки */
export function ImportFileDialog({
  engine,
  onCancel,
  onSubmit,
}: {
  engine: 'v1' | 'v3'
  onCancel: () => void
  onSubmit: (files: { name: string; content: string }[]) => void
}) {
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const ext = engine === 'v1' ? '.ontol' : '.tdl'

  const openDirectoryPicker = async () => {
    if (fileInputRef.current) {
      // Для Safari устанавливаем webkitdirectory
      (fileInputRef.current as any).webkitdirectory = true
      
      // Сбрасываем значение input перед кликом
      fileInputRef.current.value = ''
      
      // Программный клик для открытия диалога
      fileInputRef.current.click()
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setIsProcessing(true)
      try {
        await importFiles(e.target.files)
      } finally {
        setIsProcessing(false)
      }
    }
  }

  // Рекурсивная функция для обхода DirectoryEntry
  const processDirectoryEntry = async (
    entry: any,
    basePath: string,
    resultFiles: { name: string; content: string }[],
    seenNames: Set<string>
  ) => {
    if (entry.isFile) {
      const file = entry as any
      const relativePath = basePath ? `${basePath}/${file.name}` : file.name
      
      // Игнорируем дубликаты
      if (seenNames.has(relativePath)) {
        return
      }
      
      if (relativePath.endsWith(ext)) {
        try {
          const blob = await file.blob()
          const content = await blob.text()
          seenNames.add(relativePath)
          resultFiles.push({ name: relativePath, content })
        } catch (err) {
          console.error(`Ошибка чтения файла ${relativePath}:`, err)
        }
      }
    } else if (entry.isDirectory) {
      const dir = entry as any
      const reader = dir.createReader()
      
      const readEntries = async (): Promise<any[]> => {
        return new Promise((resolve, reject) => {
          reader.readEntries(async (entries: any[]) => {
            if (entries.length > 0) {
              resolve(entries)
            } else {
              resolve([])
            }
          }, (err: any) => reject(err))
        })
      }
      
      let entries
      try {
        entries = await readEntries()
        for (const subEntry of entries) {
          const subPath = basePath ? `${basePath}/${dir.name}` : dir.name
          await processDirectoryEntry(subEntry, subPath, resultFiles, seenNames)
        }
      } catch (err) {
        console.error(`Ошибка чтения директории ${dir.name}:`, err)
      }
    }
  }

  const importFiles = async (files: FileList) => {
    const resultFiles: { name: string; content: string }[] = []
    const seenNames = new Set<string>()

    console.log('=== Import Files Debug ===')
    console.log('Files count:', files.length)
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      console.log(`File ${i}:`, {
        name: file.name,
        size: file.size,
        type: file.type,
        webkitRelativePath: (file as any).webkitRelativePath,
        haswebkitGetAsEntry: typeof (file as any)?.webkitGetAsEntry === 'function'
      })
    }

    // Проверяем, поддерживает ли браузер webkitGetAsEntry
    const hasDirectoryEntrySupport = typeof (files[0] as any)?.webkitGetAsEntry === 'function'
    console.log('Has DirectoryEntry support:', hasDirectoryEntrySupport)
    
    if (hasDirectoryEntrySupport) {
      // Используем webkitGetAsEntry для рекурсивного обхода
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const entry = (file as any).webkitGetAsEntry()
        console.log(`Entry ${i}:`, entry)
        
        if (entry) {
          if (entry.isFile) {
            // Обрабатываем как файл
            const relativePath = (file as any).webkitRelativePath || file.name
            const fileName = relativePath || file.name
            
            if (!seenNames.has(fileName) && fileName.endsWith(ext)) {
              try {
                const content = await file.text()
                seenNames.add(fileName)
                resultFiles.push({ name: fileName, content })
                console.log('Added file:', fileName)
              } catch (err) {
                console.error(`Ошибка чтения файла ${fileName}:`, err)
              }
            }
          } else if (entry.isDirectory) {
            console.log('Processing directory:', entry.name)
            // Рекурсивно обрабатываем директорию
            await processDirectoryEntry(entry, '', resultFiles, seenNames)
          }
        }
      }
    } else {
      // Фолбэк для браузеров без DirectoryEntry - используем плоский список
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const relativePath = (file as any).webkitRelativePath || file.name
        const fileName = relativePath || file.name
        
        if (!seenNames.has(fileName) && fileName.endsWith(ext)) {
          try {
            const content = await file.text()
            seenNames.add(fileName)
            resultFiles.push({ name: fileName, content })
          } catch (err) {
            console.error(`Ошибка чтения файла ${fileName}:`, err)
          }
        }
      }
    }

    console.log('Final result files:', resultFiles.length)
    resultFiles.forEach(f => console.log('  -', f.name))
    console.log('========================')

    if (resultFiles.length > 0) {
      onSubmit(resultFiles)
    } else {
      setError(`Файлы с расширением ${ext} не найдены.`)
    }
  }

  return (
    <Modal title="Импорт файлов" onClose={onCancel}>
      <div className="import-dialog">
        <p className="muted">
          Выберите папку для импорта файлов {ext} в проект.
        </p>

        {error && <p className="error">{error}</p>}

        <div className="import-actions">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="file-input"
          />
          <button 
            type="button" 
            className="btn" 
            onClick={openDirectoryPicker}
            disabled={isProcessing}
          >
            {isProcessing ? 'Обработка...' : 'Выбрать папку'}
          </button>
        </div>

        <p className="muted small">
          Импортируются только файлы с расширением {ext}. Другие файлы игнорируются.
        </p>

        <div className="row modal-actions">
          <div className="spacer" />
          <button type="button" className="btn" onClick={onCancel}>
            Отмена
          </button>
        </div>
      </div>
    </Modal>
  )
}

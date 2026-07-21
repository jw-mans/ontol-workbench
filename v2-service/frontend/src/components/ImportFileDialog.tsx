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
  onSubmit: (files: { name: string; content: string }[], summary?: { total: number; imported: number; duplicates: number }) => void
}) {
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [summary, setSummary] = useState<{
    total: number
    imported: number
    skipped: number
    duplicates: number
  } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const ext = engine === 'v1' ? '.ontol' : '.tdl'

  // Refs для передачи в showDirectoryPicker
  const resultFilesRef = useRef<{ name: string; content: string }[]>([])
  const seenPathsRef = useRef<Set<string>>(new Set<string>())

  // Очистка refs при открытии диалога для предотвращения загрязнения между открытиями
  const clearRefs = () => {
    resultFilesRef.current = []
    seenPathsRef.current = new Set<string>()
    setError(null)
    setSummary(null)
  }

  // Нормализация пути для проверки дубликатов
  const normalizePath = (path: string): string => {
    // Заменяем обратные слэши на прямые, удаляем лидирующие и завершающие слэши
    return path.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
  }

  // Проверка, является ли путь файлом (последний элемент пути содержит точку и расширение)
  const isFilePath = (path: string): boolean => {
    const parts = path.split('/')
    const lastPart = parts[parts.length - 1]
    return lastPart.includes('.') && lastPart.endsWith(ext)
  }

  // Функция для обработки DirectoryHandle (showDirectoryPicker API)
  const processDirectoryHandle = async (
    dirHandle: any,
    basePath: string,
    resultFiles: { name: string; content: string }[],
    seenPaths: Set<string>
  ) => {
    for await (const entry of dirHandle.values()) {
      if (entry.kind === 'file') {
        if (entry.name.endsWith(ext)) {
          const file = await entry.getFile()
          const relativePath = basePath ? `${basePath}/${entry.name}` : entry.name
          
          // Игнорируем дубликаты
          const normalizedPath = normalizePath(relativePath)
          if (seenPaths.has(normalizedPath)) {
            continue
          }
          
          try {
            const content = await file.text()
            seenPaths.add(normalizedPath)
            resultFiles.push({ name: relativePath, content })
          } catch (err) {
            console.error(`Ошибка чтения файла ${relativePath}:`, err)
          }
        }
      } else if (entry.kind === 'directory') {
        const subPath = basePath ? `${basePath}/${entry.name}` : entry.name
        await processDirectoryHandle(entry, subPath, resultFiles, seenPaths)
      }
    }
  }

  // Рекурсивная функция для обхода DirectoryEntry (webkitGetAsEntry API)
  const processDirectoryEntry = async (
    entry: any,
    basePath: string,
    resultFiles: { name: string; content: string }[],
    seenPaths: Set<string>
  ) => {
    // Используем webkitRelativePath, если он доступен
    // Safari возвращает webkitRelativePath с ПОЛНЫМ путем от корня директории
    const webkitRelativePath = (entry as any)?.webkitRelativePath
    
    // Формируем путь для проверки дубликатов
    let pathForCheck: string
    if (webkitRelativePath && webkitRelativePath.trim() !== '') {
      pathForCheck = webkitRelativePath
    } else if (basePath) {
      pathForCheck = `${basePath}/${entry.name}`
    } else {
      pathForCheck = entry.name
    }
    
    const normalizedPath = normalizePath(pathForCheck)
    
    // Обрабатываем только файлы с нужным расширением
    if (entry.isFile && entry.name.endsWith(ext)) {
      // Проверяем, не является ли это директорией
      if (isFilePath(normalizedPath)) {
        // Игнорируем дубликаты
        if (seenPaths.has(normalizedPath)) {
          console.log('  -> SKIPPED (duplicate):', normalizedPath)
          return
        }
        
        const file = entry as any
        try {
          const blob = await file.blob()
          const content = await blob.text()
          seenPaths.add(normalizedPath)
          resultFiles.push({ name: pathForCheck, content })
          console.log('  -> ADDED:', normalizedPath)
        } catch (err) {
          console.error(`Ошибка чтения файла ${pathForCheck}:`, err)
        }
      } else {
        console.log('  -> SKIPPED (wrong extension):', normalizedPath)
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
        console.log('Directory entries for:', dir.name, 'count:', entries.length)
        for (const subEntry of entries) {
          // Safari уже включает полный путь в webkitRelativePath
          // basePath нужен только для браузеров без webkitRelativePath
          const hasWebkitRelativePath = typeof (subEntry as any)?.webkitRelativePath !== 'undefined'
          const subPath = hasWebkitRelativePath ? '' : (basePath ? `${basePath}/${dir.name}` : dir.name)
          await processDirectoryEntry(subEntry, subPath, resultFiles, seenPaths)
        }
      } catch (err) {
        console.error(`Ошибка чтения директории ${dir.name}:`, err)
      }
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    // Очищаем refs перед началом обработки
    clearRefs()
    
    if (e.target.files && e.target.files.length > 0) {
      console.log('handleFileSelect called with', e.target.files.length, 'files')
      setIsProcessing(true)
      try {
        await importFiles(e.target.files)
      } finally {
        setIsProcessing(false)
      }
    } else {
      console.log('handleFileSelect: no files selected')
    }
  }

  const importFiles = async (files: FileList) => {
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
      // Важно: Safari возвращает как файлы, так и директории, и у них всех есть webkitRelativePath
      // Мы должны обрабатывать ТОЛЬКО файлы с правильным расширением
      
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const entry = (file as any).webkitGetAsEntry()
        console.log(`Entry ${i}:`, entry, 'isFile:', entry?.isFile, 'isDirectory:', entry?.isDirectory)
        
        if (entry) {
          if (entry.isFile) {
            // Обрабатываем ф��йл напрямую
            const webkitRelativePath = (file as any).webkitRelativePath
            const fileName = (webkitRelativePath && webkitRelativePath.trim() !== '') 
              ? webkitRelativePath 
              : file.name
            
            console.log('File via webkitGetAsEntry:', file.name, 'webkitRelativePath:', webkitRelativePath, 'fileName:', fileName)
            
            // Нормализуем путь для проверки дубликатов
            const normalizedFileName = normalizePath(fileName)
            
            if (!seenPathsRef.current.has(normalizedFileName) && normalizedFileName.endsWith(ext)) {
              try {
                const content = await file.text()
                seenPathsRef.current.add(normalizedFileName)
                resultFilesRef.current.push({ name: normalizedFileName, content })
                console.log('  -> ADDED:', normalizedFileName)
              } catch (err) {
                console.error(`Ошибка чтения файла ${fileName}:`, err)
              }
            } else {
              console.log('  -> SKIPPED (duplicate or wrong ext):', normalizedFileName)
            }
          } else if (entry.isDirectory) {
            console.log('Processing directory:', entry.name)
            // Рекурсивно обрабатываем директорию
            // basePath пустой, потому что Safari уже включает полный путь в webkitRelativePath
            await processDirectoryEntry(entry, '', resultFilesRef.current, seenPathsRef.current)
          }
        }
      }
    } else {
      // Fallback для браузеров без DirectoryEntry - используем плоский список
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        // Используем webkitRelativePath, если он доступен и не пустой
        // Иначе используем просто имя файла
        const relativePath = (file as any).webkitRelativePath
        const fileName = (relativePath && relativePath.trim() !== '') ? relativePath : file.name
        
        console.log('Fallback file:', file.name, 'webkitRelativePath:', relativePath, 'fileName:', fileName)
        
        // Нормализуем путь для проверки дубликатов
        const normalizedFileName = normalizePath(fileName)
        
        if (!seenPathsRef.current.has(normalizedFileName) && normalizedFileName.endsWith(ext)) {
          try {
            const content = await file.text()
            seenPathsRef.current.add(normalizedFileName)
            resultFilesRef.current.push({ name: normalizedFileName, content })
            console.log('Added fallback file:', normalizedFileName)
          } catch (err) {
            console.error(`Ошибка чтения файла ${fileName}:`, err)
          }
        }
      }
    }

    console.log('Final result files:', resultFilesRef.current.length)
    resultFilesRef.current.forEach(f => console.log('  -', f.name))
    console.log('========================')

    if (resultFilesRef.current.length > 0) {
      const duplicates = resultFilesRef.current.length - new Set(resultFilesRef.current.map(f => normalizePath(f.name))).size
      const summary = {
        total: resultFilesRef.current.length,
        imported: resultFilesRef.current.length - duplicates,
        duplicates,
      }
      onSubmit(resultFilesRef.current, summary)
    } else {
      setError(`Файлы с расширением ${ext} не найдены.`)
    }
  }

  const openDirectoryPicker = async () => {
    // Очищаем refs перед началом обработки
    clearRefs()
    
    // Проверяем поддержку showDirectoryPicker (современные браузеры)
    if ('showDirectoryPicker' in window) {
      try {
        const dirHandle = await (window as any).showDirectoryPicker({
          mode: 'read',
        })
        
        setIsProcessing(true)
        try {
          await processDirectoryHandle(dirHandle, '', resultFilesRef.current, seenPathsRef.current)
          if (resultFilesRef.current.length > 0) {
            const duplicates = resultFilesRef.current.length - new Set(resultFilesRef.current.map(f => normalizePath(f.name))).size
            const summary = {
              total: resultFilesRef.current.length,
              imported: resultFilesRef.current.length - duplicates,
              duplicates,
            }
            onSubmit(resultFilesRef.current, summary)
          } else {
            setError(`Файлы с расширением ${ext} не найдены.`)
          }
        } catch (err) {
          console.error('Ошибка при обработке директории:', err)
          setError('Ошибка при импорте файлов')
        } finally {
          setIsProcessing(false)
        }
        return
      } catch (err: any) {
        // Пользователь отменил выбор или ошибка - пробуем fallback
        console.log('showDirectoryPicker не поддерживается или отменён:', err)
      }
    }
    
    // Fallback для Safari и других браузеров без showDirectoryPicker
    if (fileInputRef.current) {
      // Для Safari устанавливаем webkitdirectory
      (fileInputRef.current as any).webkitdirectory = true
      
      // Сбрасываем значение input перед кликом
      fileInputRef.current.value = ''
      
      // Программный клик для открытия диалога
      fileInputRef.current.click()
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

        {/* Сводка импорта */}
        {summary && (
          <div className="summary">
            <h4>Сводка импорта:</h4>
            <ul>
              <li>Всего файлов в папке: {summary.total}</li>
              <li>Файлов импортировано: {summary.imported}</li>
              <li>Дубликатов пропущено: {summary.duplicates}</li>
            </ul>
            <p className="muted">
              Файлы были отправлены на бэкенд для создания.
            </p>
          </div>
        )}

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

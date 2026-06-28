/** Скачать текст как файл (JSON, .puml). */
export function downloadText(filename: string, text: string, mime = 'text/plain') {
  const blob = new Blob([text], { type: mime })
  const url = URL.createObjectURL(blob)
  triggerDownload(filename, url)
  URL.revokeObjectURL(url)
}

/** Скачать data-URL (PNG-диаграмма). */
export function downloadDataUrl(filename: string, dataUrl: string) {
  triggerDownload(filename, dataUrl)
}

function triggerDownload(filename: string, href: string) {
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
}

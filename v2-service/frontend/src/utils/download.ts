/** Скачать текст как файл (JSON, .puml). */
export function downloadText(filename: string, text: string, mime = 'text/plain') {
  const blob = new Blob([text], { type: mime })
  const url = URL.createObjectURL(blob)
  triggerDownload(filename, url)
  URL.revokeObjectURL(url)
}

/** Скачать файл по URL (в т.ч. presigned-ссылка MinIO, кросс-origin): тянем как
 * blob и сохраняем с именем. Атрибут `download` для кросс-origin игнорируется,
 * поэтому нужен именно blob (требует CORS у хранилища — включён, см. шаг 5). */
export async function downloadFromUrl(filename: string, url: string) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const objectUrl = URL.createObjectURL(await res.blob())
  triggerDownload(filename, objectUrl)
  URL.revokeObjectURL(objectUrl)
}

function triggerDownload(filename: string, href: string) {
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
}

import { useEffect, useState } from 'react'
import Editor, { type Monaco } from '@monaco-editor/react'

import {
  ONTOL_LANG_ID,
  ONTOL_THEME_DARK,
  ONTOL_THEME_LIGHT,
  registerOntol,
} from '../ontol-lang/ontol-language'
import { TDL_LANG_ID, registerTdl } from '../ontol-lang/tdl-language'

function prefersDark(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-color-scheme: dark)').matches
  )
}

interface Props {
  value: string
  onChange: (value: string) => void
  /** Язык подсветки: 'ontol' (v1) или 'tdl' (v3). По умолчанию ontol. */
  language?: 'ontol' | 'tdl'
}

/** Редактор Ontol/TDL на Monaco: подсветка языка + тема по системной схеме. */
export default function OntolEditor({
  value,
  onChange,
  language = 'ontol',
}: Props) {
  const [dark, setDark] = useState(prefersDark)

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!mq) return
    const handler = (e: MediaQueryListEvent) => setDark(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  function beforeMount(monaco: Monaco) {
    registerOntol(monaco)
    registerTdl(monaco)
  }

  return (
    <Editor
      className="ontol-editor"
      language={language === 'tdl' ? TDL_LANG_ID : ONTOL_LANG_ID}
      theme={dark ? ONTOL_THEME_DARK : ONTOL_THEME_LIGHT}
      value={value}
      onChange={(v) => onChange(v ?? '')}
      beforeMount={beforeMount}
      loading={<div className="muted">Загрузка редактора…</div>}
      options={{
        fontSize: 14,
        fontFamily:
          'ui-monospace, Consolas, "Cascadia Code", "Fira Code", monospace',
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        tabSize: 2,
        automaticLayout: true,
        wordWrap: 'on',
        renderWhitespace: 'selection',
      }}
    />
  )
}

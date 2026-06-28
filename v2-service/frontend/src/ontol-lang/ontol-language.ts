import type { Monaco } from '@monaco-editor/react'
import type { languages } from 'monaco-editor'

export const ONTOL_LANG_ID = 'ontol'
export const ONTOL_THEME_LIGHT = 'ontol-light'
export const ONTOL_THEME_DARK = 'ontol-dark'

// Секции файла и мета-ключи шапки (распознаются как ключевые слова).
const SECTIONS = ['types', 'functions', 'hierarchy', 'figure']
const META_KEYS = ['version', 'title', 'author', 'description']
const IMPORT_KEYWORDS = ['import', 'from', 'as']
// Типы связей и направления (oast.RelationshipType / RelationshipDirection).
const RELATIONSHIPS = [
  'dependence',
  'association',
  'directAssociation',
  'inheritance',
  'implementation',
  'aggregation',
  'composition',
]
const DIRECTIONS = ['forward', 'backward', 'bidirectional']
// Имена атрибутов в фигурных скобках (Term/Relationship/Function attributes).
const ATTRIBUTES = [
  'color',
  'note',
  'direction',
  'title',
  'rightChar',
  'leftChar',
  'colorArrow',
  'type',
  'inputTitle',
  'outputTitle',
]

const languageConfig: languages.LanguageConfiguration = {
  comments: { lineComment: '#' },
  brackets: [
    ['{', '}'],
    ['(', ')'],
  ],
  autoClosingPairs: [
    { open: '{', close: '}' },
    { open: '(', close: ')' },
    { open: "'", close: "'" },
    { open: '"', close: '"' },
  ],
  surroundingPairs: [
    { open: '{', close: '}' },
    { open: '(', close: ')' },
    { open: "'", close: "'" },
    { open: '"', close: '"' },
  ],
}

const monarch: languages.IMonarchLanguage = {
  defaultToken: '',
  ignoreCase: false,
  sections: SECTIONS,
  metaKeys: META_KEYS,
  importKeywords: IMPORT_KEYWORDS,
  relationships: RELATIONSHIPS,
  directions: DIRECTIONS,
  attributes: ATTRIBUTES,

  tokenizer: {
    root: [
      [/#.*$/, 'comment'],
      [/'[^']*'|"[^"]*"/, 'string'],
      [/->/, 'operator'],
      [/[{}(),:*]/, 'delimiter'],
      [
        /[a-zA-Z_][a-zA-Z0-9_]*/,
        {
          cases: {
            '@sections': 'keyword.section',
            '@importKeywords': 'keyword',
            '@relationships': 'type',
            '@directions': 'constant',
            '@attributes': 'attribute.name',
            '@metaKeys': 'keyword.meta',
            '@default': 'identifier',
          },
        },
      ],
    ],
  },
}

/** Подсветка цвета-литерала */
const COLOR_RULES = [
  { token: 'keyword.section', foreground: 'aa3bff', fontStyle: 'bold' },
  { token: 'keyword.meta', foreground: '0a7ea4' },
  { token: 'keyword', foreground: 'aa3bff' },
  { token: 'type', foreground: 'c2410c', fontStyle: 'bold' },
  { token: 'constant', foreground: '0a7ea4' },
  { token: 'attribute.name', foreground: '8250df' },
  { token: 'string', foreground: '197d3c' },
  { token: 'comment', foreground: '8b8794', fontStyle: 'italic' },
  { token: 'operator', foreground: 'cf222e' },
  { token: 'delimiter', foreground: '6b6375' },
]

const DARK_RULES = [
  { token: 'keyword.section', foreground: 'c084fc', fontStyle: 'bold' },
  { token: 'keyword.meta', foreground: '56d4dd' },
  { token: 'keyword', foreground: 'c084fc' },
  { token: 'type', foreground: 'ffa657', fontStyle: 'bold' },
  { token: 'constant', foreground: '56d4dd' },
  { token: 'attribute.name', foreground: 'd2a8ff' },
  { token: 'string', foreground: '7ee787' },
  { token: 'comment', foreground: '8b8794', fontStyle: 'italic' },
  { token: 'operator', foreground: 'ff7b72' },
  { token: 'delimiter', foreground: '9ca3af' },
]

let registered = false

/** Зарегистрировать язык и темы Ontol (идемпотентно). */
export function registerOntol(monaco: Monaco): void {
  if (registered) return
  registered = true

  monaco.languages.register({ id: ONTOL_LANG_ID, extensions: ['.ontol'] })
  monaco.languages.setLanguageConfiguration(ONTOL_LANG_ID, languageConfig)
  monaco.languages.setMonarchTokensProvider(ONTOL_LANG_ID, monarch)

  monaco.editor.defineTheme(ONTOL_THEME_LIGHT, {
    base: 'vs',
    inherit: true,
    rules: COLOR_RULES,
    colors: {},
  })
  monaco.editor.defineTheme(ONTOL_THEME_DARK, {
    base: 'vs-dark',
    inherit: true,
    rules: DARK_RULES,
    colors: {},
  })
}

import type { Monaco } from '@monaco-editor/react'
import type { languages } from 'monaco-editor'

// Язык ontol-v3 (TDL). Темы переиспользуем от Ontol (ontol-language.ts) —
// имена токенов совпадают (keyword/type/constant/comment/operator/...).
export const TDL_LANG_ID = 'tdl'

// Ключевые слова регистронезависимы (лексер приводит к нижнему регистру).
const KEYWORDS = [
  'класс', 'перечисление', 'конец', 'атрибуты', 'операции', 'размещение',
  'зафиксировать', 'выровнять', 'распределить', 'сгруппировать', 'привязать',
  'повернуть', 'по', 'левому', 'правому', 'верху', 'низу', 'горизонтали',
  'вертикали', 'шаг', 'как', 'левее', 'правее', 'выше', 'ниже', 'в',
]
const RELATIONSHIPS = [
  'обобщение', 'ассоциация', 'композиция', 'агрегация', 'зависимость',
  'реализация',
]
const MODIFIERS = [
  'абстрактный', 'абстрактная', 'производная', 'подстановочное',
  'только_чтение', 'запрос', 'лист', 'имя',
]

const languageConfig: languages.LanguageConfiguration = {
  comments: { lineComment: '--' },
  brackets: [
    ['{', '}'],
    ['(', ')'],
    ['[', ']'],
  ],
  autoClosingPairs: [
    { open: '{', close: '}' },
    { open: '(', close: ')' },
    { open: '[', close: ']' },
  ],
  surroundingPairs: [
    { open: '{', close: '}' },
    { open: '(', close: ')' },
    { open: '[', close: ']' },
  ],
}

const monarch: languages.IMonarchLanguage = {
  defaultToken: '',
  ignoreCase: true,
  keywords: KEYWORDS,
  relationships: RELATIONSHIPS,
  modifiers: MODIFIERS,

  tokenizer: {
    root: [
      // Комментарий `--` в начале строки; `--` в середине — связь (operator).
      [/^[ \t]*--.*$/, 'comment'],
      [/->|--/, 'operator'],
      [/[{}()[\],:;=]/, 'delimiter'],
      [/[+#~]/, 'operator'], // маркеры видимости + # ~ (минус ловится выше)
      [/\d+(\.\.(\*|\d+))?|\*/, 'number'], // числа и кратности [1..*]
      [
        /[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*/,
        {
          cases: {
            '@keywords': 'keyword',
            '@relationships': 'type',
            '@modifiers': 'constant',
            '@default': 'identifier',
          },
        },
      ],
    ],
  },
}

let registered = false

/** Зарегистрировать язык TDL (идемпотентно). Темы — общие с Ontol. */
export function registerTdl(monaco: Monaco): void {
  if (registered) return
  registered = true

  monaco.languages.register({ id: TDL_LANG_ID, extensions: ['.tdl'] })
  monaco.languages.setLanguageConfiguration(TDL_LANG_ID, languageConfig)
  monaco.languages.setMonarchTokensProvider(TDL_LANG_ID, monarch)
}

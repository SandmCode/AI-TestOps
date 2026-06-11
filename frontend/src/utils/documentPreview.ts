import { marked } from 'marked'
import hljs from 'highlight.js/lib/core'
import jsonLang from 'highlight.js/lib/languages/json'
import yamlLang from 'highlight.js/lib/languages/yaml'
import xmlLang from 'highlight.js/lib/languages/xml'
import plaintextLang from 'highlight.js/lib/languages/plaintext'

hljs.registerLanguage('json', jsonLang)
hljs.registerLanguage('yaml', yamlLang)
hljs.registerLanguage('xml', xmlLang)
hljs.registerLanguage('plaintext', plaintextLang)

marked.setOptions({
  gfm: true,
  breaks: true,
})

export function renderMarkdown(content: string) {
  return marked.parse(content || '') as string
}

export function highlightCode(content: string, language: string) {
  const lang = hljs.getLanguage(language) ? language : 'plaintext'
  try {
    return hljs.highlight(content || '', { language: lang }).value
  } catch {
    return hljs.highlight(content || '', { language: 'plaintext' }).value
  }
}

export function parseCsvRows(content: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let inQuotes = false

  const pushCell = () => {
    row.push(cell)
    cell = ''
  }

  const pushRow = () => {
    if (row.length > 0 || cell) {
      pushCell()
      rows.push(row)
      row = []
    }
  }

  for (let i = 0; i < content.length; i++) {
    const ch = content[i]
    const next = content[i + 1]

    if (ch === '"') {
      if (inQuotes && next === '"') {
        cell += '"'
        i++
      } else {
        inQuotes = !inQuotes
      }
      continue
    }

    if (!inQuotes && ch === ',') {
      pushCell()
      continue
    }

    if (!inQuotes && (ch === '\n' || ch === '\r')) {
      if (ch === '\r' && next === '\n') i++
      pushRow()
      continue
    }

    cell += ch
  }

  if (cell || row.length) pushRow()
  return rows.filter((r) => r.some((c) => c.trim()))
}

export function formatArchiveSize(size: number) {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

export interface ParseItem {
  module: string
  name: string
  description: string
  type: string
}

export interface ParsedCache {
  document_id: number
  document_name: string
  features: ParseItem[]
  constraints: ParseItem[]
  exceptions: ParseItem[]
  parseVersion: number
  updatedAt: string
}

const STORAGE_KEY = 'requirement-parse-cache-v1'

function readAll(): Record<string, ParsedCache> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function writeAll(data: Record<string, ParsedCache>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

export function loadParseCache(documentId: number): ParsedCache | null {
  return readAll()[String(documentId)] ?? null
}

export function saveParseCache(documentId: number, payload: Omit<ParsedCache, 'updatedAt'>) {
  const all = readAll()
  all[String(documentId)] = {
    ...payload,
    document_id: documentId,
    updatedAt: new Date().toISOString(),
  }
  writeAll(all)
}

export function clearParseCache(documentId: number) {
  const all = readAll()
  delete all[String(documentId)]
  writeAll(all)
}

export function getLastParseDocumentId(): number | null {
  const all = readAll()
  let latest: ParsedCache | null = null
  for (const item of Object.values(all)) {
    if (!latest || item.updatedAt > latest.updatedAt) latest = item
  }
  return latest?.document_id ?? null
}

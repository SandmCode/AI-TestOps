export type Severity = 'error' | 'warning' | 'info'

export function severityLabel(severity: string): string {
  const map: Record<string, string> = {
    error: '错误',
    warning: '警告',
    info: '提示',
  }
  return map[severity] || severity
}

export function severityTagType(severity: string): 'danger' | 'warning' | 'info' | 'success' {
  if (severity === 'error') return 'danger'
  if (severity === 'warning') return 'warning'
  if (severity === 'info') return 'info'
  return 'success'
}

export interface Violation {
  field: string
  message: string
  severity: Severity
  fix?: string
  fix_snippet?: string
  auto_fixable?: boolean
  fix_id?: string
}

export interface ContractResult {
  summary: string
  violations: Violation[]
  passed?: boolean
  stats?: { error: number; warning: number; info: number }
  fixable_count?: number
  fixed_spec?: string | null
  source?: string
  fix_summary?: string
  record_id?: number
}

export interface ContractFixResult {
  fixed_spec: string
  applied: string[]
  applied_labels: string[]
  validation: ContractResult
  fix_summary?: string
  error?: string
}

export interface CoverageResult {
  summary: string
  line_coverage: number
  branch_coverage: number
  uncovered: string[]
  suggestions: string[]
  record_id?: number
}

export interface LogResult {
  summary: string
  error_count: number
  warning_count: number
  info_count?: number
  patterns: { pattern: string; count: number; suggestion: string }[]
  line_count?: number
  record_id?: number
}

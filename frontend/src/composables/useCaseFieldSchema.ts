import { computed, ref } from 'vue'
import { getCaseFieldDefinitions } from '@/api'

export interface CaseFieldDef {
  id: number
  key: string
  label: string
  field_type: 'text' | 'textarea' | 'select' | 'date' | 'priority' | 'passed'
  storage: 'column' | 'extra'
  column_name: string
  required: boolean
  searchable: boolean
  show_in_list: boolean
  show_in_filter: boolean
  sort_order: number
  is_system: boolean
  options: string[]
  project: number | null
}

export function useCaseFieldSchema() {
  const fields = ref<CaseFieldDef[]>([])
  const loading = ref(false)

  const sortedFields = computed(() =>
    [...fields.value].sort((a, b) => a.sort_order - b.sort_order),
  )

  /** 新增/编辑表单：全部已配置字段（排除只读 created_at） */
  const formFields = computed(() => sortedFields.value.filter((f) => f.key !== 'created_at'))

  /** 列表区：仅「列表展示」勾选的字段 */
  const listFields = computed(() => sortedFields.value.filter((f) => f.show_in_list))

  /** 筛选区：仅「筛选展示」勾选的字段（数量与字段均由字段配置决定） */
  const filterFields = computed(() => sortedFields.value.filter((f) => f.show_in_filter))

  const primaryListField = computed(() => listFields.value[0] ?? null)

  const secondaryListFields = computed(() =>
    primaryListField.value
      ? listFields.value.slice(1)
      : listFields.value,
  )

  async function load(projectId: number | null) {
    if (!projectId) {
      fields.value = []
      return
    }
    loading.value = true
    try {
      const res = await getCaseFieldDefinitions({ project: projectId })
      fields.value = res.data.results ?? res.data
    } finally {
      loading.value = false
    }
  }

  function defaultValue(field: CaseFieldDef): unknown {
    if (field.field_type === 'passed') return null
    if (field.field_type === 'priority') return 'P2'
    return ''
  }

  function emptyFormValues(): Record<string, unknown> {
    const values: Record<string, unknown> = {}
    for (const f of fields.value) {
      values[f.key] = defaultValue(f)
    }
    return values
  }

  function valuesFromCase(item: Record<string, unknown>): Record<string, unknown> {
    const values: Record<string, unknown> = {}
    for (const f of fields.value) {
      values[f.key] = item[f.key] ?? defaultValue(f)
    }
    return values
  }

  function buildFilterState(): Record<string, string> {
    const state: Record<string, string> = {}
    for (const f of filterFields.value) {
      state[f.key] = ''
    }
    return state
  }

  function formatFieldValue(item: Record<string, unknown>, field: CaseFieldDef): string {
    const val = item[field.key]
    if (val === null || val === undefined || val === '') return '-'
    if (field.field_type === 'passed') {
      if (val === true) return '通过'
      if (val === false) return '失败'
      return '未执行'
    }
    if (field.key === 'created_at' && typeof val === 'string') {
      return val.slice(0, 10)
    }
    return String(val)
  }

  function caseSummary(item: Record<string, unknown>): string {
    const primary = primaryListField.value
    if (primary) return formatFieldValue(item, primary)
    return `用例 #${(item.sort_order as number ?? 0) + 1}`
  }

  return {
    fields,
    loading,
    formFields,
    listFields,
    filterFields,
    primaryListField,
    secondaryListFields,
    load,
    emptyFormValues,
    valuesFromCase,
    buildFilterState,
    formatFieldValue,
    caseSummary,
  }
}

import { onMounted, ref, watch, type Ref } from 'vue'

export type AnalysisType = 'contract' | 'coverage' | 'log'

interface SessionPayload<TInput = string, TResult = unknown> {
  input: TInput
  result: TResult | null
  extra?: Record<string, unknown>
  updatedAt: number
}

function storageKey(type: AnalysisType) {
  return `ai-workbench-session:${type}`
}

export function useAnalysisSession<TInput extends string, TResult>(
  type: AnalysisType,
  input: Ref<TInput>,
  result: Ref<TResult | null>,
  extra?: Ref<Record<string, unknown> | undefined>,
) {
  const restored = ref(false)

  function saveSession() {
    const payload: SessionPayload<TInput, TResult> = {
      input: input.value,
      result: result.value,
      extra: extra?.value,
      updatedAt: Date.now(),
    }
    try {
      localStorage.setItem(storageKey(type), JSON.stringify(payload))
    } catch {
      /* ignore quota */
    }
  }

  function loadSession() {
    try {
      const raw = localStorage.getItem(storageKey(type))
      if (!raw) return
      const data = JSON.parse(raw) as SessionPayload<TInput, TResult>
      if (data.input) input.value = data.input
      if (data.result) result.value = data.result
      if (extra && data.extra) extra.value = data.extra
      restored.value = true
    } catch {
      /* ignore */
    }
  }

  function clearSession() {
    result.value = null
    if (extra) extra.value = undefined
    localStorage.removeItem(storageKey(type))
  }

  onMounted(loadSession)

  watch([input, result, () => extra?.value], saveSession, { deep: true })

  return { restored, saveSession, loadSession, clearSession }
}

export function clearAllWorkbenchCache() {
  const types: AnalysisType[] = ['contract', 'coverage', 'log']
  types.forEach((t) => localStorage.removeItem(storageKey(t)))
}

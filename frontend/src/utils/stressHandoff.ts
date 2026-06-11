export const STRESS_HANDOFF_KEY = 'api-stress-handoff'

export interface StressHandoff {
  projectId: number | null
  interfaceIds: number[]
  variables?: string
}

export function saveStressHandoff(data: StressHandoff) {
  localStorage.setItem(STRESS_HANDOFF_KEY, JSON.stringify(data))
}

export function consumeStressHandoff(): StressHandoff | null {
  try {
    const raw = localStorage.getItem(STRESS_HANDOFF_KEY)
    if (!raw) return null
    localStorage.removeItem(STRESS_HANDOFF_KEY)
    return JSON.parse(raw) as StressHandoff
  } catch {
    return null
  }
}

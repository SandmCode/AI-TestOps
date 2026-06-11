export const SECURITY_HANDOFF_KEY = 'api-security-handoff'

export interface SecurityHandoff {
  projectId: number | null
  interfaceIds: number[]
  variables?: string
}

export function saveSecurityHandoff(data: SecurityHandoff) {
  localStorage.setItem(SECURITY_HANDOFF_KEY, JSON.stringify(data))
}

export function consumeSecurityHandoff(): SecurityHandoff | null {
  try {
    const raw = localStorage.getItem(SECURITY_HANDOFF_KEY)
    if (!raw) return null
    localStorage.removeItem(SECURITY_HANDOFF_KEY)
    return JSON.parse(raw) as SecurityHandoff
  } catch {
    return null
  }
}

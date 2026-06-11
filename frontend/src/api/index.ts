import axios from 'axios'
import { ElMessage } from 'element-plus'

/** AI 生成类接口超时（毫秒），大模型响应可能较慢 */
export const AI_REQUEST_TIMEOUT = 300000

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const data = err.response?.data
    let msg = data?.error || data?.detail || err.message
    if (data && typeof data === 'object' && !data.error && !data.detail) {
      const parts = Object.entries(data).map(([k, v]) => {
        const text = Array.isArray(v) ? v.join('；') : String(v)
        return `${k}: ${text}`
      })
      if (parts.length) msg = parts.join(' | ')
    }
    if (err.code === 'ECONNABORTED' || String(msg).toLowerCase().includes('timeout')) {
      msg = '请求超时，AI 仍在处理中或文档过大，请稍后重试或换用更快的模型'
    }
    ElMessage.error(typeof msg === 'string' ? msg : '请求失败')
    return Promise.reject(err)
  }
)

export default api

// Projects
export const getProjects = (params?: object) => api.get('/projects/', { params })
export const createProject = (data: object) => api.post('/projects/', data)
export const updateProject = (id: number, data: object) => api.patch(`/projects/${id}/`, data)
export const deleteProject = (id: number) => api.delete(`/projects/${id}/`)
export const batchDeleteProjects = (ids: number[]) => api.post('/projects/batch-delete/', { ids })

// Documents
export const getDocuments = (params?: object) => api.get('/documents/', { params })
export const getDocument = (id: number) => api.get(`/documents/${id}/`)
export const getDocumentPreview = (id: number) => api.get(`/documents/${id}/preview/`)
export const createDocument = (data: FormData) => api.post('/documents/', data, {
  headers: { 'Content-Type': 'multipart/form-data' },
  timeout: 600000,
})
export const chunkInit = (data: object) => api.post('/documents/chunk-init/', data)
export const chunkStatus = (uploadId: string) => api.get('/documents/chunk-status/', { params: { upload_id: uploadId } })
export const chunkUploadPart = (data: FormData) => api.post('/documents/chunk-upload/', data, {
  headers: { 'Content-Type': 'multipart/form-data' },
  timeout: 300000,
})
export const chunkComplete = (uploadId: string) => api.post('/documents/chunk-complete/', { upload_id: uploadId }, { timeout: 600000 })
export const chunkCancel = (uploadId: string) => api.post('/documents/chunk-cancel/', { upload_id: uploadId })
export const updateDocument = (id: number, data: object | FormData) => {
  const isForm = data instanceof FormData
  return api.patch(`/documents/${id}/`, data, isForm ? { headers: { 'Content-Type': 'multipart/form-data' } } : undefined)
}
export const deleteDocument = (id: number) => api.delete(`/documents/${id}/`)
export const batchDeleteDocuments = (ids: number[]) => api.post('/documents/batch-delete/', { ids })
export const downloadDocument = (id: number) => `/api/documents/${id}/download/`
export const previewDocumentFile = (id: number) => `/api/documents/${id}/preview-file/`
export const aiGenerateRequirements = (id: number) =>
  api.post(`/documents/${id}/ai-generate-requirements/`, undefined, { timeout: AI_REQUEST_TIMEOUT })
export const aiParseDocumentDetail = (id: number) =>
  api.post(`/documents/${id}/ai-parse-detail/`, undefined, { timeout: AI_REQUEST_TIMEOUT })
export const aiParseApiDocument = (id: number) =>
  api.post(`/documents/${id}/ai-parse-apis/`, undefined, { timeout: AI_REQUEST_TIMEOUT })

// Requirements
export const getRequirements = (params?: object) => api.get('/requirements/', { params })
export const getRequirementTree = (params?: object) => api.get('/requirements/tree/', { params })
export const createRequirement = (data: object) => api.post('/requirements/', data)
export const updateRequirement = (id: number, data: object) => api.patch(`/requirements/${id}/`, data)
export const deleteRequirement = (id: number) => api.delete(`/requirements/${id}/`)
export const batchCreateRequirements = (data: object) => api.post('/requirements/batch-create/', data)
export const aiGenerateTestPoints = (id: number, data?: object) =>
  api.post(`/requirements/${id}/ai_generate_test_points/`, data || {}, { timeout: AI_REQUEST_TIMEOUT })

// Test Points
export const getTestPoints = (params?: object) => api.get('/test-points/', { params })
export const getTestPointTree = (params?: object) => api.get('/test-points/tree/', { params })
export const createTestPoint = (data: object) => api.post('/test-points/', data)
export const updateTestPoint = (id: number, data: object) => api.patch(`/test-points/${id}/`, data)
export const deleteTestPoint = (id: number) => api.delete(`/test-points/${id}/`)
export const batchCreateTestPoints = (data: object) => api.post('/test-points/batch-create/', data)
export const batchAiGenerateCases = (data: object) =>
  api.post('/test-points/ai-generate-cases/', data, { timeout: 15000 })
export const getAsyncTask = (id: number) => api.get(`/async-tasks/${id}/`)
export const getActiveAsyncTask = (params?: object) => api.get('/async-tasks/active/', { params })
export const aiGenerateCases = (id: number, data?: object) =>
  api.post(`/test-points/${id}/ai_generate_cases/`, data || {}, { timeout: AI_REQUEST_TIMEOUT })

// Knowledge / RAG
export const getKnowledgeItems = (params?: object) => api.get('/knowledge-items/', { params })
export const createKnowledgeItem = (data: object) => api.post('/knowledge-items/', data)
export const updateKnowledgeItem = (id: number, data: object) => api.patch(`/knowledge-items/${id}/`, data)
export const deleteKnowledgeItem = (id: number) => api.delete(`/knowledge-items/${id}/`)
export const recallKnowledge = (params?: object) => api.get('/knowledge-items/recall/', { params })

// Case Field Definitions
export const getCaseFieldDefinitions = (params?: object) => api.get('/case-field-definitions/', { params })
export const createCaseFieldDefinition = (data: object) => api.post('/case-field-definitions/', data)
export const updateCaseFieldDefinition = (id: number, data: object) => api.patch(`/case-field-definitions/${id}/`, data)
export const deleteCaseFieldDefinition = (id: number) => api.delete(`/case-field-definitions/${id}/`)
export const reorderCaseFieldDefinitions = (ids: number[]) => api.post('/case-field-definitions/reorder/', { ids })
export const resetCaseFieldDefinitions = (project: number) => api.post('/case-field-definitions/reset-defaults/', { project })

// Test Cases
export const getTestCases = (params?: object) => api.get('/test-cases/', { params })
export const createTestCase = (data: object) => api.post('/test-cases/', data)
export const updateTestCase = (id: number, data: object) => api.patch(`/test-cases/${id}/`, data)
export const deleteTestCase = (id: number) => api.delete(`/test-cases/${id}/`)
export const batchDeleteTestCases = (ids: number[]) => api.post('/test-cases/batch-delete/', { ids })
export const batchUpdateTestCaseStatus = (data: { ids: number[]; passed: boolean | null }) =>
  api.post('/test-cases/batch-update-status/', data)
export const reorderTestCases = (ids: number[]) => api.post('/test-cases/reorder/', { ids })
export const convertTestCases = (data: object) => api.post('/test-cases/convert/', data)
export const exportTestCasesExcel = (params?: object) =>
  api.get('/test-cases/export-excel/', { params, responseType: 'blob' })

// Test Suites & Execution
export const getTestSuites = (params?: object) => api.get('/test-suites/', { params })
export const createTestSuite = (data: object) => api.post('/test-suites/', data)
export const runTestSuite = (id: number) =>
  api.post(`/test-suites/${id}/run/`, undefined, { timeout: AI_REQUEST_TIMEOUT })
export const getExecutionRuns = (params?: object) => api.get('/execution-runs/', { params })
export const batchRunCases = (data: object) =>
  api.post('/execution-runs/batch-run/', data, { timeout: AI_REQUEST_TIMEOUT })

// API Interfaces
export const getApiInterfaces = (params?: object) => api.get('/api-interfaces/', { params })
export const createApiInterface = (data: object) => api.post('/api-interfaces/', data)
export const updateApiInterface = (id: number, data: object) => api.patch(`/api-interfaces/${id}/`, data)
export const deleteApiInterface = (id: number) => api.delete(`/api-interfaces/${id}/`)
export const batchDeleteApiInterfaces = (ids: number[]) => api.post('/api-interfaces/batch-delete/', { ids })
export const reorderApiInterfaces = (ids: number[]) => api.post('/api-interfaces/sort-order/', { ids })
export const batchImportApiInterfaces = (data: object) => api.post('/api-interfaces/batch-import/', data)
export const batchConfigureApiDeps = (data: object) => api.post('/api-interfaces/batch-configure-deps/', data)
export const runApiAutomation = (data: object) => api.post('/api-interfaces/run-automation/', data, { timeout: 120000 })
export const getSecurityMeta = () => api.get('/security-scan-targets/security-meta/')
export const getSecurityScanTargets = (params?: object) => api.get('/security-scan-targets/', { params })
export const createSecurityScanTarget = (data: object) => api.post('/security-scan-targets/', data)
export const updateSecurityScanTarget = (id: number, data: object) => api.patch(`/security-scan-targets/${id}/`, data)
export const importSecurityScanTargets = (data: object) => api.post('/security-scan-targets/import-from-interfaces/', data)
export const deleteSecurityScanTarget = (id: number) => api.delete(`/security-scan-targets/${id}/`)
export const batchDeleteSecurityScanTargets = (ids: number[]) => api.post('/security-scan-targets/batch-delete/', { ids })
export const runSecurityScan = (data: object) => api.post('/security-scan-targets/run-scan/', data, { timeout: 300000 })
export const getStressTestTargets = (params?: object) => api.get('/stress-test-targets/', { params })
export const createStressTestTarget = (data: object) => api.post('/stress-test-targets/', data)
export const updateStressTestTarget = (id: number, data: object) => api.patch(`/stress-test-targets/${id}/`, data)
export const importStressTestTargets = (data: object) => api.post('/stress-test-targets/import-from-interfaces/', data)
export const batchDeleteStressTestTargets = (ids: number[]) => api.post('/stress-test-targets/batch-delete/', { ids })
export const batchConfigureStressDeps = (data: object) => api.post('/stress-test-targets/batch-configure-deps/', data)
export const debugStressTarget = (id: number, data?: object) => api.post(`/stress-test-targets/${id}/debug/`, data || {})
export const getStressTestRuns = (params?: object) => api.get('/stress-test-runs/', { params })
export const getStressTestRun = (id: number) => api.get(`/stress-test-runs/${id}/`)
export const startStressTest = (data: object) => api.post('/stress-test-runs/start/', data, { timeout: 120000 })
export const stopStressTest = (id: number) => api.post(`/stress-test-runs/${id}/stop/`)
export const generateApiPythonCode = (data: object) => api.post('/api-interfaces/generate-python/', data)
export const debugApiInterface = (id: number, data?: object) => api.post(`/api-interfaces/${id}/debug/`, data || {})
export const aiGenerateApiCases = (id: number, data?: object) =>
  api.post(`/api-interfaces/${id}/ai_generate_cases/`, data || {}, { timeout: AI_REQUEST_TIMEOUT })

// Tools
export const parseCurl = (curl: string) => api.post('/tools/parse-curl/', { curl })
export const apiTest = (data: object) => api.post('/tools/api-test/', data)
export const mockData = (data: object) => api.post('/tools/mock-data/', data)
export const getMockDataMeta = () => api.get('/tools/mock-data/')
export const jsonTool = (data: object) => api.post('/tools/json/', data)
export const encodeConvert = (data: object) => api.post('/tools/encode/', data)
export const getEncodeMeta = () => api.get('/tools/encode/')
export const stressScript = (data: object) => api.post('/tools/stress-script/', data)

// AI Config
export const getAiConfigs = (params?: object) => api.get('/ai-config/', { params })
export const getAiConfigStatus = () => api.get('/ai/config-status/')
export const createAiConfig = (data: object) => api.post('/ai-config/', data)
export const updateAiConfig = (id: number, data: object) => api.patch(`/ai-config/${id}/`, data)
export const deleteAiConfig = (id: number) => api.delete(`/ai-config/${id}/`)
export const activateAiConfig = (id: number) => api.post(`/ai-config/${id}/activate/`)
export const deactivateAiConfig = (id: number) => api.post(`/ai-config/${id}/deactivate/`)
export const testAiConfig = (id: number) => api.post(`/ai-config/${id}/test/`, undefined, { timeout: 60000 })
export const getCcSwitchStatus = () => api.get('/ai-config/cc-switch-status/')
export const importFromCcSwitch = (data: object) => api.post('/ai-config/import-cc-switch/', data)

// AI Skills
export const getAiSkills = (params?: object) => api.get('/ai-skills/', { params })
export const getAiSkillsSettings = () => api.get('/ai-skills/global-settings/')
export const updateAiSkillsSettings = (data: object) => api.patch('/ai-skills/global-settings/', data)
export const updateAiSkill = (id: number, data: object) => api.patch(`/ai-skills/${id}/`, data)
export const deleteAiSkill = (id: number) => api.delete(`/ai-skills/${id}/`)
export const batchDeleteAiSkills = (ids?: number[]) => api.post('/ai-skills/batch-delete/', ids?.length ? { ids } : {})
export const uploadAiSkill = (data: FormData) => api.post('/ai-skills/upload/', data, {
  headers: { 'Content-Type': 'multipart/form-data' },
})
export const scanLocalSkills = () => api.post('/ai-skills/scan-local/')
export const importCcSwitchSkills = () => api.post('/ai-skills/import-cc-switch/')

// AI Features
export const contractTest = (api_spec: string) =>
  api.post('/ai/contract-test/', { api_spec }, { timeout: AI_REQUEST_TIMEOUT })
export const contractTestFix = (api_spec: string, fix_ids?: string[]) =>
  api.post('/ai/contract-test/fix/', { api_spec, fix_ids }, { timeout: AI_REQUEST_TIMEOUT })
export const coverageAnalysis = (content: string) =>
  api.post('/ai/coverage-analysis/', { content }, { timeout: AI_REQUEST_TIMEOUT })
export const logAnalysis = (logs: string) =>
  api.post('/ai/log-analysis/', { logs }, { timeout: AI_REQUEST_TIMEOUT })

// Analysis Records
export const getAnalysisRecords = (params?: object) => api.get('/analysis-records/', { params })
export const getAnalysisRecord = (id: number) => api.get(`/analysis-records/${id}/`)
export const deleteAnalysisRecord = (id: number) => api.delete(`/analysis-records/${id}/`)
export const downloadAnalysisRecordPath = (id: number, format: 'json' | 'md' = 'json') =>
  `/analysis-records/${id}/download/?file_type=${format}`

// System
export const getSystemInfo = () => api.get('/system/info/')
export const systemMaintain = (action: string) => api.post('/system/maintain/', { action })

// Reports
export const getTestReports = (params?: object) => api.get('/test-reports/', { params })
export const createTestReport = (data: object) => api.post('/test-reports/', data)
export const deleteTestReport = (id: number) => api.delete(`/test-reports/${id}/`)
export const generateAutomationReport = (data: object) => api.post('/test-reports/generate-automation/', data)
export const generateSecurityReport = (data: object) => api.post('/test-reports/generate-security/', data)
export const generateStressReport = (data: object) => api.post('/test-reports/generate-stress/', data)
export const generateStressRunReport = (id: number) => api.post(`/stress-test-runs/${id}/generate-report/`)
export const getStressRunAnalysis = (id: number) => api.get(`/stress-test-runs/${id}/analysis/`)

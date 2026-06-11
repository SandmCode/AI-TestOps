<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getProjects,
  getStressTestTargets,
  createStressTestTarget,
  updateStressTestTarget,
  importStressTestTargets,
  batchDeleteStressTestTargets,
  batchConfigureStressDeps,
  debugStressTarget,
  getStressTestRuns,
  getStressTestRun,
  startStressTest,
  stopStressTest,
  getStressRunAnalysis,
  generateStressRunReport,
} from '@/api'
import CardCheckbox from '@/components/CardCheckbox.vue'
import ApiEndpointFormDialog, { type ApiEndpointFormPayload } from '@/components/ApiEndpointFormDialog.vue'
import { consumeStressHandoff } from '@/utils/stressHandoff'
import { openReportUrl } from '@/utils/reportPrompt'

interface MappingItem {
  depends_on: number | null
  source: string
  target: string
  transform?: string
}

interface StressTarget {
  id: number
  name: string
  method: string
  url: string
  module: string
  sort_order?: number
  source_interface_id?: number | null
  depends_on?: number | null
  depends_on_name?: string | null
  dependency_mappings?: MappingItem[]
  headers?: Record<string, unknown>
  params?: Record<string, unknown>
  body?: Record<string, unknown>
  response_example?: Record<string, unknown>
  description?: string
}

interface TimePoint {
  elapsed: number
  rps: number
  avg_ms: number
  p95_ms: number
  errors: number
  threads: number
}

interface ResourcePoint {
  elapsed: number
  cpu_percent: number
  memory_mb: number
  system_memory_percent: number
}

interface EndpointStat {
  target_id: number
  name: string
  method: string
  url: string
  total: number
  success: number
  fail: number
  error_rate: number
  avg_ms: number
  p95_ms: number
  status_codes: Record<string, number>
}

interface StressAnalysis {
  bottlenecks: { type: string; desc: string; name?: string; metric?: number; unit?: string }[]
  inflection_points: { type: string; desc: string; elapsed_sec?: number }[]
  recommendations: string[]
  health_score: number
}

interface StressRun {
  id: number
  name: string
  status: string
  summary: Record<string, number>
  time_series: TimePoint[]
  endpoint_stats: EndpointStat[]
  resource_series: ResourcePoint[]
  config: Record<string, unknown>
  analysis?: StressAnalysis
  error_message?: string
}

const PROJECT_CACHE_KEY = 'stress-test-project'
const VARIABLES_CACHE_KEY = 'stress-test-variables'
const DEFAULT_VARIABLES = '{"baseUrl":"http://127.0.0.1:9000/v1"}'

const projects = ref<{ id: number; name: string }[]>([])
const targets = ref<StressTarget[]>([])
const projectId = ref<number | null>(null)
const variables = ref(DEFAULT_VARIABLES)
const selectedMap = reactive<Record<number, boolean>>({})
const loading = ref(false)
const running = ref(false)
const currentRunId = ref<number | null>(null)
const currentRun = ref<StressRun | null>(null)
const runHistory = ref<StressRun[]>([])
const skipProjectWatch = ref(false)
const formDialogVisible = ref(false)
const editingId = ref<number | null>(null)
const editingRow = ref<StressTarget | null>(null)
const depDialogVisible = ref(false)
const depTarget = ref<StressTarget | null>(null)
const depForm = ref({ mappings: [] as MappingItem[] })
const bulkDepDialogVisible = ref(false)
const bulkDepSaving = ref(false)
const bulkDepForm = ref({
  auth_target_id: null as number | null,
  only_unconfigured: true,
  overwrite: false,
  scope: 'all' as 'all' | 'selected',
})
const debugging = ref(false)
const debugResult = ref<{ name: string; url: string; status_code: number; body: string; error: string } | null>(null)
const runAnalysis = ref<StressAnalysis | null>(null)
const reportGenerating = ref(false)

const config = ref({
  users: 10,
  spawn_rate: 2,
  duration_sec: 30,
  think_time_ms: 0,
  token_refresh_sec: 60,
  name: '',
})

const rpsChartRef = ref<HTMLDivElement | null>(null)
const latencyChartRef = ref<HTMLDivElement | null>(null)
const resourceChartRef = ref<HTMLDivElement | null>(null)
let rpsChart: echarts.ECharts | null = null
let latencyChart: echarts.ECharts | null = null
let resourceChart: echarts.ECharts | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

const selectedIds = computed(() => targets.value.filter((t) => selectedMap[t.id]).map((t) => t.id))
const selectedCount = computed(() => selectedIds.value.length)
const isAllSelected = computed({
  get: () => targets.value.length > 0 && targets.value.every((t) => selectedMap[t.id]),
  set: (val: boolean) => targets.value.forEach((t) => { selectedMap[t.id] = val }),
})

const summary = computed(() => currentRun.value?.summary || {})
const isLive = computed(() => currentRun.value?.status === 'running' || currentRun.value?.status === 'pending')

const loginTargetCandidates = computed(() =>
  targets.value.filter((t) => {
    const url = (t.url || '').toLowerCase()
    return t.method === 'POST' && (url.includes('/auth/login') || url.endsWith('/login') || t.name.includes('登录'))
  }),
)

const otherTargets = computed(() =>
  targets.value.filter((t) => !depTarget.value || t.id !== depTarget.value.id),
)

const authRequiredCount = computed(() =>
  targets.value.filter((t) => {
    const url = (t.url || '').toLowerCase()
    if (url.includes('/auth/') || url.endsWith('/login')) return false
    const headers = t.headers || {}
    const hasAuth = Object.keys(headers).some((k) => k.toLowerCase() === 'authorization')
      || Object.values(headers).some((v) => typeof v === 'string' && v.toLowerCase().includes('bearer'))
    const protectedUrl = ['/users/', '/products', '/cart', '/orders'].some((p) => url.includes(p))
    return hasAuth || protectedUrl
  }).length,
)

const statusLabel: Record<string, string> = {
  pending: '准备中',
  running: '压测中',
  completed: '已完成',
  stopped: '已停止',
  failed: '失败',
}

function parseVariables(): Record<string, unknown> {
  try {
    return JSON.parse(variables.value || '{}')
  } catch {
    return {}
  }
}

function resetSelection(items: StressTarget[]) {
  Object.keys(selectedMap).forEach((k) => delete selectedMap[Number(k)])
  items.forEach((item) => { selectedMap[item.id] = false })
}

function selectTargetIds(ids: number[]) {
  ids.forEach((id) => { selectedMap[id] = true })
}

async function loadProjects() {
  const res = await getProjects()
  projects.value = res.data.results ?? res.data
  const cached = localStorage.getItem(PROJECT_CACHE_KEY)
  if (cached && projects.value.some((p) => p.id === Number(cached))) {
    projectId.value = Number(cached)
  } else {
    projectId.value = projects.value[0]?.id ?? null
  }
}

async function loadTargets() {
  if (!projectId.value) {
    targets.value = []
    return
  }
  loading.value = true
  try {
    const res = await getStressTestTargets({ project: projectId.value, page_size: 500 })
    targets.value = (res.data.results ?? res.data)
      .map((t: StressTarget) => ({ ...t, dependency_mappings: t.dependency_mappings || [] }))
      .sort((a: StressTarget, b: StressTarget) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
    resetSelection(targets.value)
  } finally {
    loading.value = false
  }
}

function defaultLoginId() {
  return loginTargetCandidates.value[0]?.id ?? null
}

function mappingDepLabels(row: StressTarget) {
  const ids = new Set<number>()
  row.dependency_mappings?.forEach((m) => {
    if (m.depends_on) ids.add(m.depends_on)
  })
  if (row.depends_on) ids.add(row.depends_on)
  return [...ids]
    .map((id) => targets.value.find((t) => t.id === id))
    .filter(Boolean)
    .map((t) => t!.name)
}

function openDepDialog(row: StressTarget) {
  depTarget.value = row
  const fallbackDep = row.depends_on ?? defaultLoginId()
  depForm.value = {
    mappings: row.dependency_mappings?.length
      ? row.dependency_mappings.map((m) => ({
          depends_on: m.depends_on ?? row.depends_on ?? defaultLoginId(),
          source: m.source || '',
          target: m.target || '',
          transform: m.transform || '',
        }))
      : [{
          depends_on: fallbackDep,
          source: 'body.data.access_token',
          target: 'headers.Authorization',
          transform: 'Bearer {value}',
        }],
  }
  depDialogVisible.value = true
}

function addMapping() {
  const last = depForm.value.mappings.at(-1)
  depForm.value.mappings.push({
    depends_on: last?.depends_on ?? defaultLoginId(),
    source: '',
    target: '',
    transform: '',
  })
}

function removeMapping(idx: number) {
  depForm.value.mappings.splice(idx, 1)
}

async function saveDependency() {
  if (!depTarget.value) return
  const mappings = depForm.value.mappings.filter((m) => m.source && m.target && m.depends_on)
  if (depForm.value.mappings.some((m) => (m.source || m.target) && !m.depends_on)) {
    ElMessage.warning('每条映射请选择来源接口')
    return
  }
  await updateStressTestTarget(depTarget.value.id, {
    depends_on: mappings[0]?.depends_on ?? null,
    dependency_mappings: mappings,
  })
  ElMessage.success('关联配置已保存')
  depDialogVisible.value = false
  await loadTargets()
}

function openBulkDepDialog() {
  bulkDepForm.value = {
    auth_target_id: loginTargetCandidates.value[0]?.id ?? null,
    only_unconfigured: true,
    overwrite: false,
    scope: selectedCount.value > 0 ? 'selected' : 'all',
  }
  bulkDepDialogVisible.value = true
}

async function saveBulkDependency() {
  if (!projectId.value) return
  bulkDepSaving.value = true
  try {
    const payload: Record<string, unknown> = {
      project_id: projectId.value,
      auth_target_id: bulkDepForm.value.auth_target_id,
      only_unconfigured: bulkDepForm.value.only_unconfigured,
      overwrite: bulkDepForm.value.overwrite,
    }
    if (bulkDepForm.value.scope === 'selected' && selectedIds.value.length) {
      payload.target_ids = selectedIds.value
    }
    const res = await batchConfigureStressDeps(payload)
    ElMessage.success(`已为 ${res.data.updated_count} 个目标配置登录关联（${res.data.auth_target_name}）`)
    bulkDepDialogVisible.value = false
    await loadTargets()
  } finally {
    bulkDepSaving.value = false
  }
}

async function debugTarget(row: StressTarget) {
  debugging.value = true
  debugResult.value = null
  try {
    const res = await debugStressTarget(row.id, { variables: parseVariables() })
    debugResult.value = {
      name: row.name,
      url: res.data.url || row.url,
      status_code: res.data.status_code ?? 0,
      body: res.data.body ?? '',
      error: res.data.error ?? '',
    }
    if (res.data.status_code >= 400 || res.data.error) {
      ElMessage.warning(`联调失败：HTTP ${res.data.status_code}`)
    } else {
      ElMessage.success('联调成功，依赖链与 token 已解析')
    }
  } finally {
    debugging.value = false
  }
}

async function loadHistory() {
  if (!projectId.value) return
  const res = await getStressTestRuns({ project: projectId.value, page_size: 10 })
  runHistory.value = res.data.results ?? res.data
}

function buildImportMessage(data: Record<string, number | boolean>, replace: boolean) {
  const before = data.before_count as number
  const after = data.after_count as number
  const mode = replace ? '覆盖导入' : '追加导入'
  return `${mode}：${before} → ${after}（新增 ${data.created_count}，更新 ${data.updated_count}）`
}

async function promptImportMode(existingCount: number, importCount: number): Promise<boolean | null> {
  try {
    await ElMessageBox.confirm(
      `当前已有 ${existingCount} 个压测目标，本次将导入 ${importCount} 个接口。\n\n【覆盖】删除全部已有目标，仅保留本次选中\n【追加】保留已有目标，重复项更新、新接口追加`,
      '如何导入压测目标？',
      {
        distinguishCancelAndClose: true,
        confirmButtonText: '覆盖（清空后导入）',
        cancelButtonText: '追加（保留已有）',
        type: 'warning',
      },
    )
    return true
  } catch (action) {
    if (action === 'cancel') return false
    return null
  }
}

async function importFromHandoff(interfaceIds: number[], replace = true) {
  if (!projectId.value || !interfaceIds.length) return
  const res = await importStressTestTargets({
    project_id: projectId.value,
    interface_ids: interfaceIds,
    replace,
  })
  await loadTargets()
  const imported = res.data.targets || []
  if (imported.length) selectTargetIds(imported.map((t: StressTarget) => t.id))
  ElMessage.success(buildImportMessage(res.data, replace))
}

function openCreateTarget() {
  if (!projectId.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  editingId.value = null
  editingRow.value = null
  formDialogVisible.value = true
}

function openEditTarget(row: StressTarget) {
  editingId.value = row.id
  editingRow.value = row
  formDialogVisible.value = true
}

async function onTargetFormSave(payload: ApiEndpointFormPayload) {
  if (!projectId.value) return
  if (editingId.value) {
    await updateStressTestTarget(editingId.value, payload)
    ElMessage.success('已保存')
  } else {
    await createStressTestTarget({
      ...payload,
      project: projectId.value,
      sort_order: targets.value.length,
    })
    ElMessage.success('已新增')
  }
  formDialogVisible.value = false
  await loadTargets()
}

async function removeSelected() {
  if (!selectedCount.value) return
  await ElMessageBox.confirm(`确定删除选中的 ${selectedCount.value} 个压测目标？`, '批量删除', { type: 'warning' })
  await batchDeleteStressTestTargets(selectedIds.value)
  ElMessage.success('已删除')
  await loadTargets()
}

async function removeOne(row: StressTarget) {
  await ElMessageBox.confirm(`确定删除「${row.name}」？`, '删除', { type: 'warning' })
  await batchDeleteStressTestTargets([row.id])
  ElMessage.success('已删除')
  await loadTargets()
}

async function loadAnalysis(runId: number) {
  try {
    const res = await getStressRunAnalysis(runId)
    runAnalysis.value = res.data
  } catch {
    runAnalysis.value = null
  }
}

async function generateReportForRun(runId: number, e?: Event) {
  e?.stopPropagation()
  reportGenerating.value = true
  try {
    const res = await generateStressRunReport(runId)
    ElMessage.success('压测 Allure 报告已生成')
    if (res.data.report_url) openReportUrl(res.data.report_url)
  } finally {
    reportGenerating.value = false
  }
}

function initCharts() {
  if (rpsChartRef.value) rpsChart = echarts.init(rpsChartRef.value)
  if (latencyChartRef.value) latencyChart = echarts.init(latencyChartRef.value)
  if (resourceChartRef.value) resourceChart = echarts.init(resourceChartRef.value)
}

function updateCharts(run: StressRun) {
  const series = run.time_series || []
  const labels = series.map((p) => `${p.elapsed}s`)
  const dark = '#9aa0a6'
  const grid = { left: 48, right: 16, top: 32, bottom: 28 }

  if (rpsChart) {
    rpsChart.setOption({
      title: { text: '吞吐量 (RPS)', textStyle: { color: '#e8eaed', fontSize: 13 }, left: 8 },
      tooltip: { trigger: 'axis' },
      grid,
      xAxis: { type: 'category', data: labels, axisLabel: { color: dark } },
      yAxis: { type: 'value', name: 'req/s', axisLabel: { color: dark }, splitLine: { lineStyle: { color: '#2a3544' } } },
      series: [{
        name: 'RPS',
        type: 'line',
        smooth: true,
        data: series.map((p) => p.rps),
        areaStyle: { color: 'rgba(16, 185, 129, 0.15)' },
        lineStyle: { color: '#10b981' },
        itemStyle: { color: '#10b981' },
      }],
    })
  }

  if (latencyChart) {
    latencyChart.setOption({
      title: { text: '响应时间', textStyle: { color: '#e8eaed', fontSize: 13 }, left: 8 },
      tooltip: { trigger: 'axis' },
      legend: { data: ['平均', 'P95'], textStyle: { color: dark }, top: 4, right: 8 },
      grid,
      xAxis: { type: 'category', data: labels, axisLabel: { color: dark } },
      yAxis: { type: 'value', name: 'ms', axisLabel: { color: dark }, splitLine: { lineStyle: { color: '#2a3544' } } },
      series: [
        {
          name: '平均',
          type: 'line',
          smooth: true,
          data: series.map((p) => p.avg_ms),
          lineStyle: { color: '#60a5fa' },
          itemStyle: { color: '#60a5fa' },
        },
        {
          name: 'P95',
          type: 'line',
          smooth: true,
          data: series.map((p) => p.p95_ms),
          lineStyle: { color: '#f59e0b' },
          itemStyle: { color: '#f59e0b' },
        },
      ],
    })
  }

  const resources = run.resource_series || []
  const resLabels = resources.map((p) => `${p.elapsed}s`)
  if (resourceChart) {
    resourceChart.setOption({
      title: { text: '压测机资源', textStyle: { color: '#e8eaed', fontSize: 13 }, left: 8 },
      tooltip: { trigger: 'axis' },
      legend: { data: ['CPU %', '内存 MB'], textStyle: { color: dark }, top: 4, right: 8 },
      grid,
      xAxis: { type: 'category', data: resLabels, axisLabel: { color: dark } },
      yAxis: [
        { type: 'value', name: 'CPU', axisLabel: { color: dark }, splitLine: { lineStyle: { color: '#2a3544' } } },
        { type: 'value', name: 'MB', axisLabel: { color: dark }, splitLine: { show: false } },
      ],
      series: [
        {
          name: 'CPU %',
          type: 'line',
          smooth: true,
          data: resources.map((p) => p.cpu_percent),
          lineStyle: { color: '#a78bfa' },
          itemStyle: { color: '#a78bfa' },
        },
        {
          name: '内存 MB',
          type: 'line',
          yAxisIndex: 1,
          smooth: true,
          data: resources.map((p) => p.memory_mb),
          lineStyle: { color: '#f472b6' },
          itemStyle: { color: '#f472b6' },
        },
      ],
    })
  }
}

async function pollRun() {
  if (!currentRunId.value) return
  const res = await getStressTestRun(currentRunId.value)
  currentRun.value = res.data
  await nextTick()
  updateCharts(res.data)
  if (res.data.status !== 'running' && res.data.status !== 'pending') {
    stopPolling()
    running.value = false
    await loadHistory()
    if (currentRunId.value) await loadAnalysis(currentRunId.value)
    ElMessage.success(`压测${statusLabel[res.data.status] || '结束'}`)
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(pollRun, 1000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function handleStart() {
  if (!projectId.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  if (!selectedCount.value) {
    ElMessage.warning('请勾选要压测的接口')
    return
  }
  running.value = true
  try {
    const res = await startStressTest({
      project_id: projectId.value,
      target_ids: selectedIds.value,
      variables: parseVariables(),
      users: config.value.users,
      spawn_rate: config.value.spawn_rate,
      duration_sec: config.value.duration_sec,
      think_time_ms: config.value.think_time_ms,
      token_refresh_sec: config.value.token_refresh_sec,
      name: config.value.name,
    })
    currentRunId.value = res.data.id
    currentRun.value = res.data
    await nextTick()
    initCharts()
    updateCharts(res.data)
    startPolling()
    ElMessage.success('压测已启动')
  } catch {
    running.value = false
  }
}

async function handleStop() {
  if (!currentRunId.value) return
  await stopStressTest(currentRunId.value)
  ElMessage.info('正在停止压测…')
  await pollRun()
}

function viewHistoryRun(run: StressRun) {
  currentRunId.value = run.id
  currentRun.value = run
  runAnalysis.value = run.analysis || null
  nextTick(() => {
    initCharts()
    updateCharts(run)
  })
  if (run.status === 'completed' || run.status === 'stopped') {
    loadAnalysis(run.id)
  }
}

watch(projectId, (id) => {
  if (skipProjectWatch.value) {
    skipProjectWatch.value = false
    return
  }
  if (id != null) localStorage.setItem(PROJECT_CACHE_KEY, String(id))
  loadTargets()
  loadHistory()
})

watch(variables, () => localStorage.setItem(VARIABLES_CACHE_KEY, variables.value))

onMounted(async () => {
  const handoff = consumeStressHandoff()
  try {
    const raw = localStorage.getItem(VARIABLES_CACHE_KEY)
    if (!handoff?.variables && raw?.trim()) variables.value = raw
  } catch { /* ignore */ }

  await loadProjects()

  if (handoff?.projectId && projects.value.some((p) => p.id === handoff.projectId)) {
    skipProjectWatch.value = true
    projectId.value = handoff.projectId
  }
  if (handoff?.variables) variables.value = handoff.variables

  await loadTargets()
  await loadHistory()
  await nextTick()
  initCharts()

  if (handoff?.interfaceIds?.length) {
    let replace = true
    const existingCount = targets.value.length
    if (existingCount > 0) {
      const choice = await promptImportMode(existingCount, handoff.interfaceIds.length)
      if (choice === null) return
      replace = choice
    }
    await importFromHandoff(handoff.interfaceIds, replace)
  }
})

onUnmounted(() => {
  stopPolling()
  rpsChart?.dispose()
  latencyChart?.dispose()
  resourceChart?.dispose()
})
</script>

<template>
  <div class="stress-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">接口压测</h1>
        <p class="page-desc">
          支持接口联调（登录 → token 注入）、一键配置关联；压测时会自动刷新 token。
          需先新增「登录」目标并配置关联，再压测需认证接口。
        </p>
      </div>
    </div>

    <div class="page-card toolbar">
      <el-form inline>
        <el-form-item label="项目">
          <el-select v-model="projectId" style="width:180px">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="全局变量">
          <el-input v-model="variables" style="width:320px" placeholder='{"baseUrl":"http://127.0.0.1:9000/v1"}' />
        </el-form-item>
      </el-form>
    </div>

    <div class="main-grid">
      <div class="page-card left-panel">
        <div class="panel-head">
          <h3>压测目标 <span class="muted">({{ targets.length }})</span></h3>
          <div class="panel-actions">
            <el-button type="primary" plain size="small" @click="openCreateTarget">新增</el-button>
            <el-button size="small" @click="openBulkDepDialog">一键关联</el-button>
            <el-checkbox v-model="isAllSelected">全选</el-checkbox>
            <el-button type="danger" plain size="small" :disabled="!selectedCount" @click="removeSelected">
              删除 ({{ selectedCount }})
            </el-button>
          </div>
        </div>
        <div v-loading="loading" class="target-list">
          <div v-if="!targets.length" class="empty-tip">暂无压测目标，可新增或从接口自动化导入</div>
          <div v-for="t in targets" :key="t.id" class="target-item">
            <CardCheckbox v-model="selectedMap[t.id]" />
            <div class="target-info">
              <div class="target-name">
                <el-tag size="small" :type="t.method === 'GET' ? 'success' : 'primary'">{{ t.method }}</el-tag>
                {{ t.name }}
              </div>
              <div class="target-url">{{ t.url }}</div>
              <div v-if="mappingDepLabels(t).length" class="target-deps">
                <span v-for="name in mappingDepLabels(t)" :key="name" class="dep-tag">{{ name }}</span>
              </div>
            </div>
            <div class="target-actions">
              <el-button link type="primary" size="small" @click="openDepDialog(t)">关联</el-button>
              <el-button link type="primary" size="small" :loading="debugging" @click="debugTarget(t)">联调</el-button>
              <el-button link type="primary" size="small" @click="openEditTarget(t)">编辑</el-button>
              <el-button link type="danger" size="small" @click="removeOne(t)">删除</el-button>
            </div>
          </div>
        </div>

        <div class="config-block">
          <h4>压测参数</h4>
          <el-form label-width="100px" size="small">
            <el-form-item label="并发用户">
              <el-input-number v-model="config.users" :min="1" :max="500" />
            </el-form-item>
            <el-form-item label="爬坡速率">
              <el-input-number v-model="config.spawn_rate" :min="1" :max="100" />
              <span class="field-hint">用户/秒</span>
            </el-form-item>
            <el-form-item label="持续时间">
              <el-input-number v-model="config.duration_sec" :min="5" :max="3600" />
              <span class="field-hint">秒</span>
            </el-form-item>
            <el-form-item label="思考时间">
              <el-input-number v-model="config.think_time_ms" :min="0" :max="60000" :step="100" />
              <span class="field-hint">ms</span>
            </el-form-item>
            <el-form-item label="Token 刷新">
              <el-input-number v-model="config.token_refresh_sec" :min="0" :max="3600" />
              <span class="field-hint">秒（0=仅压测开始时登录一次）</span>
            </el-form-item>
            <el-form-item label="任务名称">
              <el-input v-model="config.name" placeholder="可选" />
            </el-form-item>
          </el-form>
          <div class="run-actions">
            <el-button type="primary" :loading="running" :disabled="isLive" @click="handleStart">
              开始压测 ({{ selectedCount }})
            </el-button>
            <el-button type="danger" :disabled="!isLive" @click="handleStop">停止</el-button>
          </div>
        </div>
      </div>

      <div class="right-panel">
        <div v-if="currentRun" class="page-card metrics-card">
          <div class="metrics-head">
            <h3>{{ currentRun.name }}</h3>
            <el-tag :type="currentRun.status === 'running' ? 'warning' : currentRun.status === 'completed' ? 'success' : 'info'">
              {{ statusLabel[currentRun.status] || currentRun.status }}
            </el-tag>
          </div>

          <div class="metric-grid">
            <div class="metric-item">
              <span class="metric-label">总请求</span>
              <span class="metric-value">{{ summary.total_requests ?? 0 }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">吞吐量</span>
              <span class="metric-value accent">{{ summary.throughput ?? 0 }} <small>req/s</small></span>
            </div>
            <div class="metric-item">
              <span class="metric-label">平均响应</span>
              <span class="metric-value">{{ summary.avg_ms ?? 0 }} <small>ms</small></span>
            </div>
            <div class="metric-item">
              <span class="metric-label">P95</span>
              <span class="metric-value warn">{{ summary.p95_ms ?? 0 }} <small>ms</small></span>
            </div>
            <div class="metric-item">
              <span class="metric-label">错误率</span>
              <span class="metric-value" :class="{ danger: (summary.error_rate ?? 0) > 0 }">
                {{ summary.error_rate ?? 0 }}<small>%</small>
              </span>
            </div>
            <div class="metric-item">
              <span class="metric-label">成功 / 失败</span>
              <span class="metric-value">
                {{ summary.success_count ?? 0 }} / {{ summary.fail_count ?? 0 }}
              </span>
            </div>
          </div>

          <div v-if="currentRun.error_message" class="error-box">{{ currentRun.error_message }}</div>

          <div class="charts-row">
            <div ref="rpsChartRef" class="chart-box" />
            <div ref="latencyChartRef" class="chart-box" />
          </div>
          <div ref="resourceChartRef" class="chart-box wide" />

          <div
            v-if="runAnalysis && (currentRun.status === 'completed' || currentRun.status === 'stopped')"
            class="analysis-panel"
          >
            <div class="analysis-head">
              <h4 class="section-title">性能分析</h4>
              <div class="analysis-score">
                健康分
                <strong :class="{ good: runAnalysis.health_score >= 80, warn: runAnalysis.health_score < 80 && runAnalysis.health_score >= 60, bad: runAnalysis.health_score < 60 }">
                  {{ runAnalysis.health_score }}
                </strong>
              </div>
              <el-button
                type="primary"
                size="small"
                :loading="reportGenerating"
                :disabled="!currentRunId"
                @click="currentRunId && generateReportForRun(currentRunId)"
              >
                生成 Allure 报告
              </el-button>
            </div>
            <div class="analysis-grid">
              <div class="analysis-block">
                <h5>瓶颈</h5>
                <ul>
                  <li v-for="(b, i) in runAnalysis.bottlenecks" :key="'b'+i">{{ b.desc }}</li>
                  <li v-if="!runAnalysis.bottlenecks?.length" class="muted">暂无明显瓶颈</li>
                </ul>
              </div>
              <div class="analysis-block">
                <h5>拐点</h5>
                <ul>
                  <li v-for="(p, i) in runAnalysis.inflection_points" :key="'p'+i">{{ p.desc }}</li>
                  <li v-if="!runAnalysis.inflection_points?.length" class="muted">未检测到显著拐点</li>
                </ul>
              </div>
              <div class="analysis-block wide">
                <h5>建议</h5>
                <ul>
                  <li v-for="(r, i) in runAnalysis.recommendations" :key="'r'+i">{{ r }}</li>
                </ul>
              </div>
            </div>
          </div>

          <h4 class="section-title">接口明细</h4>
          <el-table :data="currentRun.endpoint_stats || []" size="small" stripe>
            <el-table-column prop="name" label="接口" min-width="140" />
            <el-table-column prop="method" label="方法" width="72" />
            <el-table-column prop="total" label="请求数" width="80" />
            <el-table-column label="成功/失败" width="100">
              <template #default="{ row }">{{ row.success }} / {{ row.fail }}</template>
            </el-table-column>
            <el-table-column prop="avg_ms" label="平均 ms" width="88" />
            <el-table-column prop="p95_ms" label="P95 ms" width="88" />
            <el-table-column prop="error_rate" label="错误率" width="80">
              <template #default="{ row }">{{ row.error_rate }}%</template>
            </el-table-column>
            <el-table-column label="状态码分布" min-width="160">
              <template #default="{ row }">
                <span v-for="(cnt, code) in row.status_codes" :key="code" class="code-tag">{{ code }}: {{ cnt }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-else class="page-card empty-dashboard">
          <p>配置参数并点击「开始压测」，此处将展示吞吐量、响应时延与资源曲线</p>
        </div>

        <div class="page-card history-card">
          <div class="history-head">
            <h3>最近压测</h3>
            <el-button
              v-if="currentRunId && currentRun && (currentRun.status === 'completed' || currentRun.status === 'stopped')"
              type="primary"
              size="small"
              :loading="reportGenerating"
              @click="generateReportForRun(currentRunId!)"
            >
              为当前任务生成报告
            </el-button>
          </div>
          <el-table :data="runHistory" size="small" @row-click="viewHistoryRun">
            <el-table-column prop="name" label="任务" min-width="120" />
            <el-table-column label="状态" width="88">
              <template #default="{ row }">{{ statusLabel[row.status] || row.status }}</template>
            </el-table-column>
            <el-table-column label="吞吐" width="88">
              <template #default="{ row }">{{ row.summary?.throughput ?? '-' }} req/s</template>
            </el-table-column>
            <el-table-column label="平均" width="72">
              <template #default="{ row }">{{ row.summary?.avg_ms ?? '-' }} ms</template>
            </el-table-column>
            <el-table-column label="健康分" width="72">
              <template #default="{ row }">{{ row.analysis?.health_score ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" min-width="140" />
            <el-table-column label="报告" width="100" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'completed' || row.status === 'stopped'"
                  link
                  type="primary"
                  size="small"
                  :loading="reportGenerating"
                  @click="generateReportForRun(row.id, $event)"
                >
                  生成报告
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>

    <ApiEndpointFormDialog
      v-model:visible="formDialogVisible"
      :editing-id="editingId"
      :initial="editingRow"
      entity-name="压测目标"
      @save="onTargetFormSave"
    />

    <el-dialog v-model="bulkDepDialogVisible" title="一键配置登录关联" width="560px">
      <p class="dialog-hint">
        为需要认证的压测目标配置「登录 → Bearer token」。约 <strong>{{ authRequiredCount }}</strong> 个目标可能需要认证。
        请确保列表中已有登录接口（如 POST /auth/login）。
      </p>
      <el-form label-width="120px">
        <el-form-item label="登录接口">
          <el-select v-model="bulkDepForm.auth_target_id" filterable style="width:100%">
            <el-option
              v-for="t in loginTargetCandidates"
              :key="t.id"
              :label="`${t.method} ${t.name}`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="配置范围">
          <el-radio-group v-model="bulkDepForm.scope">
            <el-radio value="all">全部需认证目标</el-radio>
            <el-radio value="selected" :disabled="!selectedCount">仅选中 ({{ selectedCount }})</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="策略">
          <el-checkbox v-model="bulkDepForm.only_unconfigured">跳过已配置</el-checkbox>
          <el-checkbox v-model="bulkDepForm.overwrite" :disabled="bulkDepForm.only_unconfigured">覆盖已有</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bulkDepDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="bulkDepSaving" @click="saveBulkDependency">应用</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="depDialogVisible" title="配置接口关联" width="760px">
      <template v-if="depTarget">
        <p class="dialog-hint">
          当前：<strong>{{ depTarget.name }}</strong>。映射示例：登录响应
          <code>body.data.access_token</code> → <code>headers.Authorization</code>，转换 <code>Bearer {'{value}'}</code>
        </p>
        <div class="mapping-list">
          <div v-for="(m, idx) in depForm.mappings" :key="idx" class="mapping-block">
            <el-select v-model="m.depends_on" placeholder="来源接口" filterable style="width:200px">
              <el-option
                v-for="t in otherTargets"
                :key="t.id"
                :label="`${t.method} ${t.name}`"
                :value="t.id"
              />
            </el-select>
            <div class="mapping-fields">
              <el-input v-model="m.source" placeholder="body.data.access_token" />
              <span class="arrow">→</span>
              <el-input v-model="m.target" placeholder="headers.Authorization" />
              <el-input v-model="m.transform" placeholder="Bearer {value}" />
            </div>
            <el-button link type="danger" @click="removeMapping(idx)">删</el-button>
          </div>
          <el-button link type="primary" @click="addMapping">+ 添加映射</el-button>
        </div>
      </template>
      <template #footer>
        <el-button @click="depDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDependency">保存</el-button>
      </template>
    </el-dialog>

    <div v-if="debugResult" class="page-card debug-panel">
      <div class="debug-head">
        <h4>联调结果：{{ debugResult.name }}</h4>
        <el-tag :type="debugResult.status_code < 400 ? 'success' : 'danger'" size="small">
          {{ debugResult.status_code || 'ERR' }}
        </el-tag>
      </div>
      <p class="debug-url">{{ debugResult.url }}</p>
      <p v-if="debugResult.error" class="debug-error">{{ debugResult.error }}</p>
      <pre v-else class="debug-body">{{ debugResult.body?.slice(0, 1500) }}</pre>
    </div>
  </div>
</template>

<style scoped>
.stress-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-desc {
  color: #9aa0a6;
  font-size: 14px;
  line-height: 1.6;
  max-width: 720px;
}

.main-grid {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 16px;
  align-items: start;
}

.left-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: calc(100vh - 200px);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-head h3 {
  color: #fff;
  font-size: 15px;
}

.muted {
  color: #6b7280;
  font-weight: normal;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.target-list {
  flex: 1;
  overflow-y: auto;
  max-height: 320px;
  border: 1px solid #2a3544;
  border-radius: 8px;
  padding: 8px;
}

.target-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  margin-bottom: 4px;
  background: #141c28;
}

.target-info {
  flex: 1;
  min-width: 0;
}

.target-actions {
  display: flex;
  flex-shrink: 0;
  gap: 2px;
}

.target-name {
  color: #e8eaed;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.target-url {
  color: #6b7280;
  font-size: 12px;
  margin-top: 4px;
  word-break: break-all;
}

.target-deps {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.dep-tag {
  font-size: 11px;
  color: #4ade80;
  background: rgba(74, 222, 128, 0.1);
  padding: 1px 6px;
  border-radius: 4px;
}

.dialog-hint {
  font-size: 13px;
  color: #9aa0a6;
  margin-bottom: 14px;
  line-height: 1.6;
}

.mapping-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mapping-block {
  display: grid;
  grid-template-columns: 200px 1fr auto;
  gap: 10px;
  align-items: start;
  padding-bottom: 12px;
  border-bottom: 1px solid #2a3544;
}

.mapping-fields {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 8px;
  align-items: center;
}

.mapping-fields .el-input:last-child {
  grid-column: 1 / -1;
}

.arrow {
  color: #6b7280;
}

.debug-panel {
  margin-top: 0;
}

.debug-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.debug-head h4 {
  color: #fff;
  font-size: 14px;
}

.debug-url {
  font-size: 12px;
  color: #60a5fa;
  font-family: monospace;
  margin: 0 0 8px;
}

.debug-error {
  color: #f87171;
  font-size: 13px;
}

.debug-body {
  margin: 0;
  padding: 10px;
  background: #0a0e14;
  border-radius: 6px;
  font-size: 12px;
  color: #d1d5db;
  white-space: pre-wrap;
  max-height: 200px;
  overflow: auto;
}

.empty-tip {
  color: #6b7280;
  text-align: center;
  padding: 24px;
  font-size: 13px;
}

.config-block h4 {
  color: #e8eaed;
  font-size: 14px;
  margin-bottom: 8px;
}

.field-hint {
  color: #6b7280;
  font-size: 12px;
  margin-left: 8px;
}

.run-actions {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}

.right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.metrics-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.metrics-head h3 {
  color: #fff;
  font-size: 16px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.metric-item {
  background: #141c28;
  border: 1px solid #2a3544;
  border-radius: 8px;
  padding: 12px 14px;
}

.metric-label {
  display: block;
  color: #6b7280;
  font-size: 12px;
  margin-bottom: 4px;
}

.metric-value {
  color: #e8eaed;
  font-size: 22px;
  font-weight: 600;
}

.metric-value small {
  font-size: 12px;
  color: #9aa0a6;
  font-weight: normal;
}

.metric-value.accent {
  color: #10b981;
}

.metric-value.warn {
  color: #f59e0b;
}

.metric-value.danger {
  color: #ef4444;
}

.error-box {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid #ef4444;
  color: #fca5a5;
  padding: 10px 12px;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
}

.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.chart-box {
  height: 240px;
  background: #141c28;
  border: 1px solid #2a3544;
  border-radius: 8px;
}

.chart-box.wide {
  height: 220px;
  margin-bottom: 16px;
}

.section-title {
  color: #e8eaed;
  font-size: 14px;
  margin-bottom: 10px;
}

.code-tag {
  display: inline-block;
  background: #1e293b;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: #94a3b8;
  margin-right: 6px;
}

.empty-dashboard {
  color: #6b7280;
  text-align: center;
  padding: 48px 24px;
  font-size: 14px;
}

.history-card h3 {
  color: #fff;
  font-size: 15px;
}

.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.analysis-panel {
  margin: 16px 0;
  padding: 14px;
  background: #141c28;
  border: 1px solid #2a3544;
  border-radius: 8px;
}

.analysis-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.analysis-head .section-title {
  margin: 0;
  flex: 1;
}

.analysis-score {
  color: #9aa0a6;
  font-size: 13px;
}

.analysis-score strong {
  font-size: 22px;
  margin-left: 6px;
}

.analysis-score strong.good { color: #22c55e; }
.analysis-score strong.warn { color: #f59e0b; }
.analysis-score strong.bad { color: #ef4444; }

.analysis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.analysis-block {
  background: #0f1419;
  border-radius: 6px;
  padding: 10px 12px;
}

.analysis-block.wide {
  grid-column: 1 / -1;
}

.analysis-block h5 {
  color: #e8eaed;
  font-size: 13px;
  margin-bottom: 8px;
}

.analysis-block ul {
  margin: 0;
  padding-left: 16px;
  color: #9aa0a6;
  font-size: 12px;
  line-height: 1.7;
}

.analysis-block .muted {
  list-style: none;
  padding-left: 0;
  color: #6b7280;
}

@media (max-width: 1100px) {
  .main-grid {
    grid-template-columns: 1fr;
  }

  .charts-row {
    grid-template-columns: 1fr;
  }
}
</style>

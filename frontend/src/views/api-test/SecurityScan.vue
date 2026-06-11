<script setup lang="ts">

import { computed, onMounted, reactive, ref, watch } from 'vue'

import { ElMessage, ElMessageBox } from 'element-plus'

import {

  getProjects,

  getSecurityMeta,

  getSecurityScanTargets,

  createSecurityScanTarget,

  updateSecurityScanTarget,

  importSecurityScanTargets,

  deleteSecurityScanTarget,

  batchDeleteSecurityScanTargets,

  runSecurityScan,

  generateSecurityReport,

} from '@/api'

import CardCheckbox from '@/components/CardCheckbox.vue'

import ApiEndpointFormDialog, { type ApiEndpointFormPayload } from '@/components/ApiEndpointFormDialog.vue'

import { consumeSecurityHandoff } from '@/utils/securityHandoff'

import { promptAllureReport, openReportUrl } from '@/utils/reportPrompt'



interface ScanTarget {

  id: number

  name: string

  method: string

  url: string

  module: string

  sort_order?: number

  source_interface_id?: number | null

  headers?: Record<string, unknown>

  params?: Record<string, unknown>

  body?: Record<string, unknown>

  response_example?: Record<string, unknown>

  description?: string

}



interface Strategy {

  id: string

  name: string

  desc: string

  severity: string

  default?: boolean

}



interface Finding {

  strategy: string

  strategy_name: string

  severity: 'high' | 'medium' | 'low' | 'info' | 'pass'

  title: string

  detail: string

  evidence: Record<string, unknown>

}



interface ScanResult {

  target_id: number

  source_interface_id?: number | null

  name: string

  method: string

  url: string

  baseline_status: number

  baseline_ok: boolean

  risk_level: string

  findings: Finding[]

  finding_count: number

  risk_count: number

}



interface ScanSummary {

  total: number

  high: number

  medium: number

  low: number

  info: number

  pass: number

}



const PROJECT_CACHE_KEY = 'api-security-project'

const VARIABLES_CACHE_KEY = 'api-security-variables'

const DEFAULT_VARIABLES = '{"baseUrl":"http://127.0.0.1:9000/v1"}'



const projects = ref<{ id: number; name: string }[]>([])

const targets = ref<ScanTarget[]>([])

const strategies = ref<Strategy[]>([])

const selectedStrategies = ref<string[]>([])

const projectId = ref<number | null>(null)

const selectedMap = reactive<Record<number, boolean>>({})

const variables = ref(DEFAULT_VARIABLES)

const loading = ref(false)

const scanning = ref(false)

const scanResults = ref<ScanResult[]>([])

const summary = ref<ScanSummary | null>(null)

const expandedIds = ref<number[]>([])

const skipProjectWatch = ref(false)

const formDialogVisible = ref(false)

const editingId = ref<number | null>(null)

const editingRow = ref<ScanTarget | null>(null)



const selectedIds = computed(() => targets.value.filter((a) => selectedMap[a.id]).map((a) => a.id))

const selectedCount = computed(() => selectedIds.value.length)

const isAllSelected = computed({

  get: () => targets.value.length > 0 && targets.value.every((a) => selectedMap[a.id]),

  set: (val: boolean) => { targets.value.forEach((a) => { selectedMap[a.id] = val }) },

})



const severityTagType = (level: string) => {

  if (level === 'high') return 'danger'

  if (level === 'medium') return 'warning'

  if (level === 'low') return 'info'

  if (level === 'info') return 'success'

  return 'success'

}



const severityLabel = (level: string) => ({

  high: '高危',

  medium: '中危',

  low: '低危',

  info: '正常',

  pass: '通过',

}[level] || level)



function resetSelection(items: ScanTarget[]) {

  Object.keys(selectedMap).forEach((k) => delete selectedMap[Number(k)])

  items.forEach((item) => { selectedMap[item.id] = false })

}



function selectTargetIds(ids: number[]) {

  const idSet = new Set(ids)

  targets.value.forEach((a) => { selectedMap[a.id] = idSet.has(a.id) })

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



async function loadMeta() {

  const res = await getSecurityMeta()

  strategies.value = res.data.strategies || []

  selectedStrategies.value = strategies.value.filter((s) => s.default).map((s) => s.id)

}



async function loadTargets(options?: { keepSelection?: boolean }) {

  if (!projectId.value) return

  const prevSelected = options?.keepSelection ? new Set(selectedIds.value) : null

  loading.value = true

  try {

    const res = await getSecurityScanTargets({ project: projectId.value, page_size: 500 })

    targets.value = (res.data.results ?? res.data)

      .sort((a: ScanTarget, b: ScanTarget) => (a.sort_order ?? 0) - (b.sort_order ?? 0))

    if (!options?.keepSelection) {

      resetSelection(targets.value)

      scanResults.value = []

      summary.value = null

    } else if (prevSelected) {

      resetSelection(targets.value)

      targets.value.forEach((a) => { selectedMap[a.id] = prevSelected.has(a.id) })

    }

  } finally {

    loading.value = false

  }

}



function buildImportMessage(data: Record<string, unknown>, replace: boolean) {
  const before = Number(data.before_count ?? 0)
  const after = Number(data.after_count ?? 0)
  const created = Number(data.created_count ?? 0)
  const updated = Number(data.updated_count ?? 0)
  const removed = Number(data.removed_count ?? 0)
  if (replace) {
    return `覆盖完成：删除 ${removed} 个 → 新建 ${created} 个（${before} → ${after}）`
  }
  if (created > 0 && updated > 0) {
    return `追加完成：新增 ${created} 个、更新 ${updated} 个（${before} → ${after}）`
  }
  if (created > 0) {
    return `追加完成：新增 ${created} 个接口（${before} → ${after}）`
  }
  if (updated > 0) {
    return `追加完成：更新 ${updated} 个已有接口，未新增（共 ${after} 个，与覆盖条数可能相同，但原有未选接口已保留）`
  }
  return `导入完成（${before} → ${after}）`
}

async function promptImportMode(existingCount: number, importCount: number): Promise<boolean | null> {
  try {
    await ElMessageBox.confirm(
      `当前已有 ${existingCount} 个扫描任务，本次将导入 ${importCount} 个接口。\n\n【覆盖】删除全部已有任务，仅保留本次选中\n【追加】保留已有任务，重复项更新、新接口追加`,
      '如何导入扫描任务？',
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
  const res = await importSecurityScanTargets({
    project_id: projectId.value,
    interface_ids: interfaceIds,
    replace,
  })
  await loadTargets()
  const imported = res.data.targets || []
  if (imported.length) {
    selectTargetIds(imported.map((t: ScanTarget) => t.id))
  }
  ElMessage.success(buildImportMessage(res.data, replace))
}



function clearScanResultsFor(deletedIds: number[]) {

  const removed = new Set(deletedIds)

  scanResults.value = scanResults.value.filter((r) => !removed.has(r.target_id))

  if (!scanResults.value.length) summary.value = null

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



function openEditTarget(row: ScanTarget) {

  editingId.value = row.id

  editingRow.value = row

  formDialogVisible.value = true

}



async function onTargetFormSave(payload: ApiEndpointFormPayload) {

  if (!projectId.value) return

  if (editingId.value) {

    await updateSecurityScanTarget(editingId.value, payload)

    ElMessage.success('已保存')

  } else {

    await createSecurityScanTarget({

      ...payload,

      project: projectId.value,

      sort_order: targets.value.length,

    })

    ElMessage.success('已新增')

  }

  formDialogVisible.value = false

  await loadTargets({ keepSelection: true })

}



async function removeOne(row: ScanTarget) {

  try {

    await ElMessageBox.confirm(`确定从扫描任务中删除「${row.name}」？`, '删除扫描任务', { type: 'warning' })

  } catch {

    return

  }

  await deleteSecurityScanTarget(row.id)

  clearScanResultsFor([row.id])

  delete selectedMap[row.id]

  ElMessage.success('已删除扫描任务')

  await loadTargets({ keepSelection: true })

}



async function removeSelected() {

  if (!selectedCount.value) {

    ElMessage.warning('请先勾选要删除的扫描任务')

    return

  }

  try {

    await ElMessageBox.confirm(

      `确定删除选中的 ${selectedCount.value} 个扫描任务？`,

      '批量删除',

      { type: 'warning' },

    )

  } catch {

    return

  }

  const ids = [...selectedIds.value]

  const res = await batchDeleteSecurityScanTargets(ids)

  clearScanResultsFor(ids)

  ids.forEach((id) => delete selectedMap[id])

  ElMessage.success(`已删除 ${res.data.deleted ?? ids.length} 个扫描任务`)

  await loadTargets({ keepSelection: true })

}



async function removeAllTargets() {

  if (!targets.value.length) {

    ElMessage.warning('当前没有扫描任务')

    return

  }

  const ids = targets.value.map((t) => t.id)

  try {

    await ElMessageBox.confirm(

      `确定清空全部 ${ids.length} 个扫描任务？接口自动化中的接口不会被删除。`,

      '一键清空',

      { type: 'warning' },

    )

  } catch {

    return

  }

  const res = await batchDeleteSecurityScanTargets(ids)

  clearScanResultsFor(ids)

  ElMessage.success(`已清空 ${res.data.deleted ?? ids.length} 个扫描任务`)

  await loadTargets()

}



function parseVariables(): Record<string, unknown> {

  try {

    return JSON.parse(variables.value || '{}')

  } catch {

    throw new Error('全局变量必须是合法 JSON')

  }

}



async function startScan() {

  if (!selectedCount.value) {

    ElMessage.warning('请至少选择一个扫描任务')

    return

  }

  if (!selectedStrategies.value.length) {

    ElMessage.warning('请至少选择一种攻击策略')

    return

  }

  let vars: Record<string, unknown>

  try {

    vars = parseVariables()

  } catch (e) {

    ElMessage.error(e instanceof Error ? e.message : '变量格式错误')

    return

  }



  scanning.value = true

  try {

    const res = await runSecurityScan({

      target_ids: selectedIds.value,

      variables: vars,

      strategies: selectedStrategies.value,

    })

    scanResults.value = res.data.results || []

    summary.value = res.data.summary || null

    expandedIds.value = scanResults.value

      .filter((r) => ['high', 'medium', 'low'].includes(r.risk_level))

      .map((r) => r.target_id)

    const high = summary.value?.high ?? 0

    const medium = summary.value?.medium ?? 0

    if (high || medium) {

      ElMessage.warning(`扫描完成：发现 ${high} 个高危、${medium} 个中危问题`)

    } else {

      ElMessage.success('扫描完成，未发现高危/中危问题')

    }

    if (await promptAllureReport('安全扫描')) {

      const reportRes = await generateSecurityReport({

        results: scanResults.value,

        summary: summary.value,

        project_id: projectId.value,

      })

      ElMessage.success('Allure 报告已生成')

      if (reportRes.data.report_url) {

        openReportUrl(reportRes.data.report_url)

      }

    }

  } finally {

    scanning.value = false

  }

}



function toggleExpand(id: number) {

  if (expandedIds.value.includes(id)) {

    expandedIds.value = expandedIds.value.filter((x) => x !== id)

  } else {

    expandedIds.value.push(id)

  }

}



function isExpanded(id: number) {

  return expandedIds.value.includes(id)

}



watch(projectId, (id) => {

  if (skipProjectWatch.value) {

    skipProjectWatch.value = false

    return

  }

  if (id != null) localStorage.setItem(PROJECT_CACHE_KEY, String(id))

  loadTargets()

})

watch(variables, () => localStorage.setItem(VARIABLES_CACHE_KEY, variables.value))



onMounted(async () => {

  const handoff = consumeSecurityHandoff()

  try {

    const raw = localStorage.getItem(VARIABLES_CACHE_KEY)

    if (!handoff?.variables && raw?.trim()) variables.value = raw

  } catch { /* ignore */ }



  await Promise.all([loadProjects(), loadMeta()])



  if (handoff?.projectId && projects.value.some((p) => p.id === handoff.projectId)) {

    skipProjectWatch.value = true

    projectId.value = handoff.projectId

  }

  if (handoff?.variables) variables.value = handoff.variables

  await loadTargets()

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

</script>



<template>

  <div class="security-page">

    <div class="page-header">

      <div>

        <h1 class="page-title">接口安全扫描</h1>

        <p class="page-desc">

          可从「接口自动化」导入，也可在本页「新增扫描目标」手动添加；

          在此删除仅移除扫描任务，<strong>不会</strong>影响接口自动化中的接口。

        </p>

      </div>

      <div v-if="summary" class="summary-cards">

        <div class="summary-card high">

          <span>高危</span>

          <strong>{{ summary.high }}</strong>

        </div>

        <div class="summary-card medium">

          <span>中危</span>

          <strong>{{ summary.medium }}</strong>

        </div>

        <div class="summary-card low">

          <span>低危</span>

          <strong>{{ summary.low }}</strong>

        </div>

        <div class="summary-card info">

          <span>正常</span>

          <strong>{{ summary.info + summary.pass }}</strong>

        </div>

      </div>

    </div>



    <div class="page-card config-card">

      <div class="toolbar">

        <el-form inline>

          <el-form-item label="项目">

            <el-select v-model="projectId" filterable style="width: 200px">

              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />

            </el-select>

          </el-form-item>

          <el-form-item label="全局变量">

            <el-input v-model="variables" style="width: 320px" placeholder='{"baseUrl":"http://127.0.0.1:9000/v1"}' />

          </el-form-item>

          <el-form-item>

            <el-button type="primary" plain @click="openCreateTarget">新增扫描目标</el-button>

            <el-button type="primary" :loading="scanning" @click="startScan">

              扫描选中 ({{ selectedCount }})

            </el-button>

          </el-form-item>

        </el-form>

      </div>



      <div class="strategy-section">

        <div class="strategy-head">

          <h3>攻击策略</h3>

          <span>勾选需要执行的检测项</span>

        </div>

        <el-checkbox-group v-model="selectedStrategies" class="strategy-grid">

          <label

            v-for="s in strategies"

            :key="s.id"

            class="strategy-item"

            :class="`severity-${s.severity}`"

          >

            <el-checkbox :value="s.id">

              <div class="strategy-content">

                <div class="strategy-title">

                  {{ s.name }}

                  <el-tag size="small" :type="severityTagType(s.severity)">{{ severityLabel(s.severity) }}</el-tag>

                </div>

                <p>{{ s.desc }}</p>

              </div>

            </el-checkbox>

          </label>

        </el-checkbox-group>

      </div>

    </div>



    <div class="page-card">

      <div class="table-toolbar">

        <CardCheckbox

          v-model="isAllSelected"

          :indeterminate="selectedCount > 0 && selectedCount < targets.length"

        />

        <span v-if="targets.length" class="table-hint">

          扫描任务 {{ targets.length }} 个（独立快照）

        </span>

        <span v-else class="table-hint">

          暂无扫描任务，请先在「接口自动化」勾选接口并点击「安全扫描」

        </span>

        <div class="table-actions">

          <el-button

            v-if="targets.length"

            type="danger"

            plain

            @click="removeAllTargets"

          >

            一键清空 ({{ targets.length }})

          </el-button>

          <el-button type="danger" plain :disabled="!selectedCount" @click="removeSelected">

            批量删除 ({{ selectedCount }})

          </el-button>

        </div>

      </div>



      <el-table v-loading="loading" :data="targets" stripe border>

        <el-table-column width="52">

          <template #header>

            <CardCheckbox

              v-model="isAllSelected"

              :indeterminate="selectedCount > 0 && selectedCount < targets.length"

              size="sm"

            />

          </template>

          <template #default="{ row }">

            <CardCheckbox v-model="selectedMap[row.id]" size="sm" />

          </template>

        </el-table-column>

        <el-table-column type="index" label="#" width="56" />

        <el-table-column prop="method" label="方法" width="88">

          <template #default="{ row }">

            <el-tag size="small" :type="row.method === 'GET' ? 'success' : 'primary'">{{ row.method }}</el-tag>

          </template>

        </el-table-column>

        <el-table-column prop="name" label="接口名称" min-width="140" show-overflow-tooltip />

        <el-table-column prop="url" label="URL" min-width="220" show-overflow-tooltip />

        <el-table-column prop="module" label="模块" width="100" show-overflow-tooltip />

        <el-table-column label="操作" width="120" fixed="right">

          <template #default="{ row }">

            <el-button link type="primary" @click="openEditTarget(row)">编辑</el-button>

            <el-button link type="danger" @click="removeOne(row)">删除</el-button>

          </template>

        </el-table-column>

      </el-table>

      <el-empty

        v-if="!targets.length && !loading"

        description="暂无扫描目标，可新增或从接口自动化导入"

      />

    </div>



    <ApiEndpointFormDialog

      v-model:visible="formDialogVisible"

      :editing-id="editingId"

      :initial="editingRow"

      entity-name="扫描目标"

      @save="onTargetFormSave"

    />



    <div v-if="scanResults.length" class="page-card results-panel">

      <div class="section-head">

        <h3>扫描报告</h3>

        <span>共扫描 {{ scanResults.length }} 个接口</span>

      </div>



      <div v-for="item in scanResults" :key="item.target_id" class="result-card">

        <div class="result-card-head" @click="toggleExpand(item.target_id)">

          <el-tag :type="severityTagType(item.risk_level)" size="small">

            {{ severityLabel(item.risk_level) }}

          </el-tag>

          <strong>{{ item.method }} {{ item.name }}</strong>

          <span class="result-url">{{ item.url }}</span>

          <span class="result-meta">

            基线 {{ item.baseline_status || 'ERR' }} · {{ item.finding_count }} 项发现

          </span>

          <el-icon class="expand-icon" :class="{ expanded: isExpanded(item.target_id) }">

            <ArrowDown />

          </el-icon>

        </div>



        <div v-show="isExpanded(item.target_id)" class="result-card-body">

          <div v-if="!item.findings.length" class="no-findings">未产生检测结果</div>

          <div v-for="(f, idx) in item.findings" :key="idx" class="finding-item" :class="`finding-${f.severity}`">

            <div class="finding-head">

              <el-tag size="small" :type="severityTagType(f.severity)">{{ severityLabel(f.severity) }}</el-tag>

              <strong>{{ f.title }}</strong>

              <span class="finding-strategy">{{ f.strategy_name }}</span>

            </div>

            <p class="finding-detail">{{ f.detail }}</p>

            <pre v-if="f.evidence" class="finding-evidence">{{ JSON.stringify(f.evidence, null, 2) }}</pre>

          </div>

        </div>

      </div>

    </div>

  </div>

</template>



<style scoped>

.security-page {

  display: flex;

  flex-direction: column;

  gap: 20px;

}



.page-header {

  display: flex;

  justify-content: space-between;

  align-items: flex-start;

  gap: 16px;

}



.page-desc {

  color: #9aa0a6;

  font-size: 14px;

  line-height: 1.6;

  max-width: 720px;

}



.page-desc strong {

  color: #f59e0b;

  font-weight: 600;

}



.summary-cards {

  display: flex;

  gap: 10px;

  flex-shrink: 0;

}



.summary-card {

  min-width: 72px;

  padding: 10px 14px;

  border-radius: 10px;

  text-align: center;

  border: 1px solid #2a3544;

  background: #141c28;

}



.summary-card span {

  display: block;

  font-size: 12px;

  color: #9aa0a6;

  margin-bottom: 4px;

}



.summary-card strong {

  font-size: 22px;

}



.summary-card.high strong { color: #ef4444; }

.summary-card.medium strong { color: #f59e0b; }

.summary-card.low strong { color: #3b82f6; }

.summary-card.info strong { color: #10b981; }



.config-card {

  display: flex;

  flex-direction: column;

  gap: 20px;

}



.strategy-section {

  border-top: 1px solid #2a3544;

  padding-top: 16px;

}



.strategy-head {

  display: flex;

  align-items: baseline;

  gap: 12px;

  margin-bottom: 12px;

}



.strategy-head h3 {

  color: #fff;

  font-size: 15px;

}



.strategy-head span {

  color: #9aa0a6;

  font-size: 12px;

}



.strategy-grid {

  display: grid;

  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));

  gap: 10px;

}



.strategy-item {

  display: block;

  padding: 12px 14px;

  border: 1px solid #2a3544;

  border-radius: 10px;

  background: #141c28;

  cursor: pointer;

  transition: border-color 0.2s;

}



.strategy-item:hover {

  border-color: #3b4a5f;

}



.strategy-item :deep(.el-checkbox) {

  align-items: flex-start;

  height: auto;

  white-space: normal;

}



.strategy-content {

  margin-left: 4px;

}



.strategy-title {

  display: flex;

  align-items: center;

  gap: 8px;

  color: #fff;

  font-weight: 600;

  margin-bottom: 4px;

}



.strategy-content p {

  color: #9aa0a6;

  font-size: 12px;

  line-height: 1.5;

}



.table-toolbar {

  display: flex;

  align-items: center;

  gap: 10px;

  margin-bottom: 12px;

  flex-wrap: wrap;

}



.table-hint {

  color: #9aa0a6;

  font-size: 13px;

  flex: 1;

  min-width: 200px;

}



.table-actions {

  display: flex;

  align-items: center;

  gap: 8px;

  margin-left: auto;

}



.section-head {

  display: flex;

  align-items: baseline;

  gap: 12px;

  margin-bottom: 16px;

}



.section-head h3 {

  color: #fff;

  font-size: 16px;

}



.section-head span {

  color: #9aa0a6;

  font-size: 12px;

}



.result-card {

  border: 1px solid #2a3544;

  border-radius: 10px;

  overflow: hidden;

  margin-bottom: 12px;

  background: #141c28;

}



.result-card-head {

  display: flex;

  align-items: center;

  gap: 10px;

  padding: 12px 14px;

  cursor: pointer;

  flex-wrap: wrap;

}



.result-card-head:hover {

  background: #1a2332;

}



.result-card-head strong {

  color: #fff;

}



.result-url {

  color: #9aa0a6;

  font-size: 12px;

  flex: 1;

  min-width: 120px;

  overflow: hidden;

  text-overflow: ellipsis;

  white-space: nowrap;

}



.result-meta {

  color: #6b7280;

  font-size: 12px;

}



.expand-icon {

  transition: transform 0.2s;

  color: #9aa0a6;

}



.expand-icon.expanded {

  transform: rotate(180deg);

}



.result-card-body {

  border-top: 1px solid #2a3544;

  padding: 12px 14px;

  display: flex;

  flex-direction: column;

  gap: 10px;

}



.no-findings {

  color: #9aa0a6;

  font-size: 13px;

}



.finding-item {

  padding: 12px;

  border-radius: 8px;

  border: 1px solid #2a3544;

  background: #1a2332;

}



.finding-item.finding-high {

  border-color: #ef444444;

  background: #ef444410;

}



.finding-item.finding-medium {

  border-color: #f59e0b44;

  background: #f59e0b10;

}



.finding-head {

  display: flex;

  align-items: center;

  gap: 8px;

  flex-wrap: wrap;

  margin-bottom: 6px;

}



.finding-head strong {

  color: #fff;

}



.finding-strategy {

  color: #6b7280;

  font-size: 12px;

}



.finding-detail {

  color: #cbd5e1;

  font-size: 13px;

  line-height: 1.5;

  margin-bottom: 8px;

}



.finding-evidence {

  background: #0f1419;

  border-radius: 6px;

  padding: 10px;

  font-size: 12px;

  color: #10b981;

  overflow: auto;

  max-height: 200px;

}

</style>



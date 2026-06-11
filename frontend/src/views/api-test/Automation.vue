<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import draggable from 'vuedraggable'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getProjects, getApiInterfaces, createApiInterface, updateApiInterface,
  deleteApiInterface, batchDeleteApiInterfaces,
  runApiAutomation, generateApiPythonCode, debugApiInterface,
  batchConfigureApiDeps, generateAutomationReport,
} from '@/api'
import CardCheckbox from '@/components/CardCheckbox.vue'
import ApiEndpointFormDialog, { type ApiEndpointFormPayload } from '@/components/ApiEndpointFormDialog.vue'
import { saveSecurityHandoff } from '@/utils/securityHandoff'
import { saveStressHandoff } from '@/utils/stressHandoff'
import { promptAllureReport, openReportUrl } from '@/utils/reportPrompt'

const router = useRouter()

interface ApiItem {
  id: number
  name: string
  method: string
  url: string
  module: string
  headers: Record<string, unknown>
  params: Record<string, unknown>
  body: Record<string, unknown>
  response_example: Record<string, unknown>
  description: string
  sort_order: number
  depends_on: number | null
  depends_on_name: string | null
  dependency_mappings: MappingItem[]
}

interface MappingItem {
  depends_on: number | null
  source: string
  target: string
  transform?: string
}

interface RunResult {
  interface_id: number
  name: string
  method: string
  url: string
  success: boolean
  status_code: number
  body: string
  error: string
}

const VARIABLES_CACHE_KEY = 'api-automation-variables'
const PROJECT_CACHE_KEY = 'api-automation-project'
const DEFAULT_VARIABLES = '{"baseUrl":"http://127.0.0.1:9000/v1"}'

const projects = ref<{ id: number; name: string }[]>([])
const apis = ref<ApiItem[]>([])
const projectId = ref<number | null>(null)
const selectedMap = reactive<Record<number, boolean>>({})
const variables = ref(DEFAULT_VARIABLES)
const loading = ref(false)
const running = ref(false)
const generating = ref(false)
const runResults = ref<RunResult[]>([])
const pythonCode = ref('')
const showPython = ref(false)

const editDialogVisible = ref(false)
const editingId = ref<number | null>(null)
const editingRow = ref<ApiItem | null>(null)

const depDialogVisible = ref(false)
const depTarget = ref<ApiItem | null>(null)
const depForm = ref({
  mappings: [] as MappingItem[],
})

const bulkDepDialogVisible = ref(false)
const bulkDepSaving = ref(false)
const bulkDepForm = ref({
  auth_api_id: null as number | null,
  only_unconfigured: true,
  overwrite: false,
  scope: 'all' as 'all' | 'selected',
})

const selectedIds = computed(() => apis.value.filter((a) => selectedMap[a.id]).map((a) => a.id))
const selectedCount = computed(() => selectedIds.value.length)
const isAllSelected = computed({
  get: () => apis.value.length > 0 && apis.value.every((a) => selectedMap[a.id]),
  set: (val: boolean) => { apis.value.forEach((a) => { selectedMap[a.id] = val }) },
})

const otherApis = computed(() =>
  apis.value.filter((a) => !depTarget.value || a.id !== depTarget.value.id),
)

const loginApiCandidates = computed(() =>
  apis.value.filter((a) => {
    const url = (a.url || '').toLowerCase()
    return a.method === 'POST' && (url.includes('/auth/login') || url.endsWith('/login') || a.name.includes('登录'))
  }),
)

const authRequiredCount = computed(() =>
  apis.value.filter((a) => {
    const url = (a.url || '').toLowerCase()
    if (url.includes('/auth/') || url.endsWith('/login')) return false
    const headers = a.headers || {}
    const hasAuthHeader = Object.keys(headers).some((k) => k.toLowerCase() === 'authorization')
      || Object.values(headers).some((v) => typeof v === 'string' && v.toLowerCase().includes('bearer'))
    const protectedUrl = ['/users/', '/products', '/cart', '/orders'].some((p) => url.includes(p))
    return hasAuthHeader || protectedUrl
  }).length,
)

function resetSelection(items: ApiItem[]) {
  Object.keys(selectedMap).forEach((k) => delete selectedMap[Number(k)])
  items.forEach((item) => { selectedMap[item.id] = false })
}

function orderedSelectedIds(): number[] {
  const set = new Set(selectedIds.value)
  return apis.value.filter((a) => set.has(a.id)).map((a) => a.id)
}

async function loadProjects() {
  const res = await getProjects()
  projects.value = res.data.results ?? res.data
  const cachedProject = localStorage.getItem(PROJECT_CACHE_KEY)
  if (cachedProject && projects.value.some((p) => p.id === Number(cachedProject))) {
    projectId.value = Number(cachedProject)
  } else {
    projectId.value = projects.value[0]?.id ?? null
  }
}

function loadVariablesCache() {
  try {
    const raw = localStorage.getItem(VARIABLES_CACHE_KEY)
    if (raw?.trim()) variables.value = raw
  } catch {
    variables.value = DEFAULT_VARIABLES
  }
}

function saveVariablesCache() {
  localStorage.setItem(VARIABLES_CACHE_KEY, variables.value)
}

watch(variables, saveVariablesCache)
watch(projectId, (id) => {
  if (id != null) localStorage.setItem(PROJECT_CACHE_KEY, String(id))
})

async function loadApis() {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await getApiInterfaces({ project: projectId.value, page_size: 500 })
    apis.value = (res.data.results ?? res.data)
      .map((a: ApiItem) => ({ ...a, dependency_mappings: a.dependency_mappings || [] }))
      .sort((a: ApiItem, b: ApiItem) => a.sort_order - b.sort_order)
    resetSelection(apis.value)
  } finally {
    loading.value = false
  }
}

async function onDragEnd() {
  apis.value = apis.value.map((item, index) => ({ ...item, sort_order: index }))
  try {
    await Promise.all(
      apis.value.map((a, index) => updateApiInterface(a.id, { sort_order: index })),
    )
    ElMessage.success('排序已保存')
  } catch {
    ElMessage.error('排序保存失败')
    await loadApis()
  }
}

function openCreate() {
  if (!projectId.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  editingId.value = null
  editingRow.value = null
  editDialogVisible.value = true
}

function openEdit(row: ApiItem) {
  editingId.value = row.id
  editingRow.value = row
  editDialogVisible.value = true
}

async function onFormSave(payload: ApiEndpointFormPayload) {
  if (!projectId.value) return
  if (editingId.value) {
    await updateApiInterface(editingId.value, payload)
    ElMessage.success('已保存')
  } else {
    await createApiInterface({
      ...payload,
      project: projectId.value,
      sort_order: apis.value.length,
    })
    ElMessage.success('已新增')
  }
  editDialogVisible.value = false
  await loadApis()
}

function defaultLoginId() {
  return loginApiCandidates.value[0]?.id ?? null
}

function openDepDialog(row: ApiItem) {
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

function mappingDepLabels(row: ApiItem) {
  const ids = new Set<number>()
  row.dependency_mappings?.forEach((m) => {
    if (m.depends_on) ids.add(m.depends_on)
  })
  if (row.depends_on) ids.add(row.depends_on)
  return [...ids]
    .map((id) => apis.value.find((a) => a.id === id))
    .filter(Boolean)
    .map((a) => a!.name)
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
  await updateApiInterface(depTarget.value.id, {
    depends_on: mappings[0]?.depends_on ?? null,
    dependency_mappings: mappings,
  })
  ElMessage.success('关联配置已保存')
  depDialogVisible.value = false
  await loadApis()
}

function openBulkDepDialog() {
  bulkDepForm.value = {
    auth_api_id: loginApiCandidates.value[0]?.id ?? null,
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
      auth_api_id: bulkDepForm.value.auth_api_id,
      only_unconfigured: bulkDepForm.value.only_unconfigured,
      overwrite: bulkDepForm.value.overwrite,
    }
    if (bulkDepForm.value.scope === 'selected' && selectedIds.value.length) {
      payload.interface_ids = selectedIds.value
    }
    const res = await batchConfigureApiDeps(payload)
    const { updated_count, auth_api_name } = res.data
    ElMessage.success(`已为 ${updated_count} 个接口配置登录关联（登录接口：${auth_api_name}）`)
    bulkDepDialogVisible.value = false
    await loadApis()
  } finally {
    bulkDepSaving.value = false
  }
}

async function runSelected() {
  const ids = orderedSelectedIds()
  if (!ids.length) {
    ElMessage.warning('请先勾选要执行的接口')
    return
  }
  running.value = true
  runResults.value = []
  try {
    let vars = {}
    try { vars = JSON.parse(variables.value) } catch { /* ignore */ }
    const res = await runApiAutomation({ interface_ids: ids, variables: vars })
    runResults.value = res.data.results ?? []
    const { passed, failed, total } = res.data
    ElMessage.success(`执行完成：${passed}/${total} 通过${failed ? `，${failed} 失败` : ''}（按列表顺序）`)
    if (await promptAllureReport('接口自动化执行')) {
      const reportRes = await generateAutomationReport({
        results: runResults.value,
        project_id: projectId.value,
      })
      ElMessage.success('Allure 报告已生成')
      if (reportRes.data.report_url) {
        openReportUrl(reportRes.data.report_url)
      }
    }
  } finally {
    running.value = false
  }
}

async function runSingle(row: ApiItem) {
  running.value = true
  try {
    let vars = {}
    try { vars = JSON.parse(variables.value) } catch { /* ignore */ }
    const res = await debugApiInterface(row.id, { variables: vars })
    runResults.value = [{
      interface_id: row.id,
      name: row.name,
      method: row.method,
      url: res.data.url || row.url,
      success: (res.data.status_code ?? 0) < 400 && !res.data.error,
      status_code: res.data.status_code ?? 0,
      body: res.data.body ?? '',
      error: res.data.error ?? '',
    }]
  } finally {
    running.value = false
  }
}

async function handleGeneratePython() {
  const ids = orderedSelectedIds()
  if (!ids.length) {
    ElMessage.warning('请先勾选接口')
    return
  }
  generating.value = true
  try {
    let vars: Record<string, unknown> = {}
    try {
      vars = JSON.parse(variables.value)
    } catch {
      ElMessage.warning('全局变量不是合法 JSON，将使用默认 baseUrl')
    }
    const res = await generateApiPythonCode({ interface_ids: ids, variables: vars })
    pythonCode.value = res.data.code ?? ''
    showPython.value = true
  } finally {
    generating.value = false
  }
}

function copyPython() {
  navigator.clipboard.writeText(pythonCode.value)
  ElMessage.success('已复制到剪贴板')
}

function downloadPython() {
  if (!pythonCode.value) return
  const blob = new Blob([pythonCode.value], { type: 'text/x-python;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'api_automation.py'
  link.click()
  URL.revokeObjectURL(url)
  ElMessage.success('已下载 api_automation.py')
}

async function removeOne(row: ApiItem) {
  try {
    await ElMessageBox.confirm(`确定删除接口「${row.name}」？`, '删除接口', { type: 'warning' })
  } catch {
    return
  }
  await deleteApiInterface(row.id)
  ElMessage.success('已删除')
  await loadApis()
}

async function removeSelected() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选要删除的接口')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedIds.value.length} 个接口？关联配置将一并清除。`,
      '批量删除',
      { type: 'warning' },
    )
  } catch {
    return
  }
  const res = await batchDeleteApiInterfaces(selectedIds.value)
  ElMessage.success(`已删除 ${res.data.deleted ?? selectedIds.value.length} 个接口`)
  await loadApis()
}

async function goSecurityScan() {
  if (!selectedCount.value) {
    ElMessage.warning('请先勾选要扫描的接口')
    return
  }
  if (!projectId.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  saveSecurityHandoff({
    projectId: projectId.value,
    interfaceIds: orderedSelectedIds(),
    variables: variables.value,
  })
  router.push('/test-execution/security')
}

async function goStressTest() {
  if (!selectedCount.value) {
    ElMessage.warning('请先勾选要压测的接口')
    return
  }
  if (!projectId.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  saveStressHandoff({
    projectId: projectId.value,
    interfaceIds: orderedSelectedIds(),
    variables: variables.value,
  })
  router.push('/test-execution/stress')
}

onMounted(async () => {
  loadVariablesCache()
  await loadProjects()
  await loadApis()
})
</script>

<template>
  <div class="automation-page">
    <div class="page-card toolbar">
      <el-form inline>
        <el-form-item label="项目">
          <el-select v-model="projectId" style="width:180px" @change="loadApis">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="全局变量">
          <el-input
            v-model="variables"
            style="width:360px"
            placeholder='{"baseUrl":"http://127.0.0.1:9000/v1"}'
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" plain @click="openCreate">新增接口</el-button>
          <el-button type="primary" :loading="running" @click="runSelected">
            执行选中 ({{ selectedCount }})
          </el-button>
          <el-button type="warning" :disabled="!selectedCount" @click="goSecurityScan">
            安全扫描 ({{ selectedCount }})
          </el-button>
          <el-button type="danger" plain :disabled="!selectedCount" @click="goStressTest">
            压测 ({{ selectedCount }})
          </el-button>
          <el-button @click="openBulkDepDialog">一键配置关联</el-button>
          <el-button type="success" :loading="generating" @click="handleGeneratePython">生成可执行脚本</el-button>
          <el-button type="danger" plain :disabled="!selectedCount" @click="removeSelected">
            批量删除 ({{ selectedCount }})
          </el-button>
        </el-form-item>
      </el-form>
      <p class="hint">
        拖拽左侧手柄调整顺序；「执行选中」按列表从上到下依次执行。「安全扫描」会复制选中接口到安全扫描页（独立快照，不影响本页接口）。
        baseUrl 示例：http://127.0.0.1:9000/v1
      </p>
    </div>

    <div class="page-card">
      <p class="drag-hint">
        <el-icon><Rank /></el-icon> 拖拽 ≡ 调整执行顺序 · 勾选后按当前列表顺序批量执行
      </p>

      <div v-loading="loading" class="drag-table-wrap">
        <div class="drag-table-scroll">
          <div class="drag-table-head row-grid">
            <div class="cell cell-drag" />
            <div class="cell cell-check">
              <CardCheckbox
                v-model="isAllSelected"
                :indeterminate="selectedCount > 0 && selectedCount < apis.length"
                size="sm"
              />
            </div>
            <div class="cell cell-no">序号</div>
            <div class="cell cell-method">方法</div>
            <div class="cell cell-name">接口名称</div>
            <div class="cell cell-url">URL</div>
            <div class="cell">模块</div>
            <div class="cell cell-dep">关联</div>
            <div class="cell cell-actions">操作</div>
          </div>

          <draggable
            v-if="apis.length"
            v-model="apis"
            item-key="id"
            handle=".drag-handle"
            :animation="200"
            ghost-class="row-drag-ghost"
            class="drag-table-body"
            @end="onDragEnd"
          >
            <template #item="{ element, index }">
              <div class="drag-table-row row-grid" :class="{ stripe: index % 2 === 1 }">
                <div class="cell cell-drag">
                  <span class="drag-handle" title="拖拽排序"><el-icon><Rank /></el-icon></span>
                </div>
                <div class="cell cell-check" @click.stop>
                  <CardCheckbox v-model="selectedMap[element.id]" size="sm" />
                </div>
                <div class="cell cell-no">{{ index + 1 }}</div>
                <div class="cell cell-method">
                  <el-tag size="small" :type="element.method === 'GET' ? 'success' : 'primary'">{{ element.method }}</el-tag>
                </div>
                <div class="cell cell-name" :title="element.name">{{ element.name }}</div>
                <div class="cell cell-url" :title="element.url">{{ element.url }}</div>
                <div class="cell" :title="element.module">{{ element.module || '—' }}</div>
                <div class="cell cell-dep">
                  <span
                    v-for="name in mappingDepLabels(element)"
                    :key="name"
                    class="dep-name"
                  >{{ name }}</span>
                  <el-button link type="primary" @click="openDepDialog(element)">关联</el-button>
                </div>
                <div class="cell cell-actions">
                  <el-button link type="primary" @click="openEdit(element)">编辑</el-button>
                  <el-button link type="primary" :loading="running" @click="runSingle(element)">调试</el-button>
                  <el-button link type="danger" @click="removeOne(element)">删除</el-button>
                </div>
              </div>
            </template>
          </draggable>

          <el-empty v-if="!apis.length && !loading" description="暂无接口，可「新增接口」或从「接口文档解析」导入" />
        </div>
      </div>
    </div>

    <div v-if="runResults.length" class="page-card results-panel">
      <h3>执行结果</h3>
      <div v-for="r in runResults" :key="r.interface_id + r.url" class="result-item" :class="{ fail: !r.success }">
        <div class="result-head">
          <el-tag :type="r.success ? 'success' : 'danger'" size="small">{{ r.status_code || 'ERR' }}</el-tag>
          <strong>{{ r.method }} {{ r.name }}</strong>
          <span class="result-url">{{ r.url }}</span>
        </div>
        <p v-if="r.error" class="error-text">{{ r.error }}</p>
        <pre v-else-if="r.body" class="result-body">{{ r.body?.slice(0, 2000) }}</pre>
        <p v-else class="error-text">请求失败（HTTP {{ r.status_code }}）</p>
      </div>
    </div>

    <ApiEndpointFormDialog
      v-model:visible="editDialogVisible"
      :editing-id="editingId"
      :initial="editingRow"
      @save="onFormSave"
    />

    <el-dialog v-model="bulkDepDialogVisible" title="一键配置接口关联" width="560px">
      <p class="dialog-hint">
        自动为需要 <code>Authorization</code> 的接口配置「用户登录 → Bearer token」关联。
        当前项目约 <strong>{{ authRequiredCount }}</strong> 个接口需要认证。
      </p>
      <el-form label-width="120px">
        <el-form-item label="登录接口">
          <el-select v-model="bulkDepForm.auth_api_id" placeholder="自动识别登录接口" filterable style="width:100%">
            <el-option
              v-for="a in loginApiCandidates"
              :key="a.id"
              :label="`${a.method} ${a.name}`"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="配置范围">
          <el-radio-group v-model="bulkDepForm.scope">
            <el-radio value="all">全部需认证接口</el-radio>
            <el-radio value="selected" :disabled="!selectedCount">仅选中 ({{ selectedCount }})</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="配置策略">
          <el-checkbox v-model="bulkDepForm.only_unconfigured">跳过已配置关联的接口</el-checkbox>
          <el-checkbox v-model="bulkDepForm.overwrite" :disabled="bulkDepForm.only_unconfigured">覆盖已有配置</el-checkbox>
        </el-form-item>
        <el-form-item label="默认映射">
          <div class="mapping-preview">
            <code>body.data.access_token</code>
            <span class="arrow">→</span>
            <code>headers.Authorization</code>
            <div class="mapping-transform">Bearer {'{value}'}</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bulkDepDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="bulkDepSaving" @click="saveBulkDependency">应用配置</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="depDialogVisible" title="配置接口关联" width="760px">
      <template v-if="depTarget">
        <p class="dialog-hint">
          当前接口：<strong>{{ depTarget.name }}</strong>。
          每条映射可指定不同来源接口，例如 token 来自登录、order_id 来自创建订单。
        </p>
        <el-form label-width="0">
          <el-form-item>
            <div class="mapping-list mapping-list-multi">
              <div v-for="(m, idx) in depForm.mappings" :key="idx" class="mapping-block">
                <el-select
                  v-model="m.depends_on"
                  placeholder="来源接口"
                  filterable
                  class="mapping-source-api"
                >
                  <el-option
                    v-for="a in otherApis"
                    :key="a.id"
                    :label="`${a.method} ${a.name}`"
                    :value="a.id"
                  />
                </el-select>
                <div class="mapping-fields">
                  <el-input v-model="m.source" placeholder="来源字段：body.data.access_token" />
                  <span class="arrow">→</span>
                  <el-input v-model="m.target" placeholder="目标：headers.Authorization 或 url.order_id" />
                  <el-input
                    v-model="m.transform"
                    placeholder="转换：Bearer {value}（可选）"
                  />
                </div>
                <el-button link type="danger" @click="removeMapping(idx)">删除</el-button>
              </div>
              <el-button link type="primary" @click="addMapping">+ 添加映射</el-button>
            </div>
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="depDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDependency">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showPython" title="接口自动化脚本（可直接执行）" width="760px">
      <p class="dialog-hint">按当前列表勾选顺序生成，保存为 <code>api_automation.py</code> 后运行：<code>python api_automation.py</code>（需 <code>pip install requests</code>）</p>
      <pre class="python-code">{{ pythonCode }}</pre>
      <template #footer>
        <el-button @click="showPython = false">关闭</el-button>
        <el-button @click="copyPython">复制代码</el-button>
        <el-button type="primary" @click="downloadPython">下载 .py 文件</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.automation-page { display: flex; flex-direction: column; gap: 16px; }
.hint, .drag-hint { font-size: 12px; color: #6b7280; margin: 8px 0 0; }
.drag-hint { display: flex; align-items: center; gap: 6px; margin-bottom: 12px; color: #9aa0a6; }
.dep-name { font-size: 12px; color: #4ade80; margin-right: 4px; }
.row-grid {
  display: grid;
  grid-template-columns: 36px 40px 48px 72px minmax(100px, 1.2fr) minmax(140px, 2fr) 80px 100px 180px;
  align-items: center;
  gap: 8px;
}
.drag-table-head {
  padding: 10px 12px;
  background: #1a2332;
  border-radius: 8px 8px 0 0;
  font-size: 12px;
  color: #9aa0a6;
  font-weight: 600;
}
.drag-table-row {
  padding: 10px 12px;
  border-bottom: 1px solid #2a3544;
  font-size: 13px;
  color: #e5e7eb;
}
.drag-table-row.stripe { background: #0f141980; }
.drag-table-body { min-height: 40px; }
.drag-handle {
  cursor: grab;
  color: #6b7280;
  display: inline-flex;
  padding: 4px;
}
.drag-handle:active { cursor: grabbing; }
.row-drag-ghost { opacity: 0.5; background: #1e3a5f; }
.cell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cell-url { font-family: monospace; font-size: 12px; color: #60a5fa; }
.cell-actions { white-space: nowrap; }
.results-panel h3 { color: #fff; margin: 0 0 12px; }
.result-item {
  padding: 12px; margin-bottom: 8px; background: #0f1419;
  border: 1px solid #2a3544; border-radius: 8px;
}
.result-item.fail { border-color: #7f1d1d; }
.result-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.result-head strong { color: #f3f4f6; }
.result-url { font-size: 12px; color: #60a5fa; font-family: monospace; }
.result-body, .python-code {
  margin: 0; padding: 10px; background: #0a0e14; border-radius: 6px;
  font-size: 12px; color: #d1d5db; overflow-x: auto; white-space: pre-wrap; max-height: 400px;
}
.error-text { color: #f87171; font-size: 13px; margin: 0; }
.dialog-hint { font-size: 13px; color: #9aa0a6; margin-bottom: 16px; }
.mapping-list { width: 100%; }
.mapping-list-multi .mapping-block {
  display: grid;
  grid-template-columns: 200px 1fr auto;
  gap: 10px;
  align-items: start;
  margin-bottom: 14px;
  padding-bottom: 14px;
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
.mapping-row {
  display: grid; grid-template-columns: 1fr auto 1fr auto; gap: 8px; align-items: start;
  margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #2a3544;
}
.mapping-row .el-input:nth-child(3) { grid-column: 1 / -1; }
.arrow { color: #6b7280; }
.cell-dep { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.mapping-preview {
  padding: 10px 12px; background: #0f1419; border-radius: 8px; font-size: 13px; color: #d1d5db;
}
.mapping-preview code { color: #60a5fa; }
.mapping-transform { margin-top: 6px; color: #9aa0a6; font-size: 12px; }
</style>

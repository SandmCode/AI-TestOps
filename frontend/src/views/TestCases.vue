<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import draggable from 'vuedraggable'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getTestCases,
  getProjects,
  createTestCase,
  updateTestCase,
  deleteTestCase,
  batchDeleteTestCases,
  batchUpdateTestCaseStatus,
  reorderTestCases,
  exportTestCasesExcel,
} from '@/api'
import CardCheckbox from '@/components/CardCheckbox.vue'
import AiGenerateCasesDialog from '@/components/AiGenerateCasesDialog.vue'
import { useAiCaseGenerationTask } from '@/composables/useAiCaseGenerationTask'

const route = useRoute()
const aiGenTask = useAiCaseGenerationTask(() => loadData())

interface TestCaseItem {
  id: number
  title: string
  case_no?: string
  module?: string
  precondition?: string
  steps: string
  expected: string
  postcondition?: string
  actual: string
  priority: string
  executor: string
  passed: boolean | null
  project: number
  project_name: string
  test_point_name?: string
  sort_order: number
  created_at: string
}

interface ProjectItem { id: number; name: string }

const cases = ref<TestCaseItem[]>([])
const projects = ref<ProjectItem[]>([])
const loading = ref(false)
const exporting = ref(false)
const batchStatusLoading = ref(false)
const dialogVisible = ref(false)
const aiDialogVisible = ref(false)
const editingId = ref<number | null>(null)
const selectedMap = reactive<Record<number, boolean>>({})
const showFilter = ref(true)

const filters = ref({
  project: null as number | null,
  field_search: '',
  priority: '',
  passed_status: '',
  module: '',
  case_no: '',
  executor: '',
  created_after: '',
  created_before: '',
})

const emptyForm = () => ({
  project: null as number | null,
  case_no: '',
  title: '',
  module: '',
  priority: 'P2',
  precondition: '',
  steps: '',
  expected: '',
  postcondition: '',
  executor: '',
  passed: null as boolean | null,
  actual: '',
})

const form = ref(emptyForm())

const canDragSort = computed(() => cases.value.length >= 2)

const selectedIds = computed(() => cases.value.filter((c) => selectedMap[c.id]).map((c) => c.id))
const selectedCount = computed(() => selectedIds.value.length)

const isAllSelected = computed({
  get: () => cases.value.length > 0 && cases.value.every((c) => selectedMap[c.id]),
  set: (val: boolean) => {
    cases.value.forEach((c) => { selectedMap[c.id] = val })
  },
})

function resetSelection(items: { id: number }[]) {
  Object.keys(selectedMap).forEach((k) => delete selectedMap[Number(k)])
  items.forEach((item) => { selectedMap[item.id] = false })
}

function buildParams() {
  const params: Record<string, unknown> = { page_size: 500 }
  const f = filters.value
  if (f.project) params.project = f.project
  if (f.field_search.trim()) params.field_search = f.field_search.trim()
  if (f.priority) params.priority = f.priority
  if (f.passed_status) params.passed_status = f.passed_status
  if (f.module.trim()) params.module = f.module.trim()
  if (f.case_no.trim()) params.case_no = f.case_no.trim()
  if (f.executor.trim()) params.executor = f.executor.trim()
  if (f.created_after) params.created_after = f.created_after
  if (f.created_before) params.created_before = f.created_before
  return params
}

function displayTitle(item: TestCaseItem) {
  return item.title || item.case_no || '未命名用例'
}

function cellText(val: unknown) {
  const text = val == null ? '' : String(val).trim()
  return text || '-'
}

const priorityTag = (p: string) => {
  const map: Record<string, string> = { P0: 'danger', P1: 'warning', P2: 'primary', P3: 'info' }
  return map[p] || 'info'
}

function statusButtonLabel(passed: boolean | null) {
  if (passed === true) return '已执行'
  if (passed === false) return '失败'
  return '未执行'
}

function statusButtonType(passed: boolean | null): 'info' | 'success' | 'danger' {
  if (passed === true) return 'success'
  if (passed === false) return 'danger'
  return 'info'
}

function nextPassedStatus(passed: boolean | null): boolean | null {
  if (passed === null) return true
  if (passed === true) return false
  return null
}

async function toggleExecuteStatus(item: TestCaseItem) {
  const prev = item.passed
  const next = nextPassedStatus(item.passed)
  item.passed = next
  try {
    await updateTestCase(item.id, { passed: next })
  } catch {
    item.passed = prev
  }
}

async function loadData() {
  loading.value = true
  try {
    const params = buildParams()
    const [caseRes, projRes] = await Promise.all([
      getTestCases(params),
      getProjects(),
    ])
    cases.value = (caseRes.data.results ?? caseRes.data).sort(
      (a: TestCaseItem, b: TestCaseItem) => a.sort_order - b.sort_order
    )
    projects.value = projRes.data.results ?? projRes.data
    resetSelection(cases.value)
  } finally {
    loading.value = false
  }
}

async function onDragEnd() {
  if (!canDragSort.value) return
  cases.value = cases.value.map((item, index) => ({ ...item, sort_order: index }))
  try {
    await reorderTestCases(cases.value.map((c) => c.id))
    ElMessage.success('排序已保存')
  } catch {
    loadData()
  }
}

function resetFilters() {
  filters.value = {
    project: null,
    field_search: '',
    priority: '',
    passed_status: '',
    module: '',
    case_no: '',
    executor: '',
    created_after: '',
    created_before: '',
  }
  loadData()
}

function openCreate() {
  editingId.value = null
  form.value = {
    ...emptyForm(),
    project: filters.value.project ?? projects.value[0]?.id ?? null,
  }
  dialogVisible.value = true
}

function openEdit(item: TestCaseItem) {
  editingId.value = item.id
  form.value = {
    project: item.project,
    case_no: item.case_no || '',
    title: item.title || '',
    module: item.module || '',
    priority: item.priority || 'P2',
    precondition: item.precondition || '',
    steps: item.steps || '',
    expected: item.expected || '',
    postcondition: item.postcondition || '',
    executor: item.executor || '',
    passed: item.passed,
    actual: item.actual || '',
  }
  dialogVisible.value = true
}

async function saveCase() {
  if (!form.value.project) {
    ElMessage.warning('请选择项目')
    return
  }
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写用例标题')
    return
  }
  const payload = { ...form.value }
  try {
    if (editingId.value) {
      await updateTestCase(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createTestCase({ ...payload, sort_order: cases.value.length })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch { /* interceptor */ }
}

async function handleDelete(item: TestCaseItem) {
  await ElMessageBox.confirm(`确定删除用例「${displayTitle(item)}」？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await deleteTestCase(item.id)
  ElMessage.success('删除成功')
  loadData()
}

async function handleBatchDelete() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先选择要删除的用例')
    return
  }
  await ElMessageBox.confirm(
    `确定批量删除选中的 ${selectedIds.value.length} 条用例？此操作不可恢复。`,
    '批量删除确认',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  await batchDeleteTestCases(selectedIds.value)
  ElMessage.success(`已删除 ${selectedIds.value.length} 条用例`)
  loadData()
}

async function handleBatchStatus(passed: boolean | null, actionLabel: string) {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先选择用例')
    return
  }
  const ids = [...selectedIds.value]
  const prevMap = new Map(cases.value.map((c) => [c.id, c.passed]))
  cases.value.forEach((c) => {
    if (selectedMap[c.id]) c.passed = passed
  })
  batchStatusLoading.value = true
  try {
    const res = await batchUpdateTestCaseStatus({ ids, passed })
    ElMessage.success(`已批量标记为「${actionLabel}」${res.data.updated} 条`)
  } catch {
    cases.value.forEach((c) => {
      if (ids.includes(c.id)) c.passed = prevMap.get(c.id) ?? null
    })
  } finally {
    batchStatusLoading.value = false
  }
}

function parseFilenameFromDisposition(header?: string) {
  if (!header) return ''
  const utf8 = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8?.[1]) return decodeURIComponent(utf8[1])
  const plain = header.match(/filename="?([^";]+)"?/i)
  return plain?.[1] || ''
}

async function handleExportExcel() {
  if (!cases.value.length) {
    ElMessage.warning('当前没有可导出的用例')
    return
  }
  exporting.value = true
  try {
    const params: Record<string, unknown> = { ...buildParams() }
    delete params.page_size
    if (selectedCount.value) {
      params.ids = selectedIds.value.join(',')
    }
    const res = await exportTestCasesExcel(params)
    const blob = new Blob(
      [res.data],
      { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
    )
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const fallbackName = `测试用例_${new Date().toISOString().slice(0, 10)}.xlsx`
    link.download = parseFilenameFromDisposition(res.headers['content-disposition']) || fallbackName
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success(selectedCount.value ? `已导出选中的 ${selectedCount.value} 条用例` : `已导出 ${cases.value.length} 条用例`)
  } finally {
    exporting.value = false
  }
}

const aiProjectId = computed(() => filters.value.project ?? projects.value[0]?.id ?? null)

function openAiGenerate() {
  if (!projects.value.length) {
    ElMessage.warning('请先创建项目')
    return
  }
  aiDialogVisible.value = true
}

function onAiTaskStarted(taskId: number) {
  aiGenTask.trackTask(taskId)
}

watch(() => filters.value.project, async (projectId) => {
  if (!aiGenTask.isRunning.value) {
    await aiGenTask.resumeIfActive(projectId)
  }
})

onMounted(() => {
  const qProject = route.query.project ? Number(route.query.project) : null
  if (qProject) filters.value.project = qProject
  loadData().then(async () => {
    await aiGenTask.resumeIfActive(filters.value.project)
    if (route.query.aiGenerate === '1') aiDialogVisible.value = true
  })
})
</script>

<template>
  <div>
    <h1 class="page-title">测试用例</h1>

    <div class="filter-card">
      <div class="filter-header">
        <span class="filter-title"><el-icon><Filter /></el-icon> 筛选条件</span>
        <el-button link type="primary" @click="showFilter = !showFilter">
          {{ showFilter ? '收起' : '展开' }}
        </el-button>
      </div>
      <el-collapse-transition>
        <div v-show="showFilter" class="filter-body">
          <el-row :gutter="16">
            <el-col :span="6">
              <div class="filter-item">
                <label>所属项目</label>
                <el-select v-model="filters.project" placeholder="全部项目" clearable style="width:100%">
                  <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
                </el-select>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="filter-item">
                <label>关键词</label>
                <el-input v-model="filters.field_search" placeholder="标题/标号/模块/步骤" clearable />
              </div>
            </el-col>
            <el-col :span="6">
              <div class="filter-item">
                <label>优先级</label>
                <el-select v-model="filters.priority" placeholder="全部" clearable style="width:100%">
                  <el-option label="P0 - 紧急" value="P0" />
                  <el-option label="P1 - 高" value="P1" />
                  <el-option label="P2 - 中" value="P2" />
                  <el-option label="P3 - 低" value="P3" />
                </el-select>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="filter-item">
                <label>执行状态</label>
                <el-select v-model="filters.passed_status" placeholder="全部状态" clearable style="width:100%">
                  <el-option label="已通过" value="passed" />
                  <el-option label="已失败" value="failed" />
                  <el-option label="未执行" value="pending" />
                </el-select>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="filter-item">
                <label>模块</label>
                <el-input v-model="filters.module" placeholder="模块名称" clearable />
              </div>
            </el-col>
            <el-col :span="6">
              <div class="filter-item">
                <label>标号</label>
                <el-input v-model="filters.case_no" placeholder="用例标号" clearable />
              </div>
            </el-col>
            <el-col :span="6">
              <div class="filter-item">
                <label>执行人</label>
                <el-input v-model="filters.executor" placeholder="执行人" clearable />
              </div>
            </el-col>
            <el-col :span="6">
              <div class="filter-item">
                <label>创建时间（起）</label>
                <el-date-picker v-model="filters.created_after" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" style="width:100%" />
              </div>
            </el-col>
            <el-col :span="6">
              <div class="filter-item">
                <label>创建时间（止）</label>
                <el-date-picker v-model="filters.created_before" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" style="width:100%" />
              </div>
            </el-col>
            <el-col :span="6" class="filter-actions">
              <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> 查询</el-button>
              <el-button @click="resetFilters"><el-icon><RefreshLeft /></el-icon> 重置</el-button>
            </el-col>
          </el-row>
        </div>
      </el-collapse-transition>
    </div>

    <div v-if="aiGenTask.isRunning.value" class="gen-progress-card">
      <div class="gen-progress-head">
        <span><el-icon><MagicStick /></el-icon> AI 正在生成测试用例</span>
        <span class="gen-progress-meta">{{ aiGenTask.progressText.value }}</span>
      </div>
      <el-progress
        :percentage="aiGenTask.progress.value"
        :stroke-width="10"
        striped
        striped-flow
        :duration="10"
      />
    </div>

    <div class="page-card" style="margin-top:16px">
      <div class="toolbar">
        <div class="toolbar-left">
          <span v-if="selectedCount" class="selected-tip">已选 {{ selectedCount }} 项</span>
          <template v-if="selectedCount">
            <el-button
              type="success"
              plain
              round
              :loading="batchStatusLoading"
              @click="handleBatchStatus(true, '已执行')"
            >
              批量已执行
            </el-button>
            <el-button
              type="danger"
              plain
              round
              :loading="batchStatusLoading"
              @click="handleBatchStatus(false, '失败')"
            >
              批量失败
            </el-button>
            <el-button
              plain
              round
              :loading="batchStatusLoading"
              @click="handleBatchStatus(null, '未执行')"
            >
              批量重置
            </el-button>
            <el-button type="danger" plain round @click="handleBatchDelete">
              <el-icon><Delete /></el-icon> 批量删除
            </el-button>
          </template>
        </div>
        <div class="toolbar-right">
          <el-button round :loading="exporting" @click="handleExportExcel">
            <el-icon><Download /></el-icon>
            {{ selectedCount ? `导出选中 (${selectedCount})` : '导出 Excel' }}
          </el-button>
          <el-button type="primary" round @click="openCreate">
            <el-icon><Plus /></el-icon> 新增用例
          </el-button>
          <el-button type="success" round plain @click="openAiGenerate">
            <el-icon><MagicStick /></el-icon> AI 生成
          </el-button>
        </div>
      </div>

      <p class="drag-hint">
        <template v-if="canDragSort">
          <el-icon><Rank /></el-icon> 拖拽左侧手柄可调整顺序 ·
        </template>
        测完后点击「未执行」→「已执行」；再点可标记失败或重置。勾选多条后可批量标记状态
      </p>

      <div v-loading="loading" class="drag-table-wrap">
        <div class="drag-table-scroll">
          <div class="drag-table-head row-grid">
            <div class="cell cell-drag" />
            <div class="cell cell-check">
              <CardCheckbox
                v-model="isAllSelected"
                :indeterminate="selectedCount > 0 && selectedCount < cases.length"
                size="sm"
              />
            </div>
            <div class="cell cell-no">序号</div>
            <div class="cell">标号</div>
            <div class="cell cell-title">用例标题</div>
            <div class="cell">模块</div>
            <div class="cell cell-center">优先级</div>
            <div class="cell cell-center">执行状态</div>
            <div class="cell cell-wide">测试步骤</div>
            <div class="cell cell-wide">预期结果</div>
            <div class="cell">测试点</div>
            <div class="cell">创建时间</div>
            <div class="cell cell-center">操作</div>
          </div>

          <draggable
            v-if="cases.length"
            v-model="cases"
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
                  <span class="drag-handle" title="拖拽排序">
                    <el-icon><Rank /></el-icon>
                  </span>
                </div>
                <div class="cell cell-check" @click.stop>
                  <CardCheckbox v-model="selectedMap[element.id]" size="sm" />
                </div>
                <div class="cell cell-no">{{ index + 1 }}</div>
                <div class="cell" :title="element.case_no">{{ cellText(element.case_no) }}</div>
                <div class="cell cell-title" :title="displayTitle(element)">{{ displayTitle(element) }}</div>
                <div class="cell" :title="element.module">{{ cellText(element.module) }}</div>
                <div class="cell cell-center">
                  <el-tag v-if="element.priority" :type="priorityTag(element.priority)" size="small" effect="dark">
                    {{ element.priority }}
                  </el-tag>
                  <span v-else>-</span>
                </div>
                <div class="cell cell-center" @click.stop>
                  <el-button
                    size="small"
                    round
                    :type="statusButtonType(element.passed)"
                    :plain="element.passed === null"
                    class="status-btn"
                    @click="toggleExecuteStatus(element)"
                  >
                    {{ statusButtonLabel(element.passed) }}
                  </el-button>
                </div>
                <div class="cell cell-wide" :title="element.steps">{{ cellText(element.steps) }}</div>
                <div class="cell cell-wide" :title="element.expected">{{ cellText(element.expected) }}</div>
                <div class="cell" :title="element.test_point_name">{{ cellText(element.test_point_name) }}</div>
                <div class="cell">{{ element.created_at?.slice(0, 10) || '-' }}</div>
                <div class="cell cell-center cell-actions">
                  <el-button link type="primary" @click="openEdit(element)">编辑</el-button>
                  <el-button link type="danger" @click="handleDelete(element)">删除</el-button>
                </div>
              </div>
            </template>
          </draggable>

          <el-empty v-else-if="!loading" description="暂无测试用例，点击新增或 AI 生成" />
        </div>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑用例' : '新增用例'" width="640px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="所属项目" required>
          <el-select v-model="form.project" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="用例标题" required>
          <el-input v-model="form.title" placeholder="请输入用例标题" />
        </el-form-item>
        <el-form-item label="标号">
          <el-input v-model="form.case_no" placeholder="如 TC-001" />
        </el-form-item>
        <el-form-item label="模块">
          <el-input v-model="form.module" placeholder="所属模块" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width: 100%">
            <el-option label="P0 - 紧急" value="P0" />
            <el-option label="P1 - 高" value="P1" />
            <el-option label="P2 - 中" value="P2" />
            <el-option label="P3 - 低" value="P3" />
          </el-select>
        </el-form-item>
        <el-form-item label="前置条件">
          <el-input v-model="form.precondition" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="测试步骤">
          <el-input v-model="form.steps" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="预期结果">
          <el-input v-model="form.expected" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="后置条件">
          <el-input v-model="form.postcondition" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="执行人">
          <el-input v-model="form.executor" />
        </el-form-item>
        <el-form-item v-if="editingId" label="执行状态">
          <el-select v-model="form.passed" clearable placeholder="未执行" style="width: 100%">
            <el-option label="通过" :value="true" />
            <el-option label="失败" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editingId" label="实际结果">
          <el-input v-model="form.actual" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCase">保存</el-button>
      </template>
    </el-dialog>

    <AiGenerateCasesDialog
      v-model="aiDialogVisible"
      :project-id="aiProjectId"
      @task-started="onAiTaskStarted"
    />
  </div>
</template>

<style scoped>
.gen-progress-card {
  margin-top: 16px;
  padding: 14px 18px;
  background: #1a2744;
  border: 1px solid #3b82f644;
  border-radius: 12px;
}
.gen-progress-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 13px;
  color: #93c5fd;
  flex-wrap: wrap;
}
.gen-progress-meta {
  font-size: 12px;
  color: #9aa0a6;
}
.filter-card {
  background: #1a2332;
  border: 1px solid #2a3544;
  border-radius: 12px;
  padding: 16px 20px;
}
.filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: #e8eaed;
}
.filter-body { margin-top: 16px; }
.filter-item { margin-bottom: 12px; }
.filter-item label {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}
.filter-actions {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding-bottom: 12px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 12px;
}
.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.selected-tip {
  font-size: 13px;
  color: #3b82f6;
  padding: 4px 10px;
  background: #3b82f614;
  border-radius: 20px;
}
.drag-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0 0 10px;
  font-size: 13px;
  color: #6b7280;
}
.drag-table-wrap {
  min-height: 200px;
  border: 1px solid #2a3544;
  border-radius: 8px;
  overflow: hidden;
}
.drag-table-scroll {
  overflow-x: auto;
}
.row-grid {
  display: grid;
  grid-template-columns:
    44px 48px 64px 110px minmax(160px, 1.2fr) 120px 88px 96px
    minmax(160px, 1fr) minmax(160px, 1fr) 140px 112px 120px;
  align-items: center;
  min-width: 1320px;
}
.drag-table-head {
  background: #141c28;
  border-bottom: 1px solid #2a3544;
}
.drag-table-head .cell {
  padding: 12px 10px;
  font-size: 13px;
  font-weight: 600;
  color: #9aa0a6;
  white-space: nowrap;
}
.drag-table-row {
  border-bottom: 1px solid #2a3544;
  background: #0f1419;
  transition: background 0.15s;
}
.drag-table-row.stripe {
  background: #141c28;
}
.drag-table-row:hover {
  background: #1a2332;
}
.drag-table-row .cell {
  padding: 10px;
  font-size: 13px;
  color: #e8eaed;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cell-center {
  text-align: center;
  justify-self: center;
}
.cell-check {
  display: flex;
  align-items: center;
  justify-content: center;
}
.cell-no {
  text-align: center;
  color: #6b7280;
}
.cell-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  white-space: nowrap;
}
.status-btn {
  min-width: 72px;
  font-size: 12px;
}
.drag-handle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  cursor: grab;
  color: #6b7280;
  border-radius: 6px;
  user-select: none;
}
.drag-handle:hover {
  color: #93c5fd;
  background: #3b82f614;
}
.drag-handle:active {
  cursor: grabbing;
}
:deep(.row-drag-ghost) {
  opacity: 0.55;
  background: #1a2744 !important;
}
</style>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getProjects, getRequirements, aiGenerateTestPoints, recallKnowledge,
} from '@/api'

interface Requirement {
  id: number
  name: string
  module: string
  requirement_type: string
  description: string
}

interface GeneratedGroup {
  requirementId: number
  requirementName: string
  module: string
  strategy: string
  strategyLabel: string
  points: object[]
}

const route = useRoute()
const router = useRouter()
const projects = ref<{ id: number; name: string }[]>([])
const requirements = ref<Requirement[]>([])
const projectId = ref<number | null>(null)
const selectedReqIds = ref<number[]>([])
const selectedStrategies = ref<string[]>(['default'])
const useRag = ref(true)
const loading = ref(false)
const progressText = ref('')
const ragPreview = ref<{ title: string; category: string }[]>([])
const resultGroups = ref<GeneratedGroup[]>([])
const reqDialogVisible = ref(false)
const draftReqIds = ref<number[]>([])
const reqFilter = ref('')
const reqTypeFilter = ref('')

const reqTypeOptions = [
  { value: 'feature', label: '功能需求' },
  { value: 'constraint', label: '约束' },
  { value: 'exception', label: '异常场景' },
]

const typeLabel: Record<string, string> = {
  feature: '功能需求',
  constraint: '约束',
  exception: '异常场景',
}

const strategies = [
  { value: 'default', label: '综合策略', desc: '综合多种方法，适合首次设计或快速覆盖' },
  { value: 'equivalence', label: '等价类', desc: '按有效/无效输入域划分，减少冗余' },
  { value: 'boundary', label: '边界值', desc: '关注边界及边界两侧，发现 off-by-one 问题' },
  { value: 'scenario', label: '场景法', desc: '按用户主流程、分支、异常路径设计' },
  { value: 'state', label: '状态迁移', desc: '覆盖合法/非法状态转换，验证状态机' },
]

const strategyLabelMap = Object.fromEntries(strategies.map((s) => [s.value, s.label]))

const totalPoints = computed(() => resultGroups.value.reduce((n, g) => n + g.points.length, 0))

const allStrategySelected = computed(
  () => strategies.length > 0 && selectedStrategies.value.length === strategies.length,
)

const selectedReqs = computed(() =>
  requirements.value.filter((r) => selectedReqIds.value.includes(r.id)),
)

const reqGroups = computed(() => {
  const map = new Map<string, Requirement[]>()
  for (const r of requirements.value) {
    const mod = r.module?.trim() || '未分类'
    if (!map.has(mod)) map.set(mod, [])
    map.get(mod)!.push(r)
  }
  return Array.from(map.entries()).map(([module, items]) => ({
    module,
    items,
    selectedCount: items.filter((i) => draftReqIds.value.includes(i.id)).length,
  }))
})

const dialogReqGroups = computed(() => {
  const kw = reqFilter.value.trim().toLowerCase()
  const type = reqTypeFilter.value
  return reqGroups.value
    .map((g) => ({
      ...g,
      items: g.items.filter((r) => {
        if (type && r.requirement_type !== type) return false
        if (!kw) return true
        return r.name.toLowerCase().includes(kw)
          || r.module.toLowerCase().includes(kw)
          || (typeLabel[r.requirement_type] || '').includes(kw)
      }),
    }))
    .filter((g) => g.items.length > 0)
})

const allDraftReqSelected = computed(() => {
  const visible = dialogReqGroups.value.flatMap((g) => g.items)
  return visible.length > 0 && visible.every((r) => draftReqIds.value.includes(r.id))
})

function isModuleAllSelected(group: { items: Requirement[] }) {
  return group.items.length > 0 && group.items.every((r) => draftReqIds.value.includes(r.id))
}

function isModuleIndeterminate(group: { items: Requirement[] }) {
  const n = group.items.filter((r) => draftReqIds.value.includes(r.id)).length
  return n > 0 && n < group.items.length
}

function toggleModule(group: { items: Requirement[] }, checked: boolean) {
  const ids = group.items.map((r) => r.id)
  if (checked) {
    draftReqIds.value = [...new Set([...draftReqIds.value, ...ids])]
  } else {
    draftReqIds.value = draftReqIds.value.filter((id) => !ids.includes(id))
  }
}

function toggleAllDraftReqs() {
  const visible = dialogReqGroups.value.flatMap((g) => g.items)
  if (allDraftReqSelected.value) {
    const visibleIds = new Set(visible.map((r) => r.id))
    draftReqIds.value = draftReqIds.value.filter((id) => !visibleIds.has(id))
  } else {
    draftReqIds.value = [...new Set([...draftReqIds.value, ...visible.map((r) => r.id)])]
  }
}

function openReqDialog() {
  draftReqIds.value = [...selectedReqIds.value]
  reqFilter.value = ''
  reqTypeFilter.value = ''
  reqDialogVisible.value = true
}

function confirmReqDialog() {
  selectedReqIds.value = [...draftReqIds.value]
  reqDialogVisible.value = false
  loadRagPreview()
}

function cancelReqDialog() {
  reqDialogVisible.value = false
}

function typeColor(type: string) {
  if (type === 'constraint') return '#f59e0b'
  if (type === 'exception') return '#ef4444'
  return '#3b82f6'
}

function clearSelectedReqs() {
  selectedReqIds.value = []
  loadRagPreview()
}

function removeReq(id: number) {
  selectedReqIds.value = selectedReqIds.value.filter((i) => i !== id)
  loadRagPreview()
}

function toggleAllStrategies() {
  selectedStrategies.value = allStrategySelected.value ? [] : strategies.map((s) => s.value)
}

async function loadProjects() {
  const res = await getProjects()
  projects.value = res.data.results ?? res.data
  const qProject = route.query.project ? Number(route.query.project) : null
  projectId.value = qProject && projects.value.some((p) => p.id === qProject)
    ? qProject
    : projects.value[0]?.id ?? null
}

async function loadRequirements() {
  if (!projectId.value) return
  const res = await getRequirements({ project: projectId.value, page_size: 500 })
  requirements.value = res.data.results ?? res.data

  const qReq = route.query.requirementId ? Number(route.query.requirementId) : null
  if (qReq && requirements.value.some((r) => r.id === qReq)) {
    selectedReqIds.value = [qReq]
  } else {
    selectedReqIds.value = []
  }

  const qStrategy = route.query.strategy
  if (typeof qStrategy === 'string' && strategies.some((s) => s.value === qStrategy)) {
    selectedStrategies.value = [qStrategy]
  }
}

async function loadRagPreview() {
  if (!useRag.value || !selectedReqs.value.length) {
    ragPreview.value = []
    return
  }
  const keyword = selectedReqs.value.map((r) => r.name).join(' ')
  const res = await recallKnowledge({ keyword, project: projectId.value })
  ragPreview.value = (res.data || []).map((i: { title: string; category: string }) => ({
    title: i.title, category: i.category,
  }))
}

async function handleGenerate() {
  if (!selectedReqIds.value.length) {
    ElMessage.warning('请至少选择一条需求条目')
    return
  }
  if (!selectedStrategies.value.length) {
    ElMessage.warning('请至少选择一种设计策略')
    return
  }

  loading.value = true
  resultGroups.value = []
  const groups: GeneratedGroup[] = []
  const tasks: { req: Requirement; strategy: string }[] = []
  for (const req of selectedReqs.value) {
    for (const strategy of selectedStrategies.value) {
      tasks.push({ req, strategy })
    }
  }

  try {
    for (let i = 0; i < tasks.length; i++) {
      const { req, strategy } = tasks[i]
      progressText.value = `正在生成 ${i + 1}/${tasks.length}：${req.module} - ${req.name}（${strategyLabelMap[strategy]}）`
      const res = await aiGenerateTestPoints(req.id, {
        strategy,
        use_rag: useRag.value,
      })
      const points = res.data.test_points || []
      if (points.length) {
        groups.push({
          requirementId: req.id,
          requirementName: req.name,
          module: req.module,
          strategy,
          strategyLabel: strategyLabelMap[strategy] || strategy,
          points,
        })
      }
    }
    resultGroups.value = groups
    ElMessage.success(`完成：${selectedReqs.value.length} 条需求 × ${selectedStrategies.value.length} 种策略，共 ${totalPoints.value} 个测试点`)
  } finally {
    loading.value = false
    progressText.value = ''
  }
}

function goEditor() {
  router.push('/test-design/editor')
}

function goRequirementList() {
  router.push('/requirement-center/structure')
}

function goRag() {
  router.push('/test-design/rag')
}

watch(projectId, async () => {
  await loadRequirements()
  await loadRagPreview()
})

watch([selectedReqIds, useRag], loadRagPreview, { deep: true })

onMounted(async () => {
  await loadProjects()
  await loadRequirements()
  await loadRagPreview()
})
</script>

<template>
  <div class="generator-page">
    <div class="pipeline-tip page-card">
      <div class="tip-title">需求 vs 测试点</div>
      <p>
        <strong>需求清单</strong>回答「要测什么」；
        <strong>测试点</strong>回答「怎么测」。
        可一次勾选多条需求和多种策略，批量生成测试点。
      </p>
      <el-button link type="primary" @click="goRequirementList">← 返回需求清单</el-button>
    </div>

    <div class="main-grid">
      <div class="page-card config-panel">
        <h3>AI 测试设计</h3>
        <p class="sub-title">勾选需求条目与设计策略，AI 批量推导测试点</p>

        <el-form label-width="88px" style="margin-top:16px">
          <el-form-item label="项目">
            <el-select v-model="projectId" style="width:100%">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>

          <el-form-item label="需求条目">
            <div class="req-picker">
              <div class="req-picker-bar">
                <el-button type="primary" plain @click="openReqDialog">
                  <el-icon><Tickets /></el-icon>
                  选择需求条目
                </el-button>
                <span class="select-count">已选 {{ selectedReqIds.length }} / {{ requirements.length }}</span>
                <el-button v-if="selectedReqIds.length" link type="primary" size="small" @click="clearSelectedReqs">
                  清空
                </el-button>
              </div>
              <div v-if="selectedReqs.length" class="req-summary">
                <el-tag
                  v-for="r in selectedReqs.slice(0, 6)"
                  :key="r.id"
                  size="small"
                  closable
                  @close="removeReq(r.id)"
                >
                  {{ r.module }} · {{ r.name }}
                </el-tag>
                <el-tag v-if="selectedReqs.length > 6" size="small" type="info">
                  +{{ selectedReqs.length - 6 }} 条
                </el-tag>
              </div>
              <p v-else class="field-hint">点击「选择需求条目」在弹框中勾选，支持单选、多选、全选</p>
            </div>
          </el-form-item>

          <el-form-item label="设计策略">
            <div class="select-block">
              <div class="select-toolbar">
                <span class="select-count">已选 {{ selectedStrategies.length }} / {{ strategies.length }}</span>
                <el-button link type="primary" size="small" @click="toggleAllStrategies">
                  {{ allStrategySelected ? '清空' : '全选' }}
                </el-button>
              </div>
              <el-checkbox-group v-model="selectedStrategies" class="strategy-row">
                <el-checkbox v-for="s in strategies" :key="s.value" :value="s.value" class="strategy-check">
                  {{ s.label }}
                </el-checkbox>
              </el-checkbox-group>
              <p class="field-hint">多选时，每条需求会分别按每种策略各生成一组测试点</p>
            </div>
          </el-form-item>

          <el-form-item label="RAG 增强">
            <div class="rag-block">
              <el-switch v-model="useRag" active-text="启用" inactive-text="关闭" />
              <div class="rag-explain">
                <p>
                  <strong>RAG（检索增强生成）</strong>：生成前从
                  <el-button link type="primary" size="small" @click="goRag">RAG 知识库</el-button>
                  检索与当前需求相关的片段（历史用例、Bug 经验、接口规范等），注入 AI 上下文，
                  使测试点更贴合项目实际，减少泛泛而谈的输出。
                </p>
                <p class="field-hint">关闭后仅依据需求描述生成，速度更快，但缺少项目背景参考。</p>
              </div>
              <div v-if="useRag && selectedReqIds.length && ragPreview.length" class="rag-preview">
                <p>本次将召回 {{ ragPreview.length }} 条参考知识</p>
                <el-tag v-for="(r, i) in ragPreview" :key="i" size="small" style="margin:2px">{{ r.title }}</el-tag>
              </div>
              <div v-else-if="useRag && selectedReqIds.length && !ragPreview.length" class="rag-preview empty">
                未匹配到知识库条目，将仅使用需求描述生成。
                <el-button link type="primary" size="small" @click="goRag">去维护知识库</el-button>
              </div>
            </div>
          </el-form-item>

          <el-button
            type="primary"
            :loading="loading"
            :disabled="!selectedReqIds.length || !selectedStrategies.length"
            style="width:100%; margin-top:4px"
            @click="handleGenerate"
          >
            <el-icon><MagicStick /></el-icon>
            生成测试点
            <template v-if="selectedReqIds.length && selectedStrategies.length">
              （{{ selectedReqIds.length }} 需求 × {{ selectedStrategies.length }} 策略）
            </template>
          </el-button>
          <p v-if="progressText" class="progress-text">{{ progressText }}</p>
        </el-form>
      </div>

      <div class="page-card result-panel">
        <div class="result-head">
          <h3>测试点结果 ({{ totalPoints }})</h3>
          <el-button v-if="totalPoints" @click="goEditor">去编辑测试点</el-button>
        </div>

        <div v-if="resultGroups.length" class="result-groups">
          <div v-for="(g, gi) in resultGroups" :key="`${g.requirementId}-${g.strategy}-${gi}`" class="result-group">
            <div class="group-head">
              <span class="group-req">{{ g.module }} - {{ g.requirementName }}</span>
              <el-tag size="small" type="info">{{ g.strategyLabel }}</el-tag>
              <span class="group-count">{{ g.points.length }} 个</span>
            </div>
            <div v-for="p in g.points" :key="(p as {id:number}).id" class="point-item">
              <strong>{{ (p as {name:string}).name }}</strong>
              <el-tag size="small">{{ (p as {point_type:string}).point_type }}</el-tag>
              <p>{{ (p as {description:string}).description }}</p>
            </div>
          </div>
        </div>
        <el-empty v-else description="勾选需求与策略后，点击「生成测试点」" />
      </div>
    </div>

    <el-dialog
      v-model="reqDialogVisible"
      title="选择需求条目"
      width="640px"
      destroy-on-close
      class="req-dialog"
    >
      <div class="dialog-filters">
        <el-input v-model="reqFilter" placeholder="搜索模块或需求名称" clearable />
        <el-select v-model="reqTypeFilter" placeholder="全部类型" clearable style="width: 128px">
          <el-option v-for="t in reqTypeOptions" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </div>
      <div class="dialog-toolbar">
        <span class="select-count">已选 {{ draftReqIds.length }} / {{ requirements.length }}</span>
        <el-button link type="primary" @click="toggleAllDraftReqs">
          {{ allDraftReqSelected ? '取消全选' : '全选' }}
        </el-button>
      </div>

      <div v-if="dialogReqGroups.length" class="dialog-body">
        <div v-for="group in dialogReqGroups" :key="group.module" class="dialog-module">
          <div class="module-head">
            <el-checkbox
              :model-value="isModuleAllSelected(group)"
              :indeterminate="isModuleIndeterminate(group)"
              @change="(v: boolean) => toggleModule(group, v)"
            />
            <span class="module-name">{{ group.module }}</span>
            <span class="module-count">{{ group.selectedCount }}/{{ group.items.length }}</span>
          </div>
          <el-checkbox-group v-model="draftReqIds" class="req-list">
            <el-checkbox v-for="r in group.items" :key="r.id" :value="r.id" class="req-item">
              <span class="req-label">
                <i class="type-dot" :style="{ background: typeColor(r.requirement_type) }" />
                <span class="req-name">{{ r.name }}</span>
                <el-tag size="small" type="info" class="req-type">{{ typeLabel[r.requirement_type] || r.requirement_type }}</el-tag>
              </span>
            </el-checkbox>
          </el-checkbox-group>
        </div>
      </div>
      <el-empty v-else description="暂无匹配的需求，请先在需求清单中添加" :image-size="64" />

      <template #footer>
        <el-button @click="cancelReqDialog">取消</el-button>
        <el-button type="primary" @click="confirmReqDialog">
          确定（{{ draftReqIds.length }} 条）
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.generator-page { display: flex; flex-direction: column; gap: 16px; }
.pipeline-tip { padding: 14px 18px; border-left: 3px solid #3b82f6; }
.tip-title { font-size: 13px; font-weight: 600; color: #93c5fd; margin-bottom: 6px; }
.pipeline-tip p { margin: 0 0 8px; font-size: 13px; color: #9aa0a6; line-height: 1.7; }
.pipeline-tip strong { color: #e8eaed; }
.main-grid { display: grid; grid-template-columns: 420px 1fr; gap: 16px; align-items: start; }
h3 { color: #fff; margin: 0; }
.sub-title { margin: 6px 0 0; font-size: 12px; color: #6b7280; }
.select-block { width: 100%; }
.select-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px;
}
.select-count { font-size: 12px; color: #6b7280; }
.req-picker { width: 100%; }
.req-picker-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.req-summary {
  display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px;
}
.dialog-filters {
  display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
}
.dialog-filters .el-input { flex: 1; }
.dialog-toolbar {
  display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-bottom: 16px;
}
.dialog-body {
  max-height: 420px; overflow-y: auto;
  display: flex; flex-direction: column; gap: 12px;
}
.dialog-module {
  padding: 10px 12px; background: #0f1419; border-radius: 8px;
}
.module-head {
  display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
}
.module-name { font-size: 13px; font-weight: 500; color: #e8eaed; flex: 1; }
.module-count { font-size: 12px; color: #6b7280; }
.req-list { display: flex; flex-direction: column; gap: 6px; padding-left: 24px; }
.req-item { display: flex; align-items: center; margin-right: 0 !important; height: auto; }
.req-label { display: flex; align-items: center; gap: 8px; line-height: 1.4; }
.type-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.req-name { font-size: 13px; color: #cbd5e1; }
.req-type { flex-shrink: 0; }
.strategy-row {
  display: flex; flex-wrap: wrap; gap: 8px 16px;
}
.strategy-check { margin-right: 0 !important; }
.field-hint { margin: 6px 0 0; font-size: 11px; color: #6b7280; line-height: 1.5; }
.rag-block { width: 100%; }
.rag-explain {
  margin-top: 10px; padding: 10px 12px; background: #0f1419;
  border-radius: 8px; font-size: 12px; color: #9aa0a6; line-height: 1.7;
}
.rag-explain strong { color: #cbd5e1; }
.rag-preview { padding: 10px; background: #141c28; border-radius: 8px; margin-top: 10px; font-size: 12px; }
.rag-preview p { color: #6b7280; margin-bottom: 8px; }
.rag-preview.empty { color: #6b7280; }
.progress-text { margin: 8px 0 0; font-size: 12px; color: #93c5fd; text-align: center; }
.result-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.result-groups { display: flex; flex-direction: column; gap: 16px; }
.result-group { border: 1px solid #2a3544; border-radius: 8px; overflow: hidden; }
.group-head {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  background: #141c28; font-size: 13px;
}
.group-req { color: #e8eaed; font-weight: 500; flex: 1; }
.group-count { font-size: 12px; color: #6b7280; }
.point-item { padding: 10px 14px; border-top: 1px solid #2a3544; }
.point-item strong { color: #f3f4f6; margin-right: 8px; }
.point-item p { color: #9aa0a6; font-size: 13px; margin: 6px 0 0; }
:deep(.el-form-item) { margin-bottom: 18px; }
:deep(.el-form-item__label) { color: #9aa0a6; font-size: 13px; }
</style>

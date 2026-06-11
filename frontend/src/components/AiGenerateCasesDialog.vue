<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getTestPoints, batchAiGenerateCases } from '@/api'

interface TestPointItem {
  id: number
  name: string
  module: string
  point_type: string
  description: string
}

const props = defineProps<{
  modelValue: boolean
  projectId: number | null
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  'task-started': [taskId: number]
}>()

const loading = ref(false)
const progressText = ref('')
const testPoints = ref<TestPointItem[]>([])
const selectedIds = ref<number[]>([])
const selectedStrategies = ref<string[]>(['default'])
const useRag = ref(false)
const tpFilter = ref('')
const tpTypeFilter = ref('')

const strategies = [
  { value: 'default', label: '综合策略' },
  { value: 'equivalence', label: '等价类' },
  { value: 'boundary', label: '边界值' },
  { value: 'scenario', label: '场景法' },
  { value: 'state', label: '状态迁移' },
]

const pointTypeLabel: Record<string, string> = {
  functional: '功能',
  boundary: '边界',
  exception: '异常',
  security: '安全',
}

const tpGroups = computed(() => {
  const map = new Map<string, TestPointItem[]>()
  for (const tp of testPoints.value) {
    const mod = tp.module?.trim() || '未分类'
    if (!map.has(mod)) map.set(mod, [])
    map.get(mod)!.push(tp)
  }
  return Array.from(map.entries()).map(([module, items]) => ({ module, items }))
})

const filteredGroups = computed(() => {
  const kw = tpFilter.value.trim().toLowerCase()
  const type = tpTypeFilter.value
  return tpGroups.value
    .map((g) => ({
      ...g,
      items: g.items.filter((tp) => {
        if (type && tp.point_type !== type) return false
        if (!kw) return true
        return tp.name.toLowerCase().includes(kw) || tp.module.toLowerCase().includes(kw)
      }),
    }))
    .filter((g) => g.items.length > 0)
})

const visiblePoints = computed(() => filteredGroups.value.flatMap((g) => g.items))

const allVisibleSelected = computed(
  () => visiblePoints.value.length > 0 && visiblePoints.value.every((tp) => selectedIds.value.includes(tp.id)),
)

const allStrategySelected = computed(
  () => strategies.length > 0 && selectedStrategies.value.length === strategies.length,
)

async function loadTestPoints() {
  if (!props.projectId) {
    testPoints.value = []
    return
  }
  const res = await getTestPoints({ requirement__project: props.projectId, page_size: 500 })
  testPoints.value = res.data.results ?? res.data
}

function toggleAllPoints() {
  if (allVisibleSelected.value) {
    const visible = new Set(visiblePoints.value.map((tp) => tp.id))
    selectedIds.value = selectedIds.value.filter((id) => !visible.has(id))
  } else {
    selectedIds.value = [...new Set([...selectedIds.value, ...visiblePoints.value.map((tp) => tp.id)])]
  }
}

function toggleAllStrategies() {
  selectedStrategies.value = allStrategySelected.value ? [] : strategies.map((s) => s.value)
}

function toggleModule(items: TestPointItem[], checked: boolean) {
  const ids = items.map((tp) => tp.id)
  if (checked) {
    selectedIds.value = [...new Set([...selectedIds.value, ...ids])]
  } else {
    selectedIds.value = selectedIds.value.filter((id) => !ids.includes(id))
  }
}

function isModuleAllSelected(items: TestPointItem[]) {
  return items.length > 0 && items.every((tp) => selectedIds.value.includes(tp.id))
}

function isModuleIndeterminate(items: TestPointItem[]) {
  const n = items.filter((tp) => selectedIds.value.includes(tp.id)).length
  return n > 0 && n < items.length
}

async function handleGenerate() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请至少选择一个测试点')
    return
  }
  if (!selectedStrategies.value.length) {
    ElMessage.warning('请至少选择一种设计策略')
    return
  }
  loading.value = true
  progressText.value = '正在提交生成任务...'
  try {
    const res = await batchAiGenerateCases({
      test_point_ids: selectedIds.value,
      strategies: selectedStrategies.value,
      use_rag: useRag.value,
    })
    const taskId = res.data.id
    if (!taskId) {
      ElMessage.error('任务创建失败')
      return
    }
    ElMessage.info('生成任务已启动，可在页面顶部查看进度')
    emit('task-started', taskId)
    emit('update:modelValue', false)
  } finally {
    loading.value = false
    progressText.value = ''
  }
}

function close() {
  emit('update:modelValue', false)
}

watch(() => props.modelValue, async (open) => {
  if (open) {
    tpFilter.value = ''
    tpTypeFilter.value = ''
    selectedStrategies.value = ['default']
    useRag.value = false
    await loadTestPoints()
    if (!selectedIds.value.length && testPoints.value.length) {
      selectedIds.value = testPoints.value.slice(0, 5).map((tp) => tp.id)
    }
  }
})

watch(() => props.projectId, () => {
  if (props.modelValue) loadTestPoints()
})
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="AI 生成测试用例"
    width="680px"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="intro">
      选择测试点和设计策略，AI 将快速生成核心用例（标题、步骤、预期、优先级），后台并行处理，可关闭弹框或刷新页面。
    </p>

    <div class="section">
      <div class="section-head">
        <span>测试点</span>
        <span class="count">已选 {{ selectedIds.length }} / {{ testPoints.length }}</span>
        <el-button link type="primary" size="small" @click="toggleAllPoints">
          {{ allVisibleSelected ? '取消全选' : '全选' }}
        </el-button>
      </div>
      <div class="filters">
        <el-input v-model="tpFilter" placeholder="搜索测试点" clearable />
        <el-select v-model="tpTypeFilter" placeholder="全部类型" clearable style="width:120px">
          <el-option label="功能" value="functional" />
          <el-option label="边界" value="boundary" />
          <el-option label="异常" value="exception" />
          <el-option label="安全" value="security" />
        </el-select>
      </div>
      <div v-if="filteredGroups.length" class="tp-list">
        <div v-for="group in filteredGroups" :key="group.module" class="tp-module">
          <div class="module-head">
            <el-checkbox
              :model-value="isModuleAllSelected(group.items)"
              :indeterminate="isModuleIndeterminate(group.items)"
              @change="(v: boolean) => toggleModule(group.items, v)"
            />
            <span>{{ group.module }}</span>
          </div>
          <el-checkbox-group v-model="selectedIds" class="tp-items">
            <el-checkbox v-for="tp in group.items" :key="tp.id" :value="tp.id">
              {{ tp.name }}
              <el-tag size="small" type="info">{{ pointTypeLabel[tp.point_type] || tp.point_type }}</el-tag>
            </el-checkbox>
          </el-checkbox-group>
        </div>
      </div>
      <el-empty v-else description="暂无测试点，请先在需求中心提取测试点" :image-size="48" />
    </div>

    <div class="section">
      <div class="section-head">
        <span>设计策略</span>
        <el-button link type="primary" size="small" @click="toggleAllStrategies">
          {{ allStrategySelected ? '清空' : '全选' }}
        </el-button>
      </div>
      <el-checkbox-group v-model="selectedStrategies" class="strategy-row">
        <el-checkbox v-for="s in strategies" :key="s.value" :value="s.value">{{ s.label }}</el-checkbox>
      </el-checkbox-group>
    </div>

    <div class="section rag-row">
      <span>RAG 增强</span>
      <el-switch v-model="useRag" />
      <span class="rag-hint">从知识库召回历史经验辅助生成（可选）</span>
    </div>

    <p v-if="progressText" class="progress">{{ progressText }}</p>
    <p class="async-hint">提交后将在后台并行生成，可关闭弹框或刷新页面，进度条会自动恢复。</p>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        type="primary"
        :loading="loading"
        :disabled="!selectedIds.length || !selectedStrategies.length"
        @click="handleGenerate"
      >
        生成用例
        <template v-if="selectedIds.length && selectedStrategies.length">
          （{{ selectedIds.length }} 点 × {{ selectedStrategies.length }} 策略）
        </template>
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.intro { margin: 0 0 16px; font-size: 13px; color: #9aa0a6; line-height: 1.6; }
.section { margin-bottom: 16px; }
.section-head {
  display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
  font-size: 13px; font-weight: 500; color: #e8eaed;
}
.count { font-size: 12px; color: #6b7280; margin-left: auto; }
.filters { display: flex; gap: 8px; margin-bottom: 8px; }
.filters .el-input { flex: 1; }
.tp-list { max-height: 220px; overflow-y: auto; background: #0f1419; border-radius: 8px; padding: 8px; }
.tp-module { margin-bottom: 8px; }
.module-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; font-size: 13px; color: #cbd5e1; }
.tp-items { display: flex; flex-direction: column; gap: 4px; padding-left: 24px; }
.strategy-row { display: flex; flex-wrap: wrap; gap: 8px 16px; }
.rag-row { display: flex; align-items: center; gap: 10px; font-size: 13px; color: #9aa0a6; }
.rag-hint { font-size: 12px; color: #6b7280; }
.progress { text-align: center; font-size: 12px; color: #93c5fd; margin: 0; }
.async-hint { margin: 12px 0 0; font-size: 12px; color: #6b7280; line-height: 1.5; }
</style>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getProjects, getTestCases, createTestSuite, batchRunCases } from '@/api'
import CardCheckbox from '@/components/CardCheckbox.vue'

const router = useRouter()
const projects = ref<{ id: number; name: string }[]>([])
const cases = ref<{ id: number; title: string }[]>([])
const projectId = ref<number | null>(null)
const suiteName = ref('回归测试套件')
const selectedMap = reactive<Record<number, boolean>>({})
const loading = ref(false)

async function loadData() {
  if (!projectId.value) return
  const res = await getTestCases({ project: projectId.value, page_size: 500 })
  cases.value = res.data.results ?? res.data
  cases.value.forEach((c) => { selectedMap[c.id] = false })
}

async function handleBatchRun() {
  const ids = cases.value.filter((c) => selectedMap[c.id]).map((c) => c.id)
  if (!ids.length) { ElMessage.warning('请选择用例'); return }
  loading.value = true
  try {
    await createTestSuite({ project: projectId.value, name: suiteName.value, case_ids: ids })
    const res = await batchRunCases({
      project_id: projectId.value,
      case_ids: ids,
      name: suiteName.value,
    })
    ElMessage.success(`执行完成：通过 ${res.data.passed}/${res.data.total}`)
    router.push('/test-execution/analysis')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const res = await getProjects()
  projects.value = res.data.results ?? res.data
  projectId.value = projects.value[0]?.id ?? null
  await loadData()
})
</script>

<template>
  <div class="batch-page page-card">
    <h3>批量执行 · 测试套件</h3>
    <el-form label-width="100px" style="max-width:600px; margin-top:16px">
      <el-form-item label="项目">
        <el-select v-model="projectId" style="width:100%" @change="loadData">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="套件名称"><el-input v-model="suiteName" /></el-form-item>
      <el-form-item label="选择用例">
        <div class="case-list">
          <label v-for="c in cases" :key="c.id" class="case-item">
            <CardCheckbox v-model="selectedMap[c.id]" size="sm" />
            <span>{{ c.title }}</span>
          </label>
        </div>
      </el-form-item>
      <el-button type="primary" :loading="loading" @click="handleBatchRun">
        <el-icon><VideoPlay /></el-icon> 开始批量执行
      </el-button>
    </el-form>
  </div>
</template>

<style scoped>
h3 { color: #fff; }
.case-list { max-height: 360px; overflow-y: auto; width: 100%; }
.case-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; color: #e8eaed; font-size: 13px; }
</style>

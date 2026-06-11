<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getProjects, getTestCases, convertTestCases } from '@/api'
import CardCheckbox from '@/components/CardCheckbox.vue'

const projects = ref<{ id: number; name: string }[]>([])
const cases = ref<{ id: number; title: string }[]>([])
const projectId = ref<number | null>(null)
const format = ref('pytest')
const selectedMap = reactive<Record<number, boolean>>({})
const output = ref('')
const loading = ref(false)

async function loadData() {
  if (!projectId.value) return
  const res = await getTestCases({ project: projectId.value, page_size: 500 })
  cases.value = res.data.results ?? res.data
  cases.value.forEach((c) => { selectedMap[c.id] = false })
}

async function handleConvert() {
  const ids = cases.value.filter((c) => selectedMap[c.id]).map((c) => c.id)
  if (!ids.length) { ElMessage.warning('请选择用例'); return }
  loading.value = true
  try {
    const res = await convertTestCases({ ids, format: format.value })
    output.value = res.data.content
    ElMessage.success(`已转换 ${res.data.count} 条用例`)
  } finally {
    loading.value = false
  }
}

function copyOutput() {
  navigator.clipboard.writeText(output.value)
  ElMessage.success('已复制到剪贴板')
}

onMounted(async () => {
  const res = await getProjects()
  projects.value = res.data.results ?? res.data
  projectId.value = projects.value[0]?.id ?? null
  await loadData()
})
</script>

<template>
  <div class="convert-page">
    <div class="page-card left">
      <el-select v-model="projectId" style="width:100%; margin-bottom:12px" @change="loadData">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-radio-group v-model="format" style="margin-bottom:16px">
        <el-radio-button value="pytest">Pytest</el-radio-button>
        <el-radio-button value="postman">Postman</el-radio-button>
        <el-radio-button value="jmeter">JMeter</el-radio-button>
      </el-radio-group>
      <div class="case-select-list">
        <label v-for="c in cases" :key="c.id" class="case-select-item">
          <CardCheckbox v-model="selectedMap[c.id]" size="sm" />
          <span>{{ c.title }}</span>
        </label>
      </div>
      <el-button type="primary" :loading="loading" style="width:100%; margin-top:12px" @click="handleConvert">
        转换选中用例
      </el-button>
    </div>
    <div class="page-card right">
      <div class="output-head">
        <h3>转换输出</h3>
        <el-button v-if="output" size="small" @click="copyOutput">复制</el-button>
      </div>
      <pre class="output">{{ output || '选择用例并转换后显示结果' }}</pre>
    </div>
  </div>
</template>

<style scoped>
.convert-page { display: grid; grid-template-columns: 360px 1fr; gap: 16px; }
.case-select-list { max-height: 400px; overflow-y: auto; }
.case-select-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; color: #e8eaed; font-size: 13px; cursor: pointer; }
.output-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.output-head h3 { color: #fff; }
.output {
  background: #141c28; border: 1px solid #2a3544; border-radius: 8px;
  padding: 16px; color: #e8eaed; font-size: 13px; line-height: 1.6;
  max-height: calc(100vh - 280px); overflow: auto; white-space: pre-wrap; margin: 0;
}
</style>

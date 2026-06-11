<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getProjects, getApiInterfaces, debugApiInterface, apiTest } from '@/api'

const projects = ref<{ id: number; name: string }[]>([])
const apis = ref<{ id: number; name: string; method: string; url: string }[]>([])
const projectId = ref<number | null>(null)
const selectedApiId = ref<number | null>(null)
const variables = ref('{"baseUrl":"http://127.0.0.1:8000","token":""}')
const response = ref('')
const loading = ref(false)

const manualForm = ref({ method: 'GET', url: '', headers: '{}', body: '{}' })

async function loadApis() {
  if (!projectId.value) return
  const res = await getApiInterfaces({ project: projectId.value })
  apis.value = res.data.results ?? res.data
}

async function runSavedApi() {
  if (!selectedApiId.value) { ElMessage.warning('请选择接口'); return }
  loading.value = true
  try {
    let vars = {}
    try { vars = JSON.parse(variables.value) } catch { /* ignore */ }
    const res = await debugApiInterface(selectedApiId.value, { variables: vars })
    response.value = JSON.stringify(res.data, null, 2)
  } finally {
    loading.value = false
  }
}

async function runManual() {
  loading.value = true
  try {
    const res = await apiTest({
      method: manualForm.value.method,
      url: manualForm.value.url,
      headers: JSON.parse(manualForm.value.headers || '{}'),
      body: JSON.parse(manualForm.value.body || '{}'),
    })
    response.value = JSON.stringify(res.data, null, 2)
  } catch {
    ElMessage.error('请求失败，请检查 URL 和 JSON 格式')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const res = await getProjects()
  projects.value = res.data.results ?? res.data
  projectId.value = projects.value[0]?.id ?? null
  await loadApis()
})
</script>

<template>
  <div class="runner-page">
    <div class="page-card">
      <h3>HTTP Runner · 变量系统</h3>
      <p class="hint">支持 token、baseUrl 等变量注入，格式：{"{"}"token":"xxx"{"}"}</p>
      <el-tabs>
        <el-tab-pane label="已保存接口">
          <el-form label-width="80px" style="margin-top:12px">
            <el-form-item label="项目">
              <el-select v-model="projectId" style="width:100%" @change="loadApis">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="接口">
              <el-select v-model="selectedApiId" style="width:100%">
                <el-option v-for="a in apis" :key="a.id" :label="`${a.method} ${a.name}`" :value="a.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="变量">
              <el-input v-model="variables" type="textarea" :rows="3" />
            </el-form-item>
            <el-button type="primary" :loading="loading" @click="runSavedApi">执行</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="快速请求">
          <el-form label-width="80px" style="margin-top:12px">
            <el-form-item label="方法">
              <el-select v-model="manualForm.method" style="width:120px">
                <el-option v-for="m in ['GET','POST','PUT','DELETE','PATCH']" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>
            <el-form-item label="URL"><el-input v-model="manualForm.url" placeholder="http://..." /></el-form-item>
            <el-form-item label="Headers"><el-input v-model="manualForm.headers" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="Body"><el-input v-model="manualForm.body" type="textarea" :rows="3" /></el-form-item>
            <el-button type="primary" :loading="loading" @click="runManual">发送请求</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
    <div class="page-card">
      <h3>响应结果</h3>
      <pre class="response">{{ response || '执行后显示响应' }}</pre>
    </div>
  </div>
</template>

<style scoped>
.runner-page { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
h3 { color: #fff; margin-bottom: 8px; }
.hint { color: #6b7280; font-size: 12px; margin-bottom: 12px; }
.response {
  background: #141c28; border: 1px solid #2a3544; border-radius: 8px;
  padding: 16px; color: #10b981; font-size: 13px; line-height: 1.5;
  max-height: calc(100vh - 240px); overflow: auto; white-space: pre-wrap; margin-top: 12px;
}
</style>

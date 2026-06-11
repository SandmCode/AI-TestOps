<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiTest, parseCurl } from '@/api'

const form = ref({
  method: 'GET',
  url: '',
  headers: '{}',
  params: '{}',
  body: '{}',
})

const curlInput = ref('')
const result = ref<Record<string, unknown> | null>(null)
const loading = ref(false)

async function sendRequest() {
  if (!form.value.url) {
    ElMessage.warning('请输入 URL')
    return
  }
  loading.value = true
  try {
    let headers = {}
    let params = {}
    let body = {}
    try { headers = JSON.parse(form.value.headers || '{}') } catch { ElMessage.error('Headers JSON 格式错误'); return }
    try { params = JSON.parse(form.value.params || '{}') } catch { ElMessage.error('Params JSON 格式错误'); return }
    try { body = JSON.parse(form.value.body || '{}') } catch { ElMessage.error('Body JSON 格式错误'); return }
    const res = await apiTest({ ...form.value, headers, params, body })
    result.value = res.data
    ElMessage.success('请求完成')
  } finally {
    loading.value = false
  }
}

async function parseCurlExpr() {
  if (!curlInput.value.trim()) return
  const res = await parseCurl(curlInput.value)
  form.value.method = res.data.method
  form.value.url = res.data.url
  form.value.headers = JSON.stringify(res.data.headers, null, 2)
  form.value.body = JSON.stringify(res.data.body, null, 2)
  ElMessage.success('CURL 解析成功')
}
</script>

<template>
  <div>
    <h1 class="page-title">API 测试</h1>
    <div class="page-card">
      <h3 style="color:#fff;margin-bottom:12px">CURL 解析</h3>
      <el-input v-model="curlInput" type="textarea" :rows="3" placeholder="粘贴 curl 命令..." />
      <el-button type="primary" style="margin-top:8px" @click="parseCurlExpr">解析 CURL</el-button>

      <el-divider />

      <el-form label-width="80px">
        <el-form-item label="Method">
          <el-select v-model="form.method" style="width:120px">
            <el-option v-for="m in ['GET','POST','PUT','DELETE','PATCH']" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="URL"><el-input v-model="form.url" placeholder="https://api.example.com/users" /></el-form-item>
        <el-form-item label="Headers"><el-input v-model="form.headers" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="Params"><el-input v-model="form.params" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="Body"><el-input v-model="form.body" type="textarea" :rows="4" /></el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="sendRequest">发送请求</el-button>
        </el-form-item>
      </el-form>

      <div v-if="result" class="result-box">
        <h4>响应结果</h4>
        <p>状态码: <el-tag>{{ result.status_code }}</el-tag> 耗时: {{ result.elapsed_ms }}ms</p>
        <pre>{{ JSON.stringify(result.body, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.result-box {
  margin-top: 16px;
  background: #141c28;
  border-radius: 8px;
  padding: 16px;
}

.result-box h4 {
  color: #fff;
  margin-bottom: 8px;
}

.result-box pre {
  margin-top: 8px;
  font-size: 13px;
  color: #10b981;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>

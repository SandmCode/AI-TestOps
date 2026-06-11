<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'

export interface ApiEndpointFormRow {
  name?: string
  method?: string
  url?: string
  module?: string
  description?: string
  headers?: Record<string, unknown>
  params?: Record<string, unknown>
  body?: Record<string, unknown>
  response_example?: Record<string, unknown>
}

export interface ApiEndpointFormPayload {
  name: string
  method: string
  url: string
  module: string
  description: string
  headers: Record<string, unknown>
  params: Record<string, unknown>
  body: Record<string, unknown>
  response_example: Record<string, unknown>
}

const METHOD_OPTIONS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']

const visible = defineModel<boolean>('visible', { default: false })
const props = withDefaults(
  defineProps<{
    editingId?: number | null
    initial?: ApiEndpointFormRow | null
    entityName?: string
  }>(),
  { entityName: '接口' },
)

const emit = defineEmits<{
  save: [payload: ApiEndpointFormPayload]
}>()

const dialogTitle = computed(() =>
  props.editingId ? `编辑${props.entityName}` : `新增${props.entityName}`,
)

const form = reactive({
  name: '',
  method: 'GET',
  url: '',
  module: '',
  description: '',
  headersText: '{}',
  paramsText: '{}',
  bodyText: '{}',
  responseText: '{}',
})

function resetForm(row?: ApiEndpointFormRow | null) {
  form.name = row?.name || ''
  form.method = row?.method || 'GET'
  form.url = row?.url || ''
  form.module = row?.module || ''
  form.description = row?.description || ''
  form.headersText = JSON.stringify(row?.headers || {}, null, 2)
  form.paramsText = JSON.stringify(row?.params || {}, null, 2)
  form.bodyText = JSON.stringify(row?.body || {}, null, 2)
  form.responseText = JSON.stringify(row?.response_example || {}, null, 2)
}

watch(
  () => visible.value,
  (open) => {
    if (open) resetForm(props.initial)
  },
)

function parseJsonField(text: string, label: string) {
  try {
    const val = JSON.parse(text || '{}')
    if (val !== null && typeof val === 'object' && !Array.isArray(val)) return val
    throw new Error('must be object')
  } catch {
    throw new Error(`${label} 必须是合法 JSON 对象`)
  }
}

function handleSave() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写接口名称')
    return
  }
  if (!form.url.trim()) {
    ElMessage.warning('请填写 URL')
    return
  }
  let headers: Record<string, unknown>
  let params: Record<string, unknown>
  let body: Record<string, unknown>
  let response_example: Record<string, unknown>
  try {
    headers = parseJsonField(form.headersText, '请求头')
    params = parseJsonField(form.paramsText, 'Query 参数')
    body = parseJsonField(form.bodyText, '请求体')
    response_example = parseJsonField(form.responseText, '响应示例')
  } catch (e) {
    ElMessage.warning(e instanceof Error ? e.message : 'JSON 格式错误')
    return
  }
  emit('save', {
    name: form.name.trim(),
    method: form.method,
    url: form.url.trim(),
    module: form.module.trim(),
    description: form.description.trim(),
    headers,
    params,
    body,
    response_example,
  })
}
</script>

<template>
  <el-dialog v-model="visible" :title="dialogTitle" width="640px" destroy-on-close>
    <el-form label-width="90px">
      <el-form-item label="接口名称" required>
        <el-input v-model="form.name" placeholder="如：用户登录" />
      </el-form-item>
      <el-form-item label="请求方法" required>
        <el-select v-model="form.method" style="width:100%">
          <el-option v-for="m in METHOD_OPTIONS" :key="m" :label="m" :value="m" />
        </el-select>
      </el-form-item>
      <el-form-item label="URL" required>
        <el-input v-model="form.url" placeholder="/auth/login 或完整地址" />
      </el-form-item>
      <el-form-item label="模块">
        <el-input v-model="form.module" placeholder="如：认证" />
      </el-form-item>
      <el-form-item label="请求头">
        <el-input v-model="form.headersText" type="textarea" :rows="3" placeholder='{"Content-Type":"application/json"}' />
      </el-form-item>
      <el-form-item label="Query 参数">
        <el-input v-model="form.paramsText" type="textarea" :rows="2" placeholder="{}" />
      </el-form-item>
      <el-form-item label="请求体">
        <el-input v-model="form.bodyText" type="textarea" :rows="4" placeholder='{"username":"demo_user"}' />
      </el-form-item>
      <el-form-item label="响应示例">
        <el-input v-model="form.responseText" type="textarea" :rows="5" placeholder='{"code":0,"data":{}}' />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

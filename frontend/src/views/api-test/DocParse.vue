<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDocuments, aiParseApiDocument, batchImportApiInterfaces } from '@/api'

interface DocItem {
  id: number
  name: string
  project: number
  project_name: string
  doc_type: string
}

interface ParsedApi {
  name: string
  module: string
  method: string
  url: string
  headers: Record<string, unknown>
  params: Record<string, unknown>
  body: Record<string, unknown>
  response: Record<string, unknown>
  response_fields: ResponseField[]
  description: string
  selected?: boolean
}

interface ResponseField {
  name: string
  type?: string
  description?: string
  example?: unknown
}

interface ParsedResult {
  document_id: number
  document_name: string
  project_id: number
  interfaces: ParsedApi[]
}

const CACHE_KEY = 'api-doc-parse-cache'

const documents = ref<DocItem[]>([])
const selectedDocId = ref<number | null>(null)
const loading = ref(false)
const saving = ref(false)
const parsed = ref<ParsedResult | null>(null)
const expandedId = ref<number | null>(null)

const apiDocs = computed(() => documents.value.filter((d) => d.doc_type === 'api'))

const selectedCount = computed(() => parsed.value?.interfaces.filter((i) => i.selected !== false).length ?? 0)

function loadCache(docId: number): ParsedResult | null {
  try {
    const raw = localStorage.getItem(`${CACHE_KEY}-${docId}`)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveCache() {
  if (!parsed.value || !selectedDocId.value) return
  localStorage.setItem(`${CACHE_KEY}-${selectedDocId.value}`, JSON.stringify(parsed.value))
}

function isValidCache(cache: ParsedResult | null): boolean {
  if (!cache?.interfaces?.length) return false
  const valid = cache.interfaces.filter((i) => i.url || i.name || Object.keys(i.body || {}).length)
  return valid.length > 0
}

function restoreCache(docId: number | null) {
  if (!docId) {
    parsed.value = null
    return
  }
  const cache = loadCache(docId)
  parsed.value = cache && isValidCache(cache)
    ? { ...cache, interfaces: cache.interfaces.map((i) => ({ ...i, selected: i.selected !== false })) }
    : null
}

async function loadData() {
  const res = await getDocuments({ page_size: 500, doc_type: 'api' })
  documents.value = res.data.results ?? res.data
  if (!selectedDocId.value && apiDocs.value.length) {
    selectedDocId.value = apiDocs.value[0].id
  }
  if (selectedDocId.value) restoreCache(selectedDocId.value)
}

watch(selectedDocId, (id) => restoreCache(id))

async function handleParse() {
  if (!selectedDocId.value) {
    ElMessage.warning('请先选择接口文档')
    return
  }
  if (parsed.value) {
    try {
      await ElMessageBox.confirm('再次解析将覆盖当前结果，是否继续？', '覆盖解析', { type: 'info' })
    } catch {
      return
    }
  }
  loading.value = true
  parsed.value = null
  try {
    const res = await aiParseApiDocument(selectedDocId.value)
    parsed.value = {
      document_id: res.data.document_id,
      document_name: res.data.document_name,
      project_id: res.data.project_id,
      interfaces: (res.data.interfaces ?? []).map((item: ParsedApi) => ({ ...item, selected: true })),
    }
    saveCache()
    const source = res.data.parse_source === 'markdown' ? '规则解析' : 'AI 解析'
    ElMessage.success(`解析完成（${source}），共 ${parsed.value.interfaces.length} 个接口`)
  } finally {
    loading.value = false
  }
}

async function handleImport() {
  if (!parsed.value) return
  const items = parsed.value.interfaces.filter((i) => i.selected !== false)
  if (!items.length) {
    ElMessage.warning('请至少选择一个接口')
    return
  }
  try {
    await ElMessageBox.confirm(`将导入 ${items.length} 个接口到项目接口库，是否继续？`, '导入接口')
  } catch {
    return
  }
  saving.value = true
  try {
    const res = await batchImportApiInterfaces({
      project_id: parsed.value.project_id,
      document_id: parsed.value.document_id,
      interfaces: items.map(({ selected: _, ...rest }) => rest),
    })
    ElMessage.success(
      res.data.auto_deps?.auto_configured
        ? `已导入 ${res.data.count} 个接口，并自动配置 ${res.data.auto_deps.updated_count ?? 0} 个登录关联`
        : `已导入 ${res.data.count} 个接口，可在「接口自动化」中使用`,
    )
  } finally {
    saving.value = false
  }
}

function toggleAll(val: boolean) {
  parsed.value?.interfaces.forEach((i) => { i.selected = val })
}

async function removeSelected() {
  if (!parsed.value) return
  const items = parsed.value.interfaces.filter((i) => i.selected !== false)
  if (!items.length) {
    ElMessage.warning('请先勾选要删除的接口')
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${items.length} 条解析结果？`, '批量删除', { type: 'warning' })
  } catch {
    return
  }
  parsed.value.interfaces = parsed.value.interfaces.filter((i) => i.selected === false)
  if (expandedId.value !== null && expandedId.value >= parsed.value.interfaces.length) {
    expandedId.value = null
  }
  saveCache()
  ElMessage.success(`已删除 ${items.length} 条`)
}

async function removeOne(idx: number) {
  if (!parsed.value) return
  const item = parsed.value.interfaces[idx]
  try {
    await ElMessageBox.confirm(`确定删除「${item.name}」？`, '删除接口', { type: 'warning' })
  } catch {
    return
  }
  parsed.value.interfaces.splice(idx, 1)
  if (expandedId.value === idx) expandedId.value = null
  else if (expandedId.value !== null && expandedId.value > idx) expandedId.value -= 1
  saveCache()
  ElMessage.success('已删除')
}

function formatJson(obj: Record<string, unknown> | unknown[] | unknown) {
  if (obj == null) return '—'
  if (Array.isArray(obj)) return obj.length ? JSON.stringify(obj, null, 2) : '—'
  if (typeof obj === 'object') return Object.keys(obj as object).length ? JSON.stringify(obj, null, 2) : '—'
  return String(obj)
}

function hasResponse(item: ParsedApi) {
  return Object.keys(item.response || {}).length > 0 || (item.response_fields?.length ?? 0) > 0
}

onMounted(loadData)
</script>

<template>
  <div class="doc-parse-page">
    <div class="page-card left-panel">
      <h3>选择接口文档</h3>
      <el-select v-model="selectedDocId" placeholder="从需求文档中选择接口文档" filterable style="width:100%; margin: 12px 0">
        <el-option
          v-for="d in apiDocs"
          :key="d.id"
          :label="`${d.name} (${d.project_name})`"
          :value="d.id"
        />
      </el-select>
      <el-button type="primary" :loading="loading" style="width:100%" @click="handleParse">
        <el-icon><MagicStick /></el-icon> 解析接口文档
      </el-button>
      <p class="hint">优先使用 Markdown 规则解析（秒级）；不符合格式时再调用 AI。会提取请求参数、响应示例与返回字段说明。若曾解析出空结果，请重新点击解析。</p>
    </div>

    <div class="page-card right-panel">
      <div v-if="!parsed" class="empty-hint">
        <el-empty description="选择接口文档并点击解析" />
      </div>
      <template v-else>
        <div class="result-header">
          <div>
            <h3>解析结果 · {{ parsed.interfaces.length }} 个接口</h3>
            <p class="doc-name">{{ parsed.document_name }}</p>
          </div>
          <div class="header-actions">
            <el-button @click="toggleAll(true)">全选</el-button>
            <el-button @click="toggleAll(false)">取消全选</el-button>
            <el-button type="danger" plain :disabled="!selectedCount" @click="removeSelected">
              批量删除 ({{ selectedCount }})
            </el-button>
            <el-button type="success" :loading="saving" @click="handleImport">
              导入接口库 ({{ selectedCount }})
            </el-button>
          </div>
        </div>

        <div class="api-list">
          <div v-for="(item, idx) in parsed.interfaces" :key="idx" class="api-item">
            <div class="api-item-head">
              <el-checkbox v-model="item.selected" />
              <el-tag size="small" :type="item.method === 'GET' ? 'success' : 'primary'">{{ item.method }}</el-tag>
              <strong>{{ item.name }}</strong>
              <span v-if="item.module" class="module-tag">{{ item.module }}</span>
              <el-button link type="primary" @click="expandedId = expandedId === idx ? null : idx">
                {{ expandedId === idx ? '收起' : '详情' }}
              </el-button>
              <el-button link type="danger" @click="removeOne(idx)">删除</el-button>
            </div>
            <div class="api-url">{{ item.url }}</div>
            <p v-if="item.description" class="api-desc">{{ item.description }}</p>
            <div v-if="hasResponse(item) && expandedId !== idx" class="response-preview">
              <span class="preview-label">响应示例</span>
              <code>{{ formatJson(item.response).slice(0, 120) }}{{ formatJson(item.response).length > 120 ? '…' : '' }}</code>
            </div>
            <div v-if="expandedId === idx" class="api-detail">
              <div class="detail-row"><span>请求头</span><pre>{{ formatJson(item.headers) }}</pre></div>
              <div class="detail-row"><span>Query 参数</span><pre>{{ formatJson(item.params) }}</pre></div>
              <div class="detail-row"><span>请求体</span><pre>{{ formatJson(item.body) }}</pre></div>
              <div class="detail-row"><span>响应示例</span><pre>{{ formatJson(item.response) }}</pre></div>
              <div v-if="item.response_fields?.length" class="detail-row">
                <span>返回参数字段</span>
                <el-table :data="item.response_fields" size="small" class="field-table">
                  <el-table-column prop="name" label="字段" min-width="120" />
                  <el-table-column prop="type" label="类型" width="90" />
                  <el-table-column prop="description" label="说明" min-width="160" show-overflow-tooltip />
                  <el-table-column label="示例" min-width="100">
                    <template #default="{ row }">{{ row.example ?? '—' }}</template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.doc-parse-page { display: grid; grid-template-columns: 320px 1fr; gap: 16px; min-height: 500px; }
.left-panel h3, .right-panel h3 { color: #fff; margin: 0 0 8px; }
.hint { font-size: 12px; color: #6b7280; margin-top: 12px; line-height: 1.6; }
.result-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; }
.header-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.doc-name { margin: 0; font-size: 13px; color: #6b7280; }
.api-list { max-height: calc(100vh - 280px); overflow-y: auto; }
.api-item {
  padding: 14px; margin-bottom: 8px; background: #0f1419;
  border: 1px solid #2a3544; border-radius: 8px;
}
.api-item-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.api-item-head strong { color: #f3f4f6; }
.module-tag { font-size: 12px; color: #6b7280; background: #1a2332; padding: 2px 8px; border-radius: 4px; }
.api-url { font-family: monospace; font-size: 13px; color: #60a5fa; word-break: break-all; }
.api-desc { font-size: 13px; color: #9aa0a6; margin: 8px 0 0; line-height: 1.5; }
.response-preview {
  margin-top: 8px; padding: 8px 10px; background: #0a0e14; border-radius: 6px;
  font-size: 12px; color: #9aa0a6;
}
.preview-label { color: #4ade80; margin-right: 8px; }
.response-preview code { color: #d1d5db; font-family: monospace; word-break: break-all; }
.field-table { margin-top: 6px; }
.api-detail { margin-top: 12px; display: grid; gap: 10px; }
.detail-row span { display: block; font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.detail-row pre {
  margin: 0; padding: 10px; background: #0a0e14; border-radius: 6px;
  font-size: 12px; color: #d1d5db; overflow-x: auto; white-space: pre-wrap;
}
.empty-hint { padding: 60px 0; }
</style>

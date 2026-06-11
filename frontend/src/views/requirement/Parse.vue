<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getDocuments, getProjects, aiParseDocumentDetail, batchCreateTestPoints,
} from '@/api'
import {
  loadParseCache, saveParseCache, getLastParseDocumentId, type ParseItem, type ParsedCache,
} from '@/composables/useParseCache'

interface DocItem { id: number; name: string; project: number; project_name: string; version: string; file_ext: string }

interface ParsedResult {
  document_id?: number
  document_name?: string
  features: ParseItem[]
  constraints: ParseItem[]
  exceptions: ParseItem[]
}

const router = useRouter()
const documents = ref<DocItem[]>([])
const projects = ref<{ id: number; name: string }[]>([])
const selectedDocId = ref<number | null>(null)
const loading = ref(false)
const saving = ref(false)
const activeTab = ref('features')
const parsed = ref<ParsedResult | null>(null)
const parseVersion = ref(0)
const cacheHint = ref('')

function applyCache(cache: ParsedCache) {
  parsed.value = {
    document_id: cache.document_id,
    document_name: cache.document_name,
    features: cache.features,
    constraints: cache.constraints,
    exceptions: cache.exceptions,
  }
  parseVersion.value = cache.parseVersion
  const time = new Date(cache.updatedAt).toLocaleString()
  cacheHint.value = `已恢复 ${time} 的解析缓存，再次 AI 解析将覆盖`
}

function restoreCacheForDoc(docId: number | null) {
  if (!docId) {
    parsed.value = null
    parseVersion.value = 0
    cacheHint.value = ''
    return
  }
  const cache = loadParseCache(docId)
  if (cache) applyCache(cache)
  else {
    parsed.value = null
    parseVersion.value = 0
    cacheHint.value = ''
  }
}

function persistCache() {
  if (!parsed.value || !selectedDocId.value) return
  const doc = documents.value.find((d) => d.id === selectedDocId.value)
  saveParseCache(selectedDocId.value, {
    document_id: selectedDocId.value,
    document_name: parsed.value.document_name || doc?.name || '',
    features: parsed.value.features,
    constraints: parsed.value.constraints,
    exceptions: parsed.value.exceptions,
    parseVersion: parseVersion.value,
  })
  cacheHint.value = '解析结果已自动保存，刷新页面不会丢失'
}

async function loadData() {
  const [docRes, projRes] = await Promise.all([
    getDocuments({ page_size: 500 }),
    getProjects(),
  ])
  documents.value = docRes.data.results ?? docRes.data
  projects.value = projRes.data.results ?? projRes.data
  if (!selectedDocId.value) {
    const lastId = getLastParseDocumentId()
    if (lastId && documents.value.some((d) => d.id === lastId)) {
      selectedDocId.value = lastId
    }
  }
  if (selectedDocId.value) restoreCacheForDoc(selectedDocId.value)
}

watch(selectedDocId, (id) => {
  activeTab.value = 'features'
  restoreCacheForDoc(id)
})

async function handleParse() {
  if (!selectedDocId.value) {
    ElMessage.warning('请先选择需求文档')
    return
  }
  if (parsed.value) {
    try {
      await ElMessageBox.confirm(
        '再次解析将覆盖当前解析结果（含已缓存数据），是否继续？',
        '覆盖解析',
        { type: 'info', confirmButtonText: '覆盖并解析' },
      )
    } catch {
      return
    }
  }
  loading.value = true
  parsed.value = null
  try {
    const res = await aiParseDocumentDetail(selectedDocId.value)
    const isReparse = parseVersion.value > 0
    parseVersion.value = isReparse ? parseVersion.value + 1 : 1
    parsed.value = {
      document_id: res.data.document_id,
      document_name: res.data.document_name,
      features: res.data.features ?? [],
      constraints: res.data.constraints ?? [],
      exceptions: res.data.exceptions ?? [],
    }
    activeTab.value = 'features'
    persistCache()
    ElMessage.success(isReparse ? 'AI 解析完成（已覆盖并保存）' : 'AI 解析完成')
  } finally {
    loading.value = false
  }
}

async function saveToTestPoints() {
  if (!parsed.value || !selectedDocId.value) return
  const doc = documents.value.find((d) => d.id === selectedDocId.value)
  if (!doc) return
  const items = [
    ...parsed.value.features,
    ...parsed.value.constraints,
    ...parsed.value.exceptions,
  ]
  try {
    await ElMessageBox.confirm(
      `将覆盖文档「${doc.name}」此前已保存的测试点，并写入本次 ${items.length} 条新结果。`,
      '覆盖保存',
      { type: 'warning', confirmButtonText: '覆盖保存' },
    )
  } catch {
    return
  }
  saving.value = true
  try {
    const res = await batchCreateTestPoints({
      document_id: doc.id,
      project_id: doc.project,
      items,
      replace: true,
    })
    const replaced = res.data.replaced_count ?? 0
    const msg = replaced > 0
      ? `已覆盖保存 ${items.length} 个测试点（替换 ${replaced} 个旧数据）`
      : `已保存 ${items.length} 个测试点`
    ElMessage.success(msg)
    router.push('/requirement-center/test-points')
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="parse-page">
    <div class="page-card left-panel">
      <h3>选择需求文档</h3>
      <el-select v-model="selectedDocId" placeholder="从需求文档管理中选择" filterable style="width:100%; margin: 12px 0">
        <el-option
          v-for="d in documents"
          :key="d.id"
          :label="`${d.name} (${d.project_name})`"
          :value="d.id"
        />
      </el-select>
      <el-button type="primary" :loading="loading" style="width:100%" @click="handleParse">
        <el-icon><MagicStick /></el-icon> AI 解析文档
      </el-button>
      <p v-if="cacheHint" class="cache-hint">{{ cacheHint }}</p>
      <p class="hint">解析结果会自动保存在浏览器中，刷新不丢失；再次 AI 解析或覆盖保存时会替换旧数据。</p>
    </div>

    <div class="page-card right-panel">
      <div v-if="!parsed" class="empty-hint">
        <el-empty description="选择文档并点击 AI 解析，或选择已有缓存的文档" />
      </div>
      <template v-else>
        <div class="result-header">
          <div>
            <h3>解析结果</h3>
            <p v-if="parsed.document_name" class="doc-name">{{ parsed.document_name }}</p>
          </div>
          <div class="header-actions">
            <el-tag v-if="parseVersion > 0" type="info" size="small">v{{ parseVersion }}</el-tag>
            <el-button type="success" :loading="saving" @click="saveToTestPoints">保存测试点</el-button>
          </div>
        </div>
        <el-tabs v-model="activeTab">
          <el-tab-pane :label="`功能需求 (${parsed.features.length})`" name="features" />
          <el-tab-pane :label="`约束 (${parsed.constraints.length})`" name="constraints" />
          <el-tab-pane :label="`异常场景 (${parsed.exceptions.length})`" name="exceptions" />
        </el-tabs>
        <div class="parse-list">
          <div v-for="(item, idx) in parsed[activeTab as keyof typeof parsed]" :key="idx" class="parse-item">
            <div class="parse-item-head">
              <el-tag size="small">{{ item.module || '未分类' }}</el-tag>
              <strong>{{ item.name }}</strong>
            </div>
            <p>{{ item.description }}</p>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.parse-page { display: grid; grid-template-columns: 320px 1fr; gap: 16px; min-height: 500px; }
.left-panel h3, .right-panel h3 { color: #fff; margin: 0 0 8px; }
.hint { font-size: 12px; color: #6b7280; margin-top: 12px; line-height: 1.6; }
.cache-hint { font-size: 12px; color: #4ade80; margin-top: 10px; line-height: 1.5; }
.result-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; gap: 12px; }
.header-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.doc-name { margin: 0; font-size: 13px; color: #6b7280; }
.parse-list { max-height: calc(100vh - 340px); overflow-y: auto; }
.parse-item {
  padding: 14px; margin-bottom: 8px; background: #0f1419;
  border: 1px solid #2a3544; border-radius: 8px;
}
.parse-item-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.parse-item-head strong { color: #f3f4f6; }
.parse-item p { color: #9aa0a6; font-size: 13px; line-height: 1.6; margin: 0; }
.empty-hint { padding: 60px 0; }
</style>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { genFileId } from 'element-plus'
import type { UploadFile, UploadInstance, UploadProps, UploadRawFile } from 'element-plus'
import {
  getDocuments,
  getProjects,
  updateDocument,
  deleteDocument,
  batchDeleteDocuments,
  downloadDocument,
} from '@/api'
import { useChunkUpload } from '@/composables/useChunkUpload'
import CardCheckbox from '@/components/CardCheckbox.vue'

interface DocumentItem {
  id: number
  name: string
  version: string
  doc_type: string
  doc_type_display: string
  project: number
  project_name: string
  content: string
  file_url: string
  original_name: string
  file_ext: string
  file_size: number
  preview_mode: string
  created_at: string
}

interface ProjectItem { id: number; name: string }

const router = useRouter()
const uploadRef = ref<UploadInstance>()
const documents = ref<DocumentItem[]>([])
const projects = ref<ProjectItem[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const showFilter = ref(true)
const uploadFile = ref<File | null>(null)
const highlightId = ref<number | null>(null)
const saving = ref(false)
const uploadKey = ref(0)
const selectedMap = reactive<Record<number, boolean>>({})

const chunk = useChunkUpload()

const selectedIds = computed(() => documents.value.filter((d) => selectedMap[d.id]).map((d) => d.id))

const isAllSelected = computed({
  get: () => documents.value.length > 0 && documents.value.every((d) => selectedMap[d.id]),
  set: (val: boolean) => {
    documents.value.forEach((d) => { selectedMap[d.id] = val })
  },
})

const selectedCount = computed(() => selectedIds.value.length)

function resetSelection(items: { id: number }[]) {
  Object.keys(selectedMap).forEach((k) => delete selectedMap[Number(k)])
  items.forEach((item) => { selectedMap[item.id] = false })
}

const filters = ref({
  search: '',
  project: null as number | null,
  doc_type: '',
  file_ext: '',
  created_after: '',
  created_before: '',
})

const form = ref({
  project: null as number | null,
  name: '',
  version: '',
  doc_type: 'requirement',
  content: '',
})

const docTypeMap: Record<string, string> = {
  requirement: '需求文档',
  api: '接口文档',
  prd: 'PRD文档',
  prototype: '原型图',
  other: '其他',
}

const extOptions = ['pdf', 'docx', 'doc', 'md', 'json', 'yaml', 'png', 'jpg', 'txt', 'xml']

const uploadModeText = computed(() => {
  if (!uploadFile.value) return ''
  return chunk.isChunkMode(uploadFile.value) ? '分片上传 · 支持断点续传' : '普通上传'
})

const dialogTitle = computed(() => {
  if (chunk.status.value === 'success') return '上传完成'
  if (chunk.status.value === 'uploading' || chunk.status.value === 'merging') return '正在上传...'
  if (chunk.status.value === 'paused') return '上传已暂停'
  return editingId.value ? '编辑文档' : '上传文档'
})

function buildParams() {
  const params: Record<string, unknown> = { page_size: 500 }
  if (filters.value.search.trim()) params.search = filters.value.search.trim()
  if (filters.value.project) params.project = filters.value.project
  if (filters.value.doc_type) params.doc_type = filters.value.doc_type
  if (filters.value.file_ext) params.file_ext = filters.value.file_ext
  if (filters.value.created_after) params.created_after = filters.value.created_after
  if (filters.value.created_before) params.created_before = filters.value.created_before
  return params
}

async function loadData() {
  loading.value = true
  try {
    const [docRes, projRes] = await Promise.all([getDocuments(buildParams()), getProjects()])
    documents.value = docRes.data.results ?? docRes.data
    projects.value = projRes.data.results ?? projRes.data
    resetSelection(documents.value)
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.value = { search: '', project: null, doc_type: '', file_ext: '', created_after: '', created_before: '' }
  loadData()
}

function formatSize(size: number) {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ') ?? '-'
}

function extIcon(ext: string) {
  const map: Record<string, string> = {
    pdf: 'Document', json: 'Tickets', yaml: 'Tickets', yml: 'Tickets',
    md: 'Notebook', png: 'Picture', jpg: 'Picture', jpeg: 'Picture',
    docx: 'Document', doc: 'Document',
  }
  return map[ext?.toLowerCase()] || 'Document'
}

function resetUploadState() {
  uploadFile.value = null
  chunk.reset()
  uploadKey.value++
}

function openCreate() {
  editingId.value = null
  resetUploadState()
  form.value = { project: projects.value[0]?.id ?? null, name: '', version: 'v1.0', doc_type: 'requirement', content: '' }
  dialogVisible.value = true
}

function openEdit(row: DocumentItem) {
  editingId.value = row.id
  resetUploadState()
  form.value = {
    project: row.project,
    name: row.name,
    version: row.version,
    doc_type: row.doc_type,
    content: row.content,
  }
  dialogVisible.value = true
}

function applySelectedFile(file: File) {
  uploadFile.value = file
  chunk.reset()
  form.value.name = file.name.replace(/\.[^.]+$/, '')
}

function onFileChange(file: UploadFile) {
  if (file.raw) applySelectedFile(file.raw)
}

const onExceed: UploadProps['onExceed'] = (files) => {
  uploadRef.value?.clearFiles()
  const raw = files[0] as UploadRawFile
  raw.uid = genFileId()
  uploadRef.value?.handleStart(raw)
  applySelectedFile(raw)
}

function onFileRemove() {
  uploadFile.value = null
  chunk.reset()
}

function continueUpload() {
  resetUploadState()
  form.value = {
    project: form.value.project,
    name: '',
    version: 'v1.0',
    doc_type: 'requirement',
    content: '',
  }
}

function closeDialog() {
  if (chunk.status.value === 'uploading' || chunk.status.value === 'merging') {
    ElMessage.warning('上传进行中，请先暂停或取消')
    return
  }
  dialogVisible.value = false
  resetUploadState()
}

async function saveDocument() {
  if (!form.value.project || !form.value.name) {
    ElMessage.warning('请填写项目和文档名称')
    return
  }

  if (editingId.value) {
    saving.value = true
    try {
      if (uploadFile.value) {
        const fd = new FormData()
        fd.append('project', String(form.value.project))
        fd.append('name', form.value.name)
        fd.append('version', form.value.version)
        fd.append('doc_type', form.value.doc_type)
        fd.append('content', form.value.content)
        fd.append('file', uploadFile.value)
        await updateDocument(editingId.value, fd)
      } else {
        await updateDocument(editingId.value, form.value)
      }
      ElMessage.success('更新成功')
      dialogVisible.value = false
      await loadData()
    } finally {
      saving.value = false
    }
    return
  }

  if (!uploadFile.value) {
    ElMessage.warning('请上传文档文件')
    return
  }

  saving.value = true
  try {
    const result = await chunk.startUpload(uploadFile.value, {
      project: form.value.project!,
      name: form.value.name,
      version: form.value.version,
      doc_type: form.value.doc_type,
      content: form.value.content,
    })
    highlightId.value = result.id
    await loadData()
    await nextTick()
    setTimeout(() => {
      document.getElementById(`doc-${result.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      setTimeout(() => { highlightId.value = null }, 4000)
    }, 300)
  } catch {
    /* error shown in dialog */
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: DocumentItem) {
  await ElMessageBox.confirm(
    `确定删除文档「${row.name}」？关联文件也会一并删除。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
  await deleteDocument(row.id)
  ElMessage.success('删除成功')
  loadData()
}

async function handleBatchDelete() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先选择要删除的文档')
    return
  }
  await ElMessageBox.confirm(
    `确定批量删除选中的 ${selectedIds.value.length} 个文档？文件也会一并删除，此操作不可恢复。`,
    '批量删除确认',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  await batchDeleteDocuments(selectedIds.value)
  ElMessage.success(`已删除 ${selectedIds.value.length} 个文档`)
  loadData()
}

function goPreview(row: DocumentItem) {
  router.push(`/documents/${row.id}/preview`)
}

function handleDownload(row: DocumentItem) {
  if (!row.file_url) {
    ElMessage.warning('该文档没有可下载的文件')
    return
  }
  window.open(downloadDocument(row.id), '_blank')
}

onMounted(loadData)
</script>

<template>
  <div>
    <h1 class="page-title">需求文档</h1>

    <div class="filter-card">
      <div class="filter-header">
        <span class="filter-title"><el-icon><Filter /></el-icon> 筛选条件</span>
        <el-button link type="primary" @click="showFilter = !showFilter">{{ showFilter ? '收起' : '展开' }}</el-button>
      </div>
      <el-collapse-transition>
        <div v-show="showFilter" class="filter-body">
          <el-row :gutter="16">
            <el-col :xs="24" :sm="12" :md="6">
              <div class="filter-item"><label>文档名称</label><el-input v-model="filters.search" placeholder="搜索名称/文件名" clearable /></div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <div class="filter-item">
                <label>所属项目</label>
                <el-select v-model="filters.project" placeholder="全部项目" clearable style="width:100%">
                  <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
                </el-select>
              </div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <div class="filter-item">
                <label>文档类型</label>
                <el-select v-model="filters.doc_type" placeholder="全部类型" clearable style="width:100%">
                  <el-option v-for="(label, key) in docTypeMap" :key="key" :label="label" :value="key" />
                </el-select>
              </div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <div class="filter-item">
                <label>文件格式</label>
                <el-select v-model="filters.file_ext" placeholder="全部格式" clearable style="width:100%">
                  <el-option v-for="ext in extOptions" :key="ext" :label="ext.toUpperCase()" :value="ext" />
                </el-select>
              </div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <div class="filter-item"><label>创建时间（起）</label><el-date-picker v-model="filters.created_after" type="date" value-format="YYYY-MM-DD" style="width:100%" /></div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <div class="filter-item"><label>创建时间（止）</label><el-date-picker v-model="filters.created_before" type="date" value-format="YYYY-MM-DD" style="width:100%" /></div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6" class="filter-actions">
              <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> 查询</el-button>
              <el-button @click="resetFilters"><el-icon><RefreshLeft /></el-icon> 重置</el-button>
            </el-col>
          </el-row>
        </div>
      </el-collapse-transition>
    </div>

    <div class="page-card list-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <label class="select-all">
            <CardCheckbox
              v-model="isAllSelected"
              :indeterminate="selectedCount > 0 && selectedCount < documents.length"
            />
            <span>全选</span>
          </label>
          <span v-if="selectedCount" class="selected-tip">已选 {{ selectedCount }} 项</span>
          <el-button v-if="selectedCount" type="danger" plain round @click="handleBatchDelete">
            <el-icon><Delete /></el-icon> 批量删除
          </el-button>
          <span class="doc-count">共 {{ documents.length }} 个文档</span>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" round @click="openCreate"><el-icon><UploadFilled /></el-icon> 上传文档</el-button>
        </div>
      </div>

      <div v-loading="loading" class="doc-list">
        <div
          v-for="row in documents"
          :id="`doc-${row.id}`"
          :key="row.id"
          class="doc-item"
          :class="{ 'doc-item--highlight': highlightId === row.id, selected: selectedMap[row.id] }"
        >
          <div class="checkbox-wrap" @click.stop @mousedown.stop>
            <CardCheckbox v-model="selectedMap[row.id]" />
          </div>
          <div class="doc-icon" :class="`ext-${row.file_ext}`">
            <el-icon :size="28"><component :is="extIcon(row.file_ext)" /></el-icon>
          </div>
          <div class="doc-body">
            <div class="doc-header">
              <strong class="doc-name">{{ row.name }}</strong>
              <el-tag size="small" effect="plain">{{ row.doc_type_display || docTypeMap[row.doc_type] }}</el-tag>
              <el-tag v-if="row.file_ext" size="small" type="info">{{ row.file_ext.toUpperCase() }}</el-tag>
              <el-tag v-if="row.file_size >= 104857600" size="small" type="warning">大文件</el-tag>
            </div>
            <div class="doc-meta">
              <span>项目: {{ row.project_name }}</span>
              <span>版本: {{ row.version || '-' }}</span>
              <span>大小: {{ formatSize(row.file_size) }}</span>
              <span>上传: {{ formatTime(row.created_at) }}</span>
            </div>
            <div v-if="row.original_name" class="doc-file">文件: {{ row.original_name }}</div>
          </div>
          <div class="doc-actions">
            <el-button type="primary" link @click="goPreview(row)">预览</el-button>
            <el-button link @click="openEdit(row)">编辑</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
            <el-button link @click="handleDownload(row)">下载</el-button>
          </div>
        </div>
        <el-empty v-if="!documents.length && !loading" description="暂无文档，点击上传文档开始" />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px" destroy-on-close :close-on-click-modal="false" @close="closeDialog">
      <!-- 上传成功 -->
      <div v-if="chunk.status.value === 'success'" class="upload-success">
        <div class="success-icon"><el-icon :size="56"><CircleCheckFilled /></el-icon></div>
        <h3>上传成功</h3>
        <p>文档已保存，可继续上传其他文件</p>
        <div class="success-actions">
          <el-button type="primary" @click="continueUpload">继续上传</el-button>
          <el-button @click="dialogVisible = false">关闭</el-button>
        </div>
      </div>

      <!-- 上传进度 -->
      <div v-else-if="['uploading', 'paused', 'merging'].includes(chunk.status.value)" class="upload-progress-panel">
        <div class="progress-file">
          <el-icon :size="32"><Document /></el-icon>
          <div>
            <strong>{{ uploadFile?.name }}</strong>
            <p>{{ formatSize(uploadFile?.size || 0) }} · {{ uploadModeText }}</p>
          </div>
        </div>
        <el-progress :percentage="chunk.progress.value" :status="chunk.status.value === 'merging' ? 'success' : undefined" :stroke-width="14" striped striped-flow />
        <div class="progress-meta">
          <span>{{ chunk.status.value === 'merging' ? '正在合并分片...' : chunk.status.value === 'paused' ? '已暂停' : '上传中' }}</span>
          <span v-if="chunk.speedText.value">{{ chunk.speedText.value }}</span>
        </div>
        <div class="progress-actions">
          <el-button v-if="chunk.status.value === 'uploading'" @click="chunk.pause()">暂停</el-button>
          <el-button v-if="chunk.status.value === 'paused'" type="primary" @click="chunk.resume()">继续上传</el-button>
          <el-button type="danger" plain @click="chunk.cancel()">取消上传</el-button>
        </div>
      </div>

      <!-- 表单 -->
      <template v-else>
        <el-form label-width="90px">
          <el-form-item label="所属项目" required>
            <el-select v-model="form.project" style="width:100%">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="文档名称" required><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="文档版本"><el-input v-model="form.version" /></el-form-item>
          <el-form-item label="文档类型">
            <el-select v-model="form.doc_type" style="width:100%">
              <el-option v-for="(label, key) in docTypeMap" :key="key" :label="label" :value="key" />
            </el-select>
          </el-form-item>
          <el-form-item :label="editingId ? '更换文件' : '上传文件'" :required="!editingId">
            <el-upload
              :key="uploadKey"
              ref="uploadRef"
              drag
              :auto-upload="false"
              :limit="1"
              :disabled="saving"
              :on-change="onFileChange"
              :on-exceed="onExceed"
              :on-remove="onFileRemove"
              accept=".pdf,.doc,.docx,.md,.markdown,.txt,.json,.yaml,.yml,.xml,.csv,.png,.jpg,.jpeg,.gif,.webp,.zip,.rar,.7z,.xmind"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
              <template #tip>
                <div class="el-upload__tip">支持 PDF/Word/MD/JSON/YAML/图片等，最大 10GB，超过 20MB 自动分片+断点续传</div>
              </template>
            </el-upload>
          </el-form-item>

          <!-- 已选文件卡片 -->
          <div v-if="uploadFile" class="selected-file-card">
            <div class="sfc-icon"><el-icon :size="24"><Document /></el-icon></div>
            <div class="sfc-info">
              <strong>{{ uploadFile.name }}</strong>
              <p>{{ formatSize(uploadFile.size) }}</p>
              <el-tag size="small" :type="chunk.isChunkMode(uploadFile) ? 'warning' : 'success'">
                {{ uploadModeText }}
              </el-tag>
            </div>
            <el-icon class="sfc-check" color="#10b981"><CircleCheck /></el-icon>
          </div>

          <el-form-item label="补充说明">
            <el-input v-model="form.content" type="textarea" :rows="3" placeholder="可选：补充文档说明" />
          </el-form-item>
        </el-form>
        <div v-if="chunk.status.value === 'error'" class="upload-error">{{ chunk.errorMessage.value }}</div>
      </template>

      <template #footer>
        <template v-if="!['uploading', 'paused', 'merging', 'success'].includes(chunk.status.value)">
          <el-button @click="closeDialog">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveDocument">
            {{ editingId ? '保存' : '开始上传' }}
          </el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.filter-card { background: #1a2332; border: 1px solid #2a3544; border-radius: 12px; padding: 16px 20px; }
.filter-header { display: flex; justify-content: space-between; align-items: center; }
.filter-title { display: flex; align-items: center; gap: 6px; font-weight: 600; color: #e8eaed; }
.filter-body { margin-top: 16px; }
.filter-item { margin-bottom: 12px; }
.filter-item label { display: block; font-size: 12px; color: #6b7280; margin-bottom: 6px; }
.filter-actions { display: flex; align-items: flex-end; gap: 8px; padding-bottom: 12px; }
.list-card { margin-top: 16px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
.toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 12px; }
.select-all {
  display: inline-flex; align-items: center; gap: 8px;
  cursor: pointer; user-select: none; color: #9aa0a6; font-size: 14px;
}
.select-all:hover { color: #e8eaed; }
.selected-tip {
  font-size: 13px; color: #3b82f6;
  padding: 4px 10px; background: #3b82f614; border-radius: 20px;
}
.doc-count { font-size: 13px; color: #6b7280; }
.checkbox-wrap { flex-shrink: 0; margin-top: 12px; padding: 2px; }
.doc-list { min-height: 120px; }
.doc-item {
  display: flex; gap: 14px; padding: 16px; margin-bottom: 10px;
  background: #141c28; border: 1px solid #2a3544; border-radius: 10px;
  align-items: flex-start; transition: all 0.35s ease;
}
.doc-item:hover { border-color: #3b82f6; }
.doc-item.selected { border-color: #3b82f6; background: #1a2744; }
.doc-item--highlight {
  border-color: #10b981 !important;
  background: #10b98114 !important;
  box-shadow: 0 0 0 1px #10b98144, 0 4px 20px #10b98122;
  animation: pulse-highlight 1.5s ease 2;
}
@keyframes pulse-highlight {
  0%, 100% { box-shadow: 0 0 0 1px #10b98144, 0 4px 20px #10b98122; }
  50% { box-shadow: 0 0 0 2px #10b98188, 0 4px 28px #10b98144; }
}
.doc-icon {
  width: 48px; height: 48px; border-radius: 10px;
  background: #3b82f618; color: #3b82f6;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.doc-icon.ext-pdf { background: #ef444418; color: #ef4444; }
.doc-icon.ext-json, .doc-icon.ext-yaml, .doc-icon.ext-yml { background: #f59e0b18; color: #f59e0b; }
.doc-icon.ext-png, .doc-icon.ext-jpg, .doc-icon.ext-jpeg { background: #8b5cf618; color: #8b5cf6; }
.doc-body { flex: 1; min-width: 0; }
.doc-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.doc-name { color: #f3f4f6; font-size: 15px; }
.doc-meta { margin-top: 8px; font-size: 12px; color: #6b7280; display: flex; flex-wrap: wrap; gap: 14px; }
.doc-file { margin-top: 6px; font-size: 12px; color: #9aa0a6; }
.doc-actions { display: flex; gap: 4px; flex-shrink: 0; align-items: center; flex-wrap: wrap; }

.selected-file-card {
  display: flex; align-items: center; gap: 14px;
  margin: 0 0 16px 90px; padding: 14px 16px;
  background: #10b98114; border: 1px solid #10b98144; border-radius: 10px;
}
.sfc-icon { color: #3b82f6; }
.sfc-info { flex: 1; }
.sfc-info strong { color: #f3f4f6; display: block; margin-bottom: 4px; }
.sfc-info p { font-size: 12px; color: #6b7280; margin-bottom: 6px; }
.sfc-check { font-size: 22px; }

.upload-success { text-align: center; padding: 40px 20px; }
.success-icon { color: #10b981; margin-bottom: 16px; }
.upload-success h3 { color: #fff; font-size: 20px; margin-bottom: 8px; }
.upload-success p { color: #6b7280; font-size: 14px; }
.success-actions { display: flex; gap: 12px; justify-content: center; margin-top: 24px; }

.upload-progress-panel { padding: 8px 0 16px; }
.progress-file { display: flex; gap: 14px; align-items: center; margin-bottom: 20px; color: #3b82f6; }
.progress-file strong { color: #f3f4f6; display: block; }
.progress-file p { font-size: 12px; color: #6b7280; margin-top: 4px; }
.progress-meta { display: flex; justify-content: space-between; margin-top: 10px; font-size: 13px; color: #9aa0a6; }
.progress-actions { display: flex; gap: 10px; margin-top: 20px; justify-content: center; }
.upload-error { margin-top: 12px; padding: 10px 14px; background: #ef444418; border: 1px solid #ef444444; border-radius: 8px; color: #f87171; font-size: 13px; }

:deep(.el-upload-dragger) {
  background: #141c28 !important;
  border-color: #2a3544 !important;
}
:deep(.el-upload-dragger:hover) {
  border-color: #3b82f6 !important;
}
:deep(.el-upload__text) { color: #9aa0a6 !important; }
:deep(.el-upload__tip) { color: #6b7280 !important; }
</style>

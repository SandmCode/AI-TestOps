<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import '@vue-office/docx/lib/index.css'
import 'highlight.js/styles/github-dark.min.css'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getDocumentPreview,
  downloadDocument,
  previewDocumentFile,
  aiGenerateRequirements,
  createRequirement,
} from '@/api'
import {
  renderMarkdown,
  highlightCode,
  parseCsvRows,
  formatArchiveSize,
} from '@/utils/documentPreview'

const VueOfficeDocx = defineAsyncComponent(() => import('@vue-office/docx'))

interface ArchiveFile {
  name: string
  size: number
  compressed_size: number
  is_dir: boolean
}

interface PreviewData {
  id: number
  name: string
  version: string
  doc_type: string
  doc_type_display: string
  project: number
  project_name: string
  preview_mode: string
  file_url: string
  download_url: string
  file_ext: string
  original_name: string
  file_size: number
  content: string
  raw_content: string
  code_language: string
  content_note: string
  created_at: string
  converted_preview?: boolean
  archive?: {
    files: ArchiveFile[]
    total: number
    message?: string
  }
}

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const aiLoading = ref(false)
const docxLoading = ref(false)
const preview = ref<PreviewData | null>(null)
const viewTab = ref<'original' | 'source'>('original')
const docxSrc = ref<ArrayBuffer | string>('')

const docId = computed(() => Number(route.params.id))
const previewTitle = computed(() => preview.value?.name || '文档预览')
const previewFileSrc = computed(() => previewDocumentFile(docId.value))

const dualViewModes = new Set(['docx', 'office', 'markdown', 'code', 'csv'])
const dualViewWithPdf = (p: PreviewData) => p.preview_mode === 'pdf' && p.converted_preview

const hasDualView = computed(() => {
  const p = preview.value
  if (!p) return false
  return dualViewModes.has(p.preview_mode) || dualViewWithPdf(p)
})

const originalTabLabel = computed(() => {
  const mode = preview.value?.preview_mode
  if (mode === 'markdown') return '渲染预览'
  if (mode === 'code') return '格式化预览'
  if (mode === 'csv') return '表格预览'
  if (mode === 'archive') return '压缩包内容'
  return '原文件预览'
})

const sourceTabLabel = computed(() => {
  const mode = preview.value?.preview_mode
  if (mode === 'markdown') return 'Markdown 源码'
  if (mode === 'code') return '源代码'
  if (mode === 'csv') return 'CSV 源码'
  if (mode === 'docx' || mode === 'office') return '纯文本'
  return '源代码'
})

const renderedMarkdown = computed(() => renderMarkdown(preview.value?.raw_content || preview.value?.content || ''))

const highlightedCode = computed(() =>
  highlightCode(
    preview.value?.content || preview.value?.raw_content || '',
    preview.value?.code_language || 'plaintext',
  ),
)

const csvRows = computed(() => parseCsvRows(preview.value?.raw_content || preview.value?.content || ''))

const sourceText = computed(() => preview.value?.raw_content || preview.value?.content || '')

const officeTip = computed(() => {
  if (!preview.value) return ''
  if (preview.value.file_ext === 'doc' && preview.value.preview_mode === 'office') {
    return '旧版 .doc 需安装 LibreOffice 才能转为 PDF 预览；可切换到纯文本或下载原文件。'
  }
  if (preview.value.converted_preview) {
    return '已通过 LibreOffice 将 .doc 转为 PDF 预览，版式可能与原文件略有差异。'
  }
  if (preview.value.preview_mode === 'archive' && preview.value.archive?.message) {
    return preview.value.archive.message
  }
  return ''
})

async function loadPreview() {
  loading.value = true
  docxSrc.value = ''
  try {
    const res = await getDocumentPreview(docId.value)
    preview.value = res.data
    viewTab.value = 'original'
    if (res.data.preview_mode === 'docx') {
      await loadDocxSrc(previewFileSrc.value)
    }
  } catch {
    ElMessage.error('文档不存在或加载失败')
    router.push('/documents')
  } finally {
    loading.value = false
  }
}

async function loadDocxSrc(url: string) {
  docxLoading.value = true
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error('文件加载失败')
    docxSrc.value = await res.arrayBuffer()
  } catch {
    docxSrc.value = url
    ElMessage.warning('原文件加载较慢，正在尝试备用方式')
  } finally {
    docxLoading.value = false
  }
}

function onDocxRendered() {
  docxLoading.value = false
}

function onDocxError() {
  docxLoading.value = false
  ElMessage.error('Word 原文件渲染失败，可切换到纯文本或下载查看')
  viewTab.value = 'source'
}

function goBack() {
  router.push('/documents')
}

function handleDownload() {
  if (!preview.value?.download_url) {
    ElMessage.warning('没有可下载的文件')
    return
  }
  window.open(downloadDocument(docId.value), '_blank')
}

async function handleAiGenerate() {
  if (!preview.value) return
  aiLoading.value = true
  try {
    const res = await aiGenerateRequirements(docId.value)
    const requirements = res.data.requirements || []
    for (const req of requirements) {
      await createRequirement({
        project: preview.value.project,
        document: preview.value.id,
        module: req.module,
        name: req.name,
        description: req.description,
      })
    }
    ElMessage.success(`AI 已解析生成 ${requirements.length} 条功能需求`)
  } finally {
    aiLoading.value = false
  }
}

function formatSize(size: number) {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

watch(viewTab, (tab) => {
  if (tab === 'original' && preview.value?.preview_mode === 'docx' && !docxSrc.value) {
    loadDocxSrc(previewFileSrc.value)
  }
})

onMounted(loadPreview)
</script>

<template>
  <div v-loading="loading" class="preview-page">
    <div class="preview-header">
      <div class="header-left">
        <el-button @click="goBack"><el-icon><ArrowLeft /></el-icon> 返回列表</el-button>
        <div class="title-block">
          <h1>{{ previewTitle }}</h1>
          <p v-if="preview">
            {{ preview.project_name }} · {{ preview.doc_type_display }} · {{ preview.version || '无版本' }}
            · {{ preview.file_ext?.toUpperCase() }} · {{ formatSize(preview.file_size) }}
          </p>
        </div>
      </div>
      <div class="header-actions">
        <el-button @click="handleDownload"><el-icon><Download /></el-icon> 下载原文件</el-button>
        <el-button type="success" :loading="aiLoading" @click="handleAiGenerate">
          <el-icon><MagicStick /></el-icon> AI 解析生成需求
        </el-button>
      </div>
    </div>

    <div v-if="preview" class="preview-card">
      <div v-if="preview.content_note" class="note-box">
        <strong>补充说明：</strong>{{ preview.content_note }}
      </div>

      <div v-if="officeTip && viewTab === 'original'" class="tip-box">{{ officeTip }}</div>

      <el-tabs v-if="hasDualView" v-model="viewTab" class="preview-tabs">
        <el-tab-pane :label="originalTabLabel" name="original" />
        <el-tab-pane :label="sourceTabLabel" name="source" />
      </el-tabs>

      <!-- Word docx -->
      <div
        v-if="preview.preview_mode === 'docx' && viewTab === 'original'"
        v-loading="docxLoading"
        class="preview-office-wrap"
      >
        <VueOfficeDocx
          v-if="docxSrc"
          :src="docxSrc"
          class="office-docx"
          @rendered="onDocxRendered"
          @error="onDocxError"
        />
      </div>

      <!-- PDF -->
      <div v-else-if="preview.preview_mode === 'pdf' && viewTab === 'original'" class="preview-frame-wrap">
        <iframe :src="previewFileSrc" class="preview-frame" title="PDF 预览" />
      </div>

      <!-- 图片 / SVG -->
      <div v-else-if="preview.preview_mode === 'image'" class="preview-image-wrap">
        <img :src="previewFileSrc" :alt="preview.original_name" class="preview-image" />
      </div>

      <!-- Markdown 渲染 -->
      <div
        v-else-if="preview.preview_mode === 'markdown' && viewTab === 'original'"
        class="preview-markdown-wrap"
        v-html="renderedMarkdown"
      />

      <!-- 代码高亮 -->
      <div
        v-else-if="preview.preview_mode === 'code' && viewTab === 'original'"
        class="preview-code-wrap"
      >
        <pre class="preview-code"><code v-html="highlightedCode" /></pre>
      </div>

      <!-- CSV 表格 -->
      <div
        v-else-if="preview.preview_mode === 'csv' && viewTab === 'original'"
        class="preview-csv-wrap"
      >
        <el-table v-if="csvRows.length" :data="csvRows.slice(1)" border stripe max-height="calc(100vh - 280px)">
          <el-table-column
            v-for="(col, idx) in csvRows[0]"
            :key="idx"
            :prop="String(idx)"
            :label="col || `列${idx + 1}`"
            min-width="120"
            show-overflow-tooltip
          >
            <template #default="{ row }">{{ row[idx] }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="CSV 内容为空或无法解析" />
      </div>

      <!-- ZIP 压缩包 -->
      <div v-else-if="preview.preview_mode === 'archive'" class="preview-archive-wrap">
        <div class="archive-summary">共 {{ preview.archive?.total || 0 }} 个条目</div>
        <el-table
          v-if="preview.archive?.files?.length"
          :data="preview.archive.files"
          border
          stripe
          max-height="calc(100vh - 280px)"
        >
          <el-table-column prop="name" label="文件路径" min-width="280" show-overflow-tooltip />
          <el-table-column label="类型" width="80">
            <template #default="{ row }">{{ row.is_dir ? '目录' : '文件' }}</template>
          </el-table-column>
          <el-table-column label="原始大小" width="120">
            <template #default="{ row }">{{ formatArchiveSize(row.size) }}</template>
          </el-table-column>
          <el-table-column label="压缩后" width="120">
            <template #default="{ row }">{{ row.is_dir ? '-' : formatArchiveSize(row.compressed_size) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="压缩包为空或无法读取" />
      </div>

      <!-- 纯文本 / 源码 -->
      <div
        v-else-if="viewTab === 'source' || preview.preview_mode === 'text'"
        class="preview-text-wrap"
      >
        <pre class="preview-text">{{ sourceText || '暂无文本内容' }}</pre>
      </div>

      <!-- Office 无法原文件预览 -->
      <div v-else-if="preview.preview_mode === 'office' && viewTab === 'original'" class="preview-fallback">
        <el-empty description="旧版 .doc 无法直接原文件预览">
          <p class="fallback-tip">请安装 LibreOffice 后刷新页面（自动转 PDF 预览），或切换到「纯文本」/ 下载原文件。</p>
          <el-button type="primary" @click="handleDownload">下载原文件</el-button>
        </el-empty>
      </div>

      <!-- 不支持在线预览 -->
      <div v-else class="preview-fallback">
        <el-empty :description="`「${preview.file_ext?.toUpperCase()}」格式暂不支持在线原文件预览`">
          <p class="fallback-tip">支持 PDF、图片、Word、Markdown、JSON/YAML/XML、CSV、TXT、ZIP 等格式在线预览。</p>
          <el-button type="primary" @click="handleDownload">下载原文件查看</el-button>
        </el-empty>
      </div>
    </div>
  </div>
</template>

<style scoped>
.preview-page { min-height: calc(100vh - 48px); }
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.header-left { display: flex; align-items: flex-start; gap: 16px; }
.title-block h1 { color: #fff; font-size: 22px; margin-bottom: 6px; }
.title-block p { color: #6b7280; font-size: 13px; }
.header-actions { display: flex; gap: 10px; flex-shrink: 0; }
.preview-card {
  background: #1a2332;
  border: 1px solid #2a3544;
  border-radius: 12px;
  padding: 20px;
  min-height: 500px;
}
.note-box, .tip-box {
  background: #141c28;
  border: 1px solid #2a3544;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
  color: #9aa0a6;
  font-size: 14px;
}
.tip-box { border-color: #f59e0b44; color: #fbbf24; }
.preview-tabs { margin-bottom: 12px; }
.preview-frame-wrap { height: calc(100vh - 260px); min-height: 600px; }
.preview-frame { width: 100%; height: 100%; border: none; border-radius: 8px; background: #fff; }
.preview-office-wrap {
  height: calc(100vh - 260px);
  min-height: 600px;
  overflow: auto;
  background: #fff;
  border-radius: 8px;
}
.office-docx { width: 100%; min-height: 100%; }
.preview-image-wrap { text-align: center; padding: 20px; }
.preview-image { max-width: 100%; max-height: calc(100vh - 240px); border-radius: 8px; }
.preview-text-wrap,
.preview-code-wrap,
.preview-markdown-wrap,
.preview-csv-wrap,
.preview-archive-wrap {
  max-height: calc(100vh - 260px);
  overflow: auto;
}
.preview-text,
.preview-code {
  background: #141c28;
  border: 1px solid #2a3544;
  border-radius: 8px;
  padding: 20px;
  color: #e8eaed;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}
.preview-code { padding: 0; overflow: auto; }
.preview-code code { display: block; padding: 20px; font-family: Consolas, Monaco, monospace; font-size: 13px; line-height: 1.6; }
.preview-markdown-wrap {
  background: #fff;
  color: #1f2937;
  border-radius: 8px;
  padding: 28px 36px;
  line-height: 1.75;
  font-size: 15px;
}
.preview-markdown-wrap :deep(h1),
.preview-markdown-wrap :deep(h2),
.preview-markdown-wrap :deep(h3) { margin: 1.2em 0 0.6em; font-weight: 700; }
.preview-markdown-wrap :deep(p) { margin: 0.8em 0; }
.preview-markdown-wrap :deep(ul),
.preview-markdown-wrap :deep(ol) { padding-left: 1.5em; margin: 0.8em 0; }
.preview-markdown-wrap :deep(code) {
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: Consolas, Monaco, monospace;
  font-size: 0.9em;
}
.preview-markdown-wrap :deep(pre) {
  background: #111827;
  color: #f9fafb;
  padding: 16px;
  border-radius: 8px;
  overflow: auto;
}
.preview-markdown-wrap :deep(pre code) { background: transparent; padding: 0; color: inherit; }
.preview-markdown-wrap :deep(table) { border-collapse: collapse; width: 100%; margin: 1em 0; }
.preview-markdown-wrap :deep(th),
.preview-markdown-wrap :deep(td) { border: 1px solid #d1d5db; padding: 8px 12px; }
.preview-markdown-wrap :deep(blockquote) {
  border-left: 4px solid #3b82f6;
  margin: 1em 0;
  padding: 0.5em 1em;
  color: #4b5563;
  background: #f9fafb;
}
.archive-summary { color: #9aa0a6; font-size: 13px; margin-bottom: 12px; }
.preview-fallback { padding: 60px 0; }
.fallback-tip { color: #6b7280; font-size: 13px; margin: 8px 0 16px; max-width: 480px; line-height: 1.6; }
</style>

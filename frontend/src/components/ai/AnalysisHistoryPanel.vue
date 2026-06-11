<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteAnalysisRecord,
  downloadAnalysisRecordPath,
  getAnalysisRecords,
  getAnalysisRecord,
} from '@/api'
import { downloadFromApi } from '@/utils/downloadFile'
import type { AnalysisType } from '@/composables/useAnalysisSession'

interface RecordItem {
  id: number
  analysis_type: AnalysisType
  title: string
  summary: string
  input_preview: string
  created_at: string
  analysis_type_display: string
}

const props = defineProps<{
  analysisType: AnalysisType
  activeRecordId?: number | null
}>()

const emit = defineEmits<{
  load: [payload: { input: string; result: Record<string, unknown> }]
}>()

const records = ref<RecordItem[]>([])
const loading = ref(false)
const downloadingId = ref<number | null>(null)
const expanded = ref(true)

async function fetchRecords() {
  loading.value = true
  try {
    const res = await getAnalysisRecords({ analysis_type: props.analysisType, page_size: 50 })
    records.value = res.data.results ?? res.data ?? []
  } finally {
    loading.value = false
  }
}

async function loadRecord(item: RecordItem) {
  const res = await getAnalysisRecord(item.id)
  const data = res.data
  emit('load', {
    input: data.input_content || '',
    result: data.result || {},
  })
  ElMessage.success('已加载历史记录')
}

async function downloadRecord(item: RecordItem, format: 'json' | 'md') {
  downloadingId.value = item.id
  try {
    const ext = format === 'md' ? 'md' : 'json'
    await downloadFromApi(
      downloadAnalysisRecordPath(item.id, format),
      `analysis-${item.id}-${item.analysis_type}.${ext}`,
    )
  } finally {
    downloadingId.value = null
  }
}

async function removeRecord(item: RecordItem) {
  try {
    await ElMessageBox.confirm(`确定删除记录「${item.title}」？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteAnalysisRecord(item.id)
    records.value = records.value.filter((r) => r.id !== item.id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败，请稍后重试')
  }
}

function formatTime(iso: string) {
  if (!iso) return ''
  return iso.replace('T', ' ').slice(0, 19)
}

onMounted(fetchRecords)
watch(() => props.analysisType, fetchRecords)

defineExpose({ refresh: fetchRecords })
</script>

<template>
  <div class="history-panel">
    <div class="history-head" @click="expanded = !expanded">
      <div class="history-title">
        <el-icon><Clock /></el-icon>
        分析记录
        <el-tag size="small" round effect="plain">{{ records.length }}</el-tag>
      </div>
      <div class="history-actions" @click.stop>
        <el-button link type="primary" size="small" :loading="loading" @click="fetchRecords">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <el-icon class="chevron" :class="{ open: expanded }"><ArrowDown /></el-icon>
      </div>
    </div>

    <div v-show="expanded" class="history-body">
      <div v-if="loading && !records.length" class="history-empty">加载中...</div>
      <div v-else-if="!records.length" class="history-empty">暂无分析记录，完成分析后将自动保存</div>
      <div v-else class="history-list">
        <div
          v-for="item in records"
          :key="item.id"
          class="history-item"
          :class="{ active: activeRecordId === item.id }"
        >
          <div class="item-main" @click="loadRecord(item)">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-summary">{{ item.summary || item.input_preview }}</div>
            <div class="item-time">{{ formatTime(item.created_at) }}</div>
          </div>
          <div class="item-btns">
            <el-tooltip content="加载到编辑器">
              <el-button circle size="small" @click="loadRecord(item)">
                <el-icon><FolderOpened /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="下载 JSON">
              <el-button
                circle
                size="small"
                :loading="downloadingId === item.id"
                @click="downloadRecord(item, 'json')"
              >
                <el-icon><Download /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="下载 Markdown">
              <el-button
                circle
                size="small"
                :loading="downloadingId === item.id"
                @click="downloadRecord(item, 'md')"
              >
                <el-icon><Document /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="删除">
              <el-button circle size="small" type="danger" plain @click="removeRecord(item)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-panel {
  background: #1a2332;
  border: 1px solid #2a3544;
  border-radius: 14px;
  overflow: hidden;
  margin-top: 16px;
}
.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  cursor: pointer;
  background: #141c28;
  border-bottom: 1px solid #2a354433;
}
.history-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #e8eaed;
}
.history-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.chevron { transition: transform 0.2s; color: #6b7280; }
.chevron.open { transform: rotate(180deg); }
.history-body { max-height: 360px; overflow-y: auto; }
.history-empty {
  padding: 28px;
  text-align: center;
  color: #6b7280;
  font-size: 13px;
}
.history-list { display: flex; flex-direction: column; }
.history-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #2a354433;
  transition: background 0.15s;
}
.history-item:hover { background: #243044; }
.history-item.active { background: #1e3a5f44; border-left: 3px solid #3b82f6; }
.item-main { flex: 1; min-width: 0; cursor: pointer; }
.item-title {
  font-size: 13px;
  font-weight: 600;
  color: #f3f4f6;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item-summary {
  font-size: 12px;
  color: #9aa0a6;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item-time { font-size: 11px; color: #6b7280; margin-top: 4px; }
.item-btns {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
</style>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import AiWorkbench from '@/components/ai/AiWorkbench.vue'
import AnalysisHistoryPanel from '@/components/ai/AnalysisHistoryPanel.vue'
import { useAnalysisSession } from '@/composables/useAnalysisSession'
import { logAnalysis } from '@/api'
import { copyText } from '@/utils/clipboard'
import type { LogResult } from '@/utils/aiAnalysis'

const SAMPLE = `2026-03-09 10:23:01 ERROR ConnectionTimeout: Redis connection failed after 5000ms
2026-03-09 10:23:05 WARN  Retry attempt 1/3 for celery task
2026-03-09 10:24:12 ERROR ValidationError: email field is required
2026-03-09 10:24:15 ERROR ValidationError: phone format invalid
2026-03-09 10:25:00 INFO  Test execution completed: 45/50 passed
2026-03-09 10:25:01 WARN  Slow query detected: 3200ms on orders table`

const logs = ref(SAMPLE)
const result = ref<LogResult | null>(null)
const loading = ref(false)
const chartRef = ref<HTMLElement | null>(null)
const pieRef = ref<HTMLElement | null>(null)
const historyRef = ref<InstanceType<typeof AnalysisHistoryPanel> | null>(null)
let barChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null

const activeRecordId = computed(() => result.value?.record_id ?? null)
const { clearSession } = useAnalysisSession('log', logs, result)

const healthLevel = computed(() => {
  if (!result.value) return { label: '', type: 'info' as const }
  if (result.value.error_count > 0) return { label: '需排查', type: 'danger' as const }
  if (result.value.warning_count > 0) return { label: '有警告', type: 'warning' as const }
  return { label: '正常', type: 'success' as const }
})

async function run() {
  if (!logs.value.trim()) {
    ElMessage.warning('请粘贴日志内容')
    return
  }
  loading.value = true
  try {
    const res = await logAnalysis(logs.value)
    result.value = res.data as LogResult
    historyRef.value?.refresh()
    await nextTick()
    renderCharts()
    ElMessage.success('日志分析完成，已保存记录')
  } finally {
    loading.value = false
  }
}

function loadSample() {
  logs.value = SAMPLE
  result.value = null
}

function clearInput() {
  logs.value = ''
  clearSession()
}

function loadFromHistory(payload: { input: string; result: Record<string, unknown> }) {
  logs.value = payload.input
  result.value = payload.result as LogResult
  nextTick(renderCharts)
}

function filterErrors() {
  const lines = logs.value.split('\n').filter((l) => /error/i.test(l))
  if (!lines.length) {
    ElMessage.info('未找到 ERROR 行')
    return
  }
  logs.value = lines.join('\n')
  ElMessage.success(`已筛选 ${lines.length} 条 ERROR 日志`)
}

function renderCharts() {
  if (!result.value) return
  const patterns = result.value.patterns || []

  if (pieRef.value) {
    if (!pieChart) pieChart = echarts.init(pieRef.value)
    pieChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, textStyle: { color: '#9aa0a6', fontSize: 11 } },
      series: [{
        type: 'pie',
        radius: ['42%', '68%'],
        label: { color: '#e8eaed', fontSize: 11 },
        data: [
          { name: '错误', value: result.value.error_count, itemStyle: { color: '#ef4444' } },
          { name: '警告', value: result.value.warning_count, itemStyle: { color: '#f59e0b' } },
          { name: '信息', value: result.value.info_count ?? 0, itemStyle: { color: '#60a5fa' } },
        ].filter((d) => d.value > 0),
      }],
    })
  }

  if (chartRef.value && patterns.length) {
    if (!barChart) barChart = echarts.init(chartRef.value)
    barChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 44, right: 12, top: 16, bottom: patterns.length > 2 ? 56 : 32 },
      xAxis: {
        type: 'category',
        data: patterns.map((p) => p.pattern),
        axisLabel: { color: '#9aa0a6', rotate: patterns.length > 2 ? 18 : 0, fontSize: 11 },
        axisLine: { lineStyle: { color: '#2a3544' } },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: '#9aa0a6' },
        splitLine: { lineStyle: { color: '#2a354433' } },
      },
      series: [{
        type: 'bar',
        data: patterns.map((p) => p.count),
        itemStyle: { color: '#ef4444', borderRadius: [5, 5, 0, 0] },
        label: { show: true, position: 'top', color: '#e8eaed' },
      }],
    })
  }
}

watch(result, () => nextTick(renderCharts))
onUnmounted(() => {
  barChart?.dispose()
  pieChart?.dispose()
})
</script>

<template>
  <AiWorkbench
    theme="log"
    icon="Memo"
    title="日志分析"
    desc="统计 ERROR/WARN 数量，识别错误模式，提供可复制的排查建议"
    editor-label="测试 / 系统日志"
    :has-result="!!result"
  >
    <template #hero-extra>
      <el-tag v-if="result" :type="healthLevel.type" size="large" effect="dark" round>
        {{ healthLevel.label }}
      </el-tag>
    </template>

    <template #tools>
      <el-button size="small" round @click="loadSample">加载示例</el-button>
      <el-button size="small" round @click="filterErrors">仅保留 ERROR</el-button>
      <el-button size="small" round @click="clearInput">清空</el-button>
    </template>

    <template #input>
      <el-input v-model="logs" type="textarea" :rows="14" placeholder="粘贴测试或系统运行日志，每行一条记录..." />
    </template>

    <template #actions>
      <el-button type="primary" :loading="loading" @click="run">
        <el-icon><Search /></el-icon> 开始分析
      </el-button>
      <el-button v-if="result" plain :loading="loading" @click="run">
        <el-icon><Refresh /></el-icon> 重新分析
      </el-button>
      <el-button v-if="result?.summary" plain @click="copyText(result.summary, '分析摘要')">
        <el-icon><DocumentCopy /></el-icon> 复制摘要
      </el-button>
    </template>

    <template #results>
      <div class="ai-result-banner" :class="healthLevel.type === 'success' ? 'ok' : healthLevel.type === 'danger' ? 'warn' : 'info'">
        <el-icon :size="30" color="#c4b5fd"><Document /></el-icon>
        <div class="ai-result-banner-text">
          <div class="ai-result-banner-title">{{ result?.summary }}</div>
          <div v-if="result?.line_count" class="ai-result-banner-meta">共分析 {{ result.line_count }} 行日志</div>
        </div>
      </div>

      <div class="ai-stat-grid">
        <div class="ai-stat-card error">
          <span class="num">{{ result?.error_count }}</span><span class="lbl">错误 ERROR</span>
        </div>
        <div class="ai-stat-card warn">
          <span class="num">{{ result?.warning_count }}</span><span class="lbl">警告 WARN</span>
        </div>
        <div class="ai-stat-card info">
          <span class="num">{{ result?.info_count ?? 0 }}</span><span class="lbl">信息 INFO</span>
        </div>
        <div class="ai-stat-card ok">
          <span class="num">{{ result?.patterns?.length ?? 0 }}</span><span class="lbl">错误模式</span>
        </div>
      </div>

      <div class="ai-result-grid">
        <div class="ai-panel">
          <div class="ai-panel-head"><span class="ai-panel-title">日志级别分布</span></div>
          <div ref="pieRef" class="ai-chart-box" style="height:220px" />
        </div>

        <div class="ai-panel">
          <div class="ai-panel-head"><span class="ai-panel-title">错误模式统计</span></div>
          <div v-if="result?.patterns?.length" ref="chartRef" class="ai-chart-box" />
          <div v-else class="ai-empty" style="padding:40px;border:none;background:transparent">
            <p>未发现典型错误模式</p>
          </div>
        </div>
      </div>

      <div class="ai-panel">
        <div class="ai-panel-head">
          <span class="ai-panel-title">模式诊断与排查建议</span>
        </div>
        <div v-if="result?.patterns?.length" class="ai-suggest-list">
          <div v-for="(p, i) in result.patterns" :key="p.pattern" class="ai-suggest-item">
            <span class="ai-suggest-index">{{ i + 1 }}</span>
            <div class="pattern-body">
              <div class="pattern-head">
                <strong>{{ p.pattern }}</strong>
                <el-tag type="danger" size="small" round>× {{ p.count }}</el-tag>
              </div>
              <p class="pattern-suggestion">{{ p.suggestion }}</p>
            </div>
            <div class="suggest-actions">
              <el-button size="small" @click="copyText(p.suggestion, '排查建议')">
                <el-icon><DocumentCopy /></el-icon> 复制建议
              </el-button>
              <el-button size="small" plain @click="copyText(p.pattern, '错误模式')">
                复制模式
              </el-button>
            </div>
          </div>
        </div>
        <div v-else class="ai-empty" style="padding:32px;border:none;background:#141c28">
          <el-icon :size="36" color="#10b981"><CircleCheck /></el-icon>
          <p>未发现需要特别关注的错误模式</p>
        </div>
      </div>
    </template>

    <template #empty>
      <el-icon :size="48" color="#8b5cf6"><Memo /></el-icon>
      <p>粘贴日志后点击「开始分析」</p>
      <p class="hint">支持本地规则快速统计；每条诊断建议均可一键复制，便于写入缺陷单或排查文档</p>
    </template>
  </AiWorkbench>

  <AnalysisHistoryPanel
    ref="historyRef"
    analysis-type="log"
    :active-record-id="activeRecordId"
    @load="loadFromHistory"
  />
</template>

<style scoped>
@import '@/styles/ai-analysis.css';

.pattern-body { flex: 1; min-width: 0; }
.pattern-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.pattern-head strong { color: #e8eaed; font-size: 14px; }
.pattern-suggestion {
  margin: 0;
  font-size: 13px;
  color: #9aa0a6;
  line-height: 1.6;
}
.suggest-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}
</style>

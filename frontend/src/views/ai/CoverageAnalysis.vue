<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import AiWorkbench from '@/components/ai/AiWorkbench.vue'
import AnalysisHistoryPanel from '@/components/ai/AnalysisHistoryPanel.vue'
import { useAnalysisSession } from '@/composables/useAnalysisSession'
import { coverageAnalysis } from '@/api'
import { copyText } from '@/utils/clipboard'
import type { CoverageResult } from '@/utils/aiAnalysis'

const SAMPLE = `def create_order(user_id, items, coupon_code=None):
    if not items:
        raise ValueError("items required")
    total = sum(i["price"] * i["qty"] for i in items)
    if coupon_code:
        total = apply_coupon(total, coupon_code)
    if total <= 0:
        raise ValueError("invalid total")
    return save_order(user_id, items, total)

# 已有用例：
# - test_create_order_success
# - test_empty_items_raises
# 缺少：优惠券分支、total<=0 边界、save_order 异常`

const content = ref(SAMPLE)
const result = ref<CoverageResult | null>(null)
const loading = ref(false)
const chartRef = ref<HTMLElement | null>(null)
const gaugeRef = ref<HTMLElement | null>(null)
const historyRef = ref<InstanceType<typeof AnalysisHistoryPanel> | null>(null)
let barChart: echarts.ECharts | null = null
let gaugeChart: echarts.ECharts | null = null

const activeRecordId = computed(() => result.value?.record_id ?? null)
const { clearSession } = useAnalysisSession('coverage', content, result)

const avgCoverage = computed(() => {
  if (!result.value) return 0
  return Math.round((result.value.line_coverage + result.value.branch_coverage) / 2)
})

const coverageLevel = computed(() => {
  const avg = avgCoverage.value
  if (avg >= 80) return { label: '良好', type: 'success' as const }
  if (avg >= 60) return { label: '一般', type: 'warning' as const }
  return { label: '偏低', type: 'danger' as const }
})

async function run() {
  if (!content.value.trim()) {
    ElMessage.warning('请粘贴代码或用例内容')
    return
  }
  loading.value = true
  try {
    const res = await coverageAnalysis(content.value)
    result.value = res.data as CoverageResult
    historyRef.value?.refresh()
    await nextTick()
    renderCharts()
    ElMessage.success('覆盖率分析完成，已保存记录')
  } finally {
    loading.value = false
  }
}

function appendSuggestion(text: string) {
  content.value = `${content.value.trim()}\n\n# 待补充用例：${text}`
  ElMessage.success('已追加到输入区底部')
}

function clearInput() {
  content.value = ''
  clearSession()
}

function loadFromHistory(payload: { input: string; result: Record<string, unknown> }) {
  content.value = payload.input
  result.value = payload.result as CoverageResult
  nextTick(renderCharts)
}

function loadSample() {
  content.value = SAMPLE
  result.value = null
}

function renderCharts() {
  if (!result.value) return
  const line = result.value.line_coverage
  const branch = result.value.branch_coverage

  if (gaugeRef.value) {
    if (!gaugeChart) gaugeChart = echarts.init(gaugeRef.value)
    gaugeChart.setOption({
      backgroundColor: 'transparent',
      series: [{
        type: 'gauge',
        startAngle: 200,
        endAngle: -20,
        min: 0,
        max: 100,
        splitNumber: 5,
        itemStyle: { color: '#3b82f6' },
        progress: { show: true, width: 14 },
        pointer: { show: false },
        axisLine: { lineStyle: { width: 14, color: [[1, '#2a3544']] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { color: '#6b7280', fontSize: 10 },
        detail: {
          valueAnimation: true,
          formatter: '{value}%',
          color: '#fff',
          fontSize: 28,
          offsetCenter: [0, '10%'],
        },
        data: [{ value: avgCoverage.value, name: '综合覆盖' }],
        title: { color: '#9aa0a6', fontSize: 12, offsetCenter: [0, '72%'] },
      }],
    })
  }

  if (chartRef.value) {
    if (!barChart) barChart = echarts.init(chartRef.value)
    barChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 44, right: 16, top: 20, bottom: 28 },
      xAxis: {
        type: 'category',
        data: ['行覆盖', '分支覆盖', '综合'],
        axisLabel: { color: '#9aa0a6' },
        axisLine: { lineStyle: { color: '#2a3544' } },
      },
      yAxis: {
        type: 'value',
        max: 100,
        axisLabel: { color: '#9aa0a6', formatter: '{value}%' },
        splitLine: { lineStyle: { color: '#2a354433' } },
      },
      series: [{
        type: 'bar',
        barWidth: 40,
        data: [
          { value: line, itemStyle: { color: '#3b82f6', borderRadius: [6, 6, 0, 0] } },
          { value: branch, itemStyle: { color: '#f59e0b', borderRadius: [6, 6, 0, 0] } },
          { value: avgCoverage.value, itemStyle: { color: '#10b981', borderRadius: [6, 6, 0, 0] } },
        ],
        label: { show: true, position: 'top', color: '#e8eaed', formatter: '{c}%' },
      }],
    })
  }
}

watch(result, () => nextTick(renderCharts))
onUnmounted(() => {
  barChart?.dispose()
  gaugeChart?.dispose()
})
</script>

<template>
  <AiWorkbench
    theme="coverage"
    icon="PieChart"
    title="覆盖率分析"
    desc="分析源码与已有用例，评估行/分支覆盖率并生成可执行的补充测试建议"
    editor-label="源代码 / 用例清单"
    :has-result="!!result"
  >
    <template #hero-extra>
      <el-tag v-if="result" :type="coverageLevel.type" size="large" effect="dark" round>
        综合 {{ avgCoverage }}% · {{ coverageLevel.label }}
      </el-tag>
    </template>

    <template #tools>
      <el-button size="small" round @click="loadSample">加载示例</el-button>
      <el-button size="small" round @click="clearInput">清空</el-button>
    </template>

    <template #input>
      <el-input
        v-model="content"
        type="textarea"
        :rows="14"
        placeholder="粘贴源代码、测试用例列表或覆盖率报告..."
      />
    </template>

    <template #actions>
      <el-button type="primary" :loading="loading" @click="run">
        <el-icon><DataAnalysis /></el-icon> 开始分析
      </el-button>
      <el-button v-if="result" plain :loading="loading" @click="run">
        <el-icon><Refresh /></el-icon> 重新分析
      </el-button>
    </template>

    <template #results>
      <div class="ai-result-banner info">
        <el-icon :size="30" color="#34d399"><DataLine /></el-icon>
        <div class="ai-result-banner-text">
          <div class="ai-result-banner-title">{{ result?.summary }}</div>
        </div>
      </div>

      <div class="ai-stat-grid">
        <div class="ai-stat-card info">
          <span class="num">{{ result?.line_coverage }}%</span>
          <span class="lbl">行覆盖率</span>
        </div>
        <div class="ai-stat-card warn">
          <span class="num">{{ result?.branch_coverage }}%</span>
          <span class="lbl">分支覆盖率</span>
        </div>
        <div class="ai-stat-card ok">
          <span class="num">{{ avgCoverage }}%</span>
          <span class="lbl">综合评估</span>
        </div>
        <div class="ai-stat-card error">
          <span class="num">{{ result?.uncovered?.length ?? 0 }}</span>
          <span class="lbl">未覆盖项</span>
        </div>
      </div>

      <div class="ai-result-grid">
        <div class="ai-panel">
          <div class="ai-panel-head"><span class="ai-panel-title">综合仪表盘</span></div>
          <div ref="gaugeRef" class="ai-chart-box" style="height:200px" />
          <div style="margin-top:8px">
            <div style="display:flex;justify-content:space-between;font-size:12px;color:#9aa0a6;margin-bottom:6px">
              <span>行覆盖</span><span>{{ result?.line_coverage }}%</span>
            </div>
            <el-progress :percentage="result?.line_coverage ?? 0" :stroke-width="8" :show-text="false" />
            <div style="display:flex;justify-content:space-between;font-size:12px;color:#9aa0a6;margin:10px 0 6px">
              <span>分支覆盖</span><span>{{ result?.branch_coverage }}%</span>
            </div>
            <el-progress :percentage="result?.branch_coverage ?? 0" :stroke-width="8" status="warning" :show-text="false" />
          </div>
        </div>

        <div class="ai-panel">
          <div class="ai-panel-head"><span class="ai-panel-title">覆盖率对比</span></div>
          <div ref="chartRef" class="ai-chart-box" />
        </div>
      </div>

      <div v-if="result?.uncovered?.length" class="ai-panel">
        <div class="ai-panel-head"><span class="ai-panel-title">未覆盖区域</span></div>
        <div class="tag-cloud">
          <el-tag
            v-for="u in result.uncovered"
            :key="u"
            type="info"
            effect="plain"
            round
            class="tag-item"
          >
            {{ u }}
            <el-button link type="primary" size="small" @click="copyText(u, '未覆盖项')">复制</el-button>
          </el-tag>
        </div>
      </div>

      <div v-if="result?.suggestions?.length" class="ai-panel">
        <div class="ai-panel-head"><span class="ai-panel-title">改进建议</span></div>
        <div class="ai-suggest-list">
          <div v-for="(s, i) in result.suggestions" :key="i" class="ai-suggest-item">
            <span class="ai-suggest-index">{{ i + 1 }}</span>
            <div class="ai-suggest-body">{{ s }}</div>
            <div class="suggest-actions">
              <el-button size="small" @click="copyText(s, '建议')">
                <el-icon><DocumentCopy /></el-icon> 复制
              </el-button>
              <el-button size="small" type="primary" plain @click="appendSuggestion(s)">
                <el-icon><Plus /></el-icon> 追加到输入
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template #empty>
      <el-icon :size="48" color="#10b981"><PieChart /></el-icon>
      <p>粘贴代码与用例清单后点击「开始分析」</p>
      <p class="hint">建议同时提供源码和已有测试用例；分析后可复制建议或一键追加到输入区</p>
    </template>
  </AiWorkbench>

  <AnalysisHistoryPanel
    ref="historyRef"
    analysis-type="coverage"
    :active-record-id="activeRecordId"
    @load="loadFromHistory"
  />
</template>

<style scoped>
@import '@/styles/ai-analysis.css';

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.tag-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  height: auto;
}
.suggest-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}
</style>

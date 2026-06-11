<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import AiWorkbench from '@/components/ai/AiWorkbench.vue'
import AnalysisHistoryPanel from '@/components/ai/AnalysisHistoryPanel.vue'
import { useAnalysisSession } from '@/composables/useAnalysisSession'
import { contractTest, contractTestFix } from '@/api'
import { copyText } from '@/utils/clipboard'
import {
  severityLabel,
  severityTagType,
  type ContractResult,
  type Violation,
} from '@/utils/aiAnalysis'

const SAMPLE_INCOMPLETE = `{
  "openapi": "3.0.0",
  "paths": {
    "/api/users": {
      "get": {
        "summary": "获取用户列表",
        "responses": {
          "200": {
            "description": "成功",
            "content": {
              "application/json": {
                "schema": {
                  "type": "array",
                  "items": { "type": "object", "properties": { "id": { "type": "integer" }, "name": { "type": "string" } } }
                }
              }
            }
          }
        }
      }
    }
  }
}`

const SAMPLE_VALID = `{
  "openapi": "3.0.0",
  "info": { "title": "用户服务 API", "version": "1.0.0", "description": "用户管理相关接口" },
  "servers": [{ "url": "http://127.0.0.1:9000/v1" }],
  "paths": {
    "/api/users": {
      "get": {
        "summary": "获取用户列表",
        "responses": {
          "200": {
            "description": "成功",
            "content": {
              "application/json": {
                "schema": {
                  "type": "array",
                  "items": { "type": "object", "properties": { "id": { "type": "integer" }, "name": { "type": "string" } } }
                }
              }
            }
          }
        }
      }
    }
  }
}`

const apiSpec = ref(SAMPLE_INCOMPLETE)
const result = ref<ContractResult | null>(null)
const loading = ref(false)
const fixing = ref(false)
const fixingId = ref<string | null>(null)
const appliedLabels = ref<string[]>([])
const previewOpen = ref(false)
const expandedFix = ref<Set<string>>(new Set())
const chartRef = ref<HTMLElement | null>(null)
const historyRef = ref<InstanceType<typeof AnalysisHistoryPanel> | null>(null)
const sessionExtra = ref<{ appliedLabels?: string[] }>({})
let chart: echarts.ECharts | null = null

const activeRecordId = computed(() => result.value?.record_id ?? null)

const { clearSession } = useAnalysisSession('contract', apiSpec, result, sessionExtra)

watch(sessionExtra, (v) => {
  if (v?.appliedLabels?.length) appliedLabels.value = v.appliedLabels
}, { immediate: true, deep: true })

const stats = computed(() => result.value?.stats ?? { error: 0, warning: 0, info: 0 })
const passed = computed(() => result.value?.passed ?? (result.value?.violations?.length === 0))
const fixableCount = computed(() => result.value?.fixable_count ?? 0)
const hasFixedPreview = computed(() => Boolean(result.value?.fixed_spec && fixableCount.value > 0))

async function run() {
  loading.value = true
  appliedLabels.value = []
  try {
    const res = await contractTest(apiSpec.value)
    result.value = res.data as ContractResult
    sessionExtra.value = { appliedLabels: appliedLabels.value }
    historyRef.value?.refresh()
    await nextTick()
    renderChart()
    ElMessage.success(passed.value ? '契约检查通过' : '契约检查完成，已保存记录')
  } finally {
    loading.value = false
  }
}

async function doFix(fixIds?: string[], label = '修复') {
  const count = fixIds?.length ?? fixableCount.value
  if (!count) return

  if (!fixIds) {
    try {
      await ElMessageBox.confirm(
        `将自动修复 ${fixableCount.value} 项问题并更新规范内容，是否继续？`,
        '一键修复',
        { confirmButtonText: '确认修复', cancelButtonText: '取消', type: 'info' },
      )
    } catch {
      return
    }
  }

  fixing.value = true
  if (fixIds?.length === 1) fixingId.value = fixIds[0]
  try {
    const res = await contractTestFix(apiSpec.value, fixIds)
    const data = res.data
    if (!data.applied_labels?.length) {
      ElMessage.warning('该项当前无法自动修复，请参考修复建议手动修改')
      return
    }
    apiSpec.value = data.fixed_spec
    appliedLabels.value = [...appliedLabels.value, ...data.applied_labels]
    result.value = data.validation as ContractResult
    if (data.validation?.fix_summary) {
      result.value.fix_summary = data.validation.fix_summary
    }
    sessionExtra.value = { appliedLabels: appliedLabels.value }
    historyRef.value?.refresh()
    await nextTick()
    renderChart()
    ElMessage.success(`${label}完成，已保存记录`)
  } finally {
    fixing.value = false
    fixingId.value = null
  }
}

function applyPreview() {
  if (!result.value?.fixed_spec) return
  apiSpec.value = result.value.fixed_spec
  previewOpen.value = false
  ElMessage.info('已应用到编辑器，建议重新检查确认')
}

function loadSample(type: 'incomplete' | 'valid') {
  apiSpec.value = type === 'valid' ? SAMPLE_VALID : SAMPLE_INCOMPLETE
  result.value = null
  appliedLabels.value = []
}

function clearInput() {
  apiSpec.value = ''
  appliedLabels.value = []
  clearSession()
}

function loadFromHistory(payload: { input: string; result: Record<string, unknown> }) {
  apiSpec.value = payload.input
  result.value = payload.result as ContractResult
  appliedLabels.value = []
  nextTick(renderChart)
}

function formatJson() {
  try {
    apiSpec.value = JSON.stringify(JSON.parse(apiSpec.value), null, 2)
    ElMessage.success('格式化完成')
  } catch {
    ElMessage.error('JSON 格式无效，无法格式化')
  }
}

function toggleSnippet(row: Violation) {
  const key = row.fix_id || row.field
  const next = new Set(expandedFix.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedFix.value = next
}

function isExpanded(row: Violation) {
  return expandedFix.value.has(row.fix_id || row.field)
}

function renderChart() {
  if (!chartRef.value || !result.value?.violations?.length) return
  if (!chart) chart = echarts.init(chartRef.value)
  const s = stats.value
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['50%', '72%'],
      label: { color: '#e8eaed', fontSize: 11 },
      data: [
        { name: '错误', value: s.error, itemStyle: { color: '#ef4444' } },
        { name: '警告', value: s.warning, itemStyle: { color: '#f59e0b' } },
        { name: '提示', value: s.info, itemStyle: { color: '#3b82f6' } },
      ].filter((d) => d.value > 0),
    }],
  })
}

watch(result, () => nextTick(renderChart))
onUnmounted(() => { chart?.dispose(); chart = null })
</script>

<template>
  <AiWorkbench
    theme="contract"
    icon="Tickets"
    title="契约测试"
    desc="检查 OpenAPI 规范完整性，提供修复建议与一键/单项自动修复"
    editor-label="OpenAPI / Swagger 规范"
    :has-result="!!result"
  >
    <template #hero-extra>
      <el-tag v-if="result" :type="passed ? 'success' : 'danger'" size="large" effect="dark" round>
        {{ passed ? '✓ 通过' : '待修复' }}
      </el-tag>
    </template>

    <template #tools>
      <el-button size="small" round @click="loadSample('incomplete')">缺 info 示例</el-button>
      <el-button size="small" round type="success" plain @click="loadSample('valid')">合规示例</el-button>
      <el-button size="small" round @click="formatJson">格式化</el-button>
      <el-button size="small" round @click="clearInput">清空</el-button>
    </template>

    <template #input>
      <el-input v-model="apiSpec" type="textarea" :rows="14" placeholder="粘贴 OpenAPI 3.0 JSON 规范..." />
    </template>

    <template #actions>
      <el-button type="primary" size="default" :loading="loading" @click="run">
        <el-icon><Search /></el-icon> 开始检查
      </el-button>
      <el-button
        v-if="fixableCount > 0"
        type="warning"
        :loading="fixing && !fixingId"
        @click="doFix()"
      >
        <el-icon><MagicStick /></el-icon> 一键修复 {{ fixableCount }} 项
      </el-button>
      <el-button v-if="hasFixedPreview" plain @click="previewOpen = true">
        <el-icon><View /></el-icon> 预览修复
      </el-button>
      <el-button v-if="result" plain :loading="loading" @click="run">
        <el-icon><Refresh /></el-icon> 重新检查
      </el-button>
      <span class="spacer" />
      <span v-if="result?.source" class="action-hint">
        {{ result.source === 'local' ? '本地规则' : result.source === 'local+ai' ? '本地 + AI' : 'AI 分析' }}
      </span>
    </template>

    <template #results>
      <div
        class="ai-result-banner"
        :class="passed ? 'ok' : stats.error > 0 ? 'warn' : 'info'"
      >
        <el-icon :size="32">
          <component :is="passed ? 'CircleCheckFilled' : 'WarningFilled'" />
        </el-icon>
        <div class="ai-result-banner-text">
          <div class="ai-result-banner-title">{{ result?.fix_summary || result?.summary }}</div>
          <div v-if="appliedLabels.length" class="ai-result-banner-meta">
            已修复：{{ appliedLabels.join('；') }}
          </div>
        </div>
      </div>

      <div class="ai-stat-grid">
        <div class="ai-stat-card error"><span class="num">{{ stats.error }}</span><span class="lbl">错误</span></div>
        <div class="ai-stat-card warn"><span class="num">{{ stats.warning }}</span><span class="lbl">警告</span></div>
        <div class="ai-stat-card info"><span class="num">{{ stats.info }}</span><span class="lbl">提示</span></div>
        <div class="ai-stat-card ok"><span class="num">{{ fixableCount }}</span><span class="lbl">可自动修复</span></div>
      </div>

      <div v-if="result?.violations?.length" class="ai-result-grid">
        <div class="ai-panel">
          <div class="ai-panel-head">
            <span class="ai-panel-title">问题分布</span>
          </div>
          <div ref="chartRef" class="ai-chart-box" style="height:220px" />
        </div>

        <div class="ai-panel">
          <div class="ai-panel-head">
            <span class="ai-panel-title">问题与修复（{{ result.violations.length }}）</span>
            <el-button
              v-if="fixableCount > 0"
              type="warning"
              size="small"
              :loading="fixing && !fixingId"
              @click="doFix()"
            >
              全部修复
            </el-button>
          </div>
          <div class="issue-list">
            <div
              v-for="row in result.violations"
              :key="`${row.field}-${row.message}`"
              class="ai-issue-card"
              :class="row.severity"
            >
              <div class="ai-issue-head">
                <div class="ai-issue-tags">
                  <code class="ai-field-tag">{{ row.field }}</code>
                  <el-tag :type="severityTagType(row.severity)" size="small" round>
                    {{ severityLabel(row.severity) }}
                  </el-tag>
                  <el-tag v-if="row.auto_fixable" type="success" size="small" effect="plain" round>可自动修复</el-tag>
                </div>
              </div>
              <p class="ai-issue-msg">{{ row.message }}</p>
              <div class="ai-fix-zone">
                <div class="ai-fix-text">
                  <el-icon style="vertical-align:-2px"><Tools /></el-icon>
                  {{ row.fix || '请根据问题描述手动调整' }}
                </div>
                <div class="ai-fix-actions">
                  <el-button
                    v-if="row.auto_fixable"
                    type="warning"
                    size="small"
                    :loading="fixingId === (row.fix_id || row.field)"
                    @click="doFix([row.fix_id || row.field], '单项修复')"
                  >
                    <el-icon><MagicStick /></el-icon> 应用修复
                  </el-button>
                  <el-button size="small" @click="copyText(row.fix || row.message, '修复建议')">
                    <el-icon><DocumentCopy /></el-icon> 复制建议
                  </el-button>
                  <el-button
                    v-if="row.fix_snippet"
                    size="small"
                    @click="copyText(row.fix_snippet!, '示例代码')"
                  >
                    <el-icon><CopyDocument /></el-icon> 复制示例
                  </el-button>
                  <el-button
                    v-if="row.fix_snippet"
                    size="small"
                    plain
                    @click="toggleSnippet(row)"
                  >
                    <el-icon><View /></el-icon>
                    {{ isExpanded(row) ? '收起示例' : '查看示例' }}
                  </el-button>
                </div>
                <pre v-if="isExpanded(row) && row.fix_snippet" class="ai-fix-snippet">{{ row.fix_snippet }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="ai-panel" style="text-align:center;padding:40px">
        <el-icon :size="48" color="#10b981"><CircleCheckFilled /></el-icon>
        <p style="color:#9aa0a6;margin-top:12px">规范检查通过，未发现契约问题</p>
      </div>
    </template>

    <template #empty>
      <el-icon :size="48" color="#3b82f6"><Tickets /></el-icon>
      <p>在上方粘贴 OpenAPI 规范，点击「开始检查」</p>
      <p class="hint">支持本地规则即时校验；每项问题提供复制建议、查看示例、单项应用修复等辅助操作</p>
    </template>
  </AiWorkbench>

  <el-dialog v-model="previewOpen" title="修复预览" width="760px" destroy-on-close class="preview-dialog">
    <p style="color:#9aa0a6;font-size:13px;margin-bottom:12px">以下为自动修复后的完整规范，确认后可写入编辑器</p>
    <el-input :model-value="result?.fixed_spec || ''" type="textarea" :rows="20" readonly />
    <template #footer>
      <el-button @click="previewOpen = false">取消</el-button>
      <el-button @click="copyText(result?.fixed_spec || '', '修复后规范')">复制全文</el-button>
      <el-button type="primary" @click="applyPreview">应用到编辑器</el-button>
      <el-button type="warning" :loading="fixing" @click="doFix(); previewOpen = false">修复并复检</el-button>
    </template>
  </el-dialog>

  <AnalysisHistoryPanel
    ref="historyRef"
    analysis-type="contract"
    :active-record-id="activeRecordId"
    @load="loadFromHistory"
  />
</template>

<style scoped>
@import '@/styles/ai-analysis.css';

.spacer { flex: 1; }
.action-hint { font-size: 12px; color: #6b7280; }
.issue-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 520px;
  overflow-y: auto;
  padding-right: 4px;
}
.issue-list::-webkit-scrollbar { width: 6px; }
.issue-list::-webkit-scrollbar-thumb { background: #2a3544; border-radius: 3px; }
</style>

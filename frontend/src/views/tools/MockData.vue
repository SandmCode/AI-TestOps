<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getMockDataMeta, mockData } from '@/api'

interface FieldItem {
  name: string
  type: string
}

interface FieldTypeMeta {
  value: string
  label: string
  group: string
}

interface Preset {
  id: string
  name: string
  desc: string
  icon: string
  color: string
  fields: FieldItem[]
}

const count = ref(10)
const seed = ref<number | null>(null)
const loading = ref(false)
const activePreset = ref('user')
const viewMode = ref<'table' | 'json'>('table')
const fields = ref<FieldItem[]>([])
const result = ref<Record<string, unknown>[]>([])
const fieldTypes = ref<FieldTypeMeta[]>([])
const presets = ref<Preset[]>([])

const groupedFieldTypes = computed(() => {
  const groups = new Map<string, FieldTypeMeta[]>()
  fieldTypes.value.forEach((item) => {
    const list = groups.get(item.group) || []
    list.push(item)
    groups.set(item.group, list)
  })
  return [...groups.entries()].map(([label, options]) => ({ label, options }))
})

const resultColumns = computed(() =>
  fields.value.map((f) => ({
    prop: f.name,
    label: f.name,
    minWidth: Math.min(168, Math.max(108, f.name.length * 9 + 36)),
  })),
)

const jsonOutput = computed(() => JSON.stringify(result.value, null, 2))

const currentPreset = computed(() => presets.value.find((p) => p.id === activePreset.value))

async function loadMeta() {
  const res = await getMockDataMeta()
  fieldTypes.value = res.data.field_types || []
  presets.value = res.data.presets || []
  if (presets.value.length) {
    applyPreset(presets.value[0].id)
  }
}

function applyPreset(id: string) {
  activePreset.value = id
  const preset = presets.value.find((p) => p.id === id)
  if (!preset) return
  fields.value = preset.fields.map((f) => ({ ...f }))
}

async function generate() {
  if (!fields.value.length) {
    ElMessage.warning('请至少保留一个字段')
    return
  }
  const names = fields.value.map((f) => f.name.trim()).filter(Boolean)
  if (names.length !== fields.value.length) {
    ElMessage.warning('字段名不能为空')
    return
  }
  const schema: Record<string, string> = {}
  fields.value.forEach((f) => { schema[f.name.trim()] = f.type })

  loading.value = true
  try {
    const payload: Record<string, unknown> = { schema, count: count.value }
    if (seed.value !== null && seed.value !== undefined) payload.seed = seed.value
    const res = await mockData(payload)
    result.value = res.data.data || []
    ElMessage.success(`已生成 ${result.value.length} 条数据`)
  } finally {
    loading.value = false
  }
}

function addField() {
  fields.value.push({ name: `field_${fields.value.length + 1}`, type: 'string' })
}

function removeField(idx: number) {
  fields.value.splice(idx, 1)
}

function randomSeed() {
  seed.value = Math.floor(Math.random() * 1_000_000)
}

function clearSeed() {
  seed.value = null
}

async function copyResult() {
  if (!result.value.length) return
  await navigator.clipboard.writeText(jsonOutput.value)
  ElMessage.success('已复制 JSON 到剪贴板')
}

function downloadResult() {
  if (!result.value.length) return
  const blob = new Blob([jsonOutput.value], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `mock-data-${Date.now()}.json`
  link.click()
  URL.revokeObjectURL(url)
}

function downloadCsv() {
  if (!result.value.length) return
  const cols = fields.value.map((f) => f.name)
  const escape = (val: unknown) => {
    const text = val === null || val === undefined ? '' : String(val)
    return `"${text.replace(/"/g, '""')}"`
  }
  const lines = [
    cols.join(','),
    ...result.value.map((row) => cols.map((col) => escape(row[col])).join(',')),
  ]
  const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `mock-data-${Date.now()}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

onMounted(loadMeta)
</script>

<template>
  <div class="mock-data-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">假数据生成</h1>
        <p class="page-desc">内置 40+ 字段类型与 6 套业务模板，一键生成用户、订单、商品等测试数据</p>
      </div>
      <div class="header-stats" v-if="result.length">
        <div class="stat-chip">
          <span class="stat-label">已生成</span>
          <strong>{{ result.length }}</strong>
        </div>
        <div class="stat-chip">
          <span class="stat-label">字段数</span>
          <strong>{{ fields.length }}</strong>
        </div>
      </div>
    </div>

    <section class="preset-section page-card">
      <div class="section-head">
        <h3>快速模板</h3>
        <span>选择场景后自动填充字段结构</span>
      </div>
      <div class="preset-grid">
        <button
          v-for="preset in presets"
          :key="preset.id"
          type="button"
          class="preset-card"
          :class="{ active: activePreset === preset.id }"
          :style="{ '--accent': preset.color }"
          @click="applyPreset(preset.id)"
        >
          <div class="preset-icon">
            <el-icon><component :is="preset.icon" /></el-icon>
          </div>
          <div class="preset-body">
            <div class="preset-name">{{ preset.name }}</div>
            <div class="preset-desc">{{ preset.desc }}</div>
          </div>
          <div class="preset-count">{{ preset.fields.length }} 字段</div>
        </button>
      </div>
    </section>

    <section class="schema-panel page-card">
      <div class="section-head">
        <div>
          <h3>字段结构</h3>
          <span v-if="currentPreset">{{ currentPreset.name }} · 可自由增删改</span>
        </div>
        <el-button link type="primary" @click="addField">+ 添加字段</el-button>
      </div>

      <div class="config-bar">
        <el-form inline>
          <el-form-item label="生成数量">
            <el-input-number v-model="count" :min="1" :max="500" />
          </el-form-item>
          <el-form-item label="随机种子">
            <div class="seed-row">
              <el-input-number v-model="seed" :min="0" :max="999999999" controls-position="right" placeholder="可选" />
              <el-button @click="randomSeed">随机</el-button>
              <el-button @click="clearSeed">清空</el-button>
            </div>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="generate">生成数据</el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="fields-table">
        <div class="fields-head">
          <span>#</span>
          <span>字段名</span>
          <span>数据类型</span>
          <span>操作</span>
        </div>
        <div v-for="(f, idx) in fields" :key="idx" class="field-row">
          <span class="field-index">{{ idx + 1 }}</span>
          <el-input v-model="f.name" class="field-name-input" placeholder="例如 user_id" />
          <el-select v-model="f.type" class="field-type-select" filterable placeholder="选择类型">
            <el-option-group
              v-for="group in groupedFieldTypes"
              :key="group.label"
              :label="group.label"
            >
              <el-option
                v-for="opt in group.options"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-option-group>
          </el-select>
          <el-button type="danger" link @click="removeField(idx)">删除</el-button>
        </div>
      </div>
    </section>

    <section class="result-panel page-card">
        <div class="section-head">
          <div>
            <h3>生成结果</h3>
            <span>支持表格预览、JSON 查看与导出</span>
          </div>
          <div class="result-actions">
            <el-radio-group v-model="viewMode" size="small">
              <el-radio-button value="table">表格</el-radio-button>
              <el-radio-button value="json">JSON</el-radio-button>
            </el-radio-group>
            <el-button :disabled="!result.length" @click="copyResult">复制 JSON</el-button>
            <el-button :disabled="!result.length" @click="downloadResult">下载 JSON</el-button>
            <el-button :disabled="!result.length" @click="downloadCsv">下载 CSV</el-button>
          </div>
        </div>

        <div v-if="!result.length" class="empty-state">
          <el-icon class="empty-icon"><Box /></el-icon>
          <p>选择模板并点击「生成数据」</p>
          <span>可生成用户、订单、商品 SKU、员工档案等多种业务数据</span>
        </div>

        <div v-else-if="viewMode === 'table'" class="table-wrap">
          <el-table :data="result" stripe max-height="560" border style="width: 100%">
            <el-table-column type="index" label="#" width="56" />
            <el-table-column
              v-for="col in resultColumns"
              :key="col.prop"
              :prop="col.prop"
              :label="col.label"
              :min-width="col.minWidth"
              show-overflow-tooltip
            />
          </el-table>
        </div>

        <pre v-else class="json-output">{{ jsonOutput }}</pre>
    </section>
  </div>
</template>

<style scoped>
.mock-data-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.page-title {
  margin-bottom: 8px;
}

.page-desc {
  color: #9aa0a6;
  font-size: 14px;
  line-height: 1.6;
}

.header-stats {
  display: flex;
  gap: 12px;
}

.stat-chip {
  min-width: 88px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #141c28;
  border: 1px solid #2a3544;
  text-align: center;
}

.stat-label {
  display: block;
  color: #9aa0a6;
  font-size: 12px;
  margin-bottom: 4px;
}

.stat-chip strong {
  color: #10b981;
  font-size: 20px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.section-head h3 {
  color: #fff;
  font-size: 16px;
  margin-bottom: 4px;
}

.section-head span {
  color: #9aa0a6;
  font-size: 12px;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.preset-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid #2a3544;
  background: #141c28;
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
}

.preset-card:hover {
  border-color: color-mix(in srgb, var(--accent) 50%, #2a3544);
  transform: translateY(-1px);
}

.preset-card.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 35%, transparent);
  background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 12%, #141c28), #141c28);
}

.preset-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--accent) 18%, #141c28);
  color: var(--accent);
  font-size: 20px;
  flex-shrink: 0;
}

.preset-body {
  flex: 1;
  min-width: 0;
}

.preset-name {
  font-weight: 600;
  color: #fff;
  margin-bottom: 4px;
}

.preset-desc {
  color: #9aa0a6;
  font-size: 12px;
  line-height: 1.4;
}

.preset-count {
  color: #6b7280;
  font-size: 12px;
  white-space: nowrap;
}

.config-bar {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #2a3544;
}

.config-bar :deep(.el-form-item) {
  margin-bottom: 0;
}

.seed-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.fields-table {
  border: 1px solid #2a3544;
  border-radius: 10px;
  overflow-x: auto;
}

.fields-head,
.field-row {
  display: grid;
  grid-template-columns: 40px minmax(140px, 220px) minmax(160px, 240px) 56px;
  gap: 12px;
  align-items: center;
  padding: 10px 14px;
}

.field-name-input,
.field-type-select {
  width: 100%;
  min-width: 0;
}

.field-name-input :deep(.el-input__inner) {
  font-family: Consolas, 'Courier New', monospace;
}

.fields-head {
  background: #141c28;
  color: #9aa0a6;
  font-size: 12px;
}

.field-row + .field-row {
  border-top: 1px solid #2a3544;
}

.field-index {
  color: #6b7280;
  text-align: center;
  font-size: 12px;
}

.result-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.empty-state {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #9aa0a6;
  border: 1px dashed #2a3544;
  border-radius: 12px;
  background: #141c28;
}

.empty-icon {
  font-size: 42px;
  color: #4b5563;
  margin-bottom: 12px;
}

.empty-state p {
  color: #e8eaed;
  font-size: 16px;
  margin-bottom: 6px;
}

.table-wrap {
  border-radius: 10px;
  overflow-x: auto;
}

.json-output {
  background: #141c28;
  border: 1px solid #2a3544;
  padding: 16px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.6;
  color: #10b981;
  max-height: 560px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>

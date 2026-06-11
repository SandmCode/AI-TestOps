<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAiConfigs,
  getAiConfigStatus,
  createAiConfig,
  updateAiConfig,
  deleteAiConfig,
  activateAiConfig,
  deactivateAiConfig,
  testAiConfig,
  getCcSwitchStatus,
  importFromCcSwitch,
} from '@/api'

interface AiConfigItem {
  id: number
  name: string
  provider: string
  provider_display: string
  masked_api_key: string
  base_url: string
  model: string
  temperature: number
  max_tokens: number
  is_active: boolean
}

interface CcSwitchProvider {
  id: string
  name: string
  app_type: string
  is_current: boolean
  importable: boolean
  has_api_key: boolean
  base_url: string
  model: string
  note: string
}

const PROVIDERS = [
  { value: 'zhipu', label: '智谱 AI', baseUrl: '', defaultModel: 'glm-4-flash' },
  { value: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1', defaultModel: 'gpt-4o-mini' },
  { value: 'deepseek', label: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1', defaultModel: 'deepseek-chat' },
  { value: 'qwen', label: '通义千问', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', defaultModel: 'qwen-plus' },
  { value: 'moonshot', label: 'Moonshot', baseUrl: 'https://api.moonshot.cn/v1', defaultModel: 'moonshot-v1-8k' },
  { value: 'custom', label: '自定义 OpenAI 兼容', baseUrl: '', defaultModel: '' },
]

const configs = ref<AiConfigItem[]>([])
const status = ref<Record<string, unknown> | null>(null)
const ccSwitch = ref<Record<string, unknown> | null>(null)
const loading = ref(false)
const importingCc = ref(false)
const ccDialogVisible = ref(false)
const dialogVisible = ref(false)
const testingId = ref<number | null>(null)
const editingId = ref<number | null>(null)
const showApiKey = ref(false)
const selectedCcProvider = ref('')
const ccSourceApp = ref('claude')

const form = reactive({
  name: '',
  provider: 'zhipu',
  api_key: '',
  base_url: '',
  model: 'glm-4-flash',
  temperature: 0.7,
  max_tokens: 4096,
})

const currentProvider = computed(() => PROVIDERS.find((p) => p.value === form.provider))
const needsBaseUrl = computed(() => form.provider !== 'zhipu')
const ccProviders = computed(() => (ccSwitch.value?.providers as CcSwitchProvider[]) || [])
const importableCcProviders = computed(() => ccProviders.value.filter((p) => p.importable))

function applyProviderDefaults() {
  const preset = currentProvider.value
  if (!preset) return
  if (preset.baseUrl) form.base_url = preset.baseUrl
  if (preset.defaultModel) form.model = preset.defaultModel
}

function resetForm() {
  editingId.value = null
  showApiKey.value = false
  form.name = ''
  form.provider = 'zhipu'
  form.api_key = ''
  form.base_url = ''
  form.model = 'glm-4-flash'
  form.temperature = 0.7
  form.max_tokens = 4096
}

async function loadData() {
  loading.value = true
  try {
    const [listRes, statusRes, ccRes] = await Promise.all([
      getAiConfigs(),
      getAiConfigStatus(),
      getCcSwitchStatus(),
    ])
    configs.value = listRes.data.results ?? listRes.data
    status.value = statusRes.data
    ccSwitch.value = ccRes.data
    const current = importableCcProviders.value.find((p) => p.is_current)
    selectedCcProvider.value = current?.id || importableCcProviders.value[0]?.id || ''
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: AiConfigItem) {
  editingId.value = row.id
  showApiKey.value = false
  form.name = row.name
  form.provider = row.provider
  form.api_key = ''
  form.base_url = row.base_url
  form.model = row.model
  form.temperature = row.temperature
  form.max_tokens = row.max_tokens
  dialogVisible.value = true
}

async function saveConfig() {
  if (!form.name.trim() || !form.model.trim()) {
    ElMessage.warning('请填写配置名称和模型')
    return
  }
  if (!editingId.value && !form.api_key.trim()) {
    ElMessage.warning('请填写 API Key')
    return
  }

  const payload: Record<string, unknown> = {
    name: form.name.trim(),
    provider: form.provider,
    base_url: form.base_url.trim(),
    model: form.model.trim(),
    temperature: form.temperature,
    max_tokens: form.max_tokens,
  }
  if (form.api_key.trim()) payload.api_key = form.api_key.trim()

  try {
    if (editingId.value) {
      await updateAiConfig(editingId.value, payload)
      ElMessage.success('配置已更新')
    } else {
      await createAiConfig(payload)
      ElMessage.success('配置已创建')
    }
    dialogVisible.value = false
    await loadData()
  } catch { /* interceptor */ }
}

async function quickImportCcSwitch() {
  if (!ccSwitch.value?.available) {
    ccDialogVisible.value = true
    return
  }
  importingCc.value = true
  try {
    const res = await importFromCcSwitch({ source_app: 'claude', activate: true })
    ElMessage.success(`已从 CC Switch 导入「${res.data.source.provider_name}」`)
    await loadData()
  } catch { /* interceptor */ }
  finally {
    importingCc.value = false
  }
}

async function confirmImportCcSwitch() {
  if (!selectedCcProvider.value) {
    ElMessage.warning('请选择 Provider')
    return
  }
  importingCc.value = true
  try {
    const res = await importFromCcSwitch({
      provider_id: selectedCcProvider.value,
      source_app: ccSourceApp.value,
      activate: true,
    })
    ElMessage.success(`已导入「${res.data.source.provider_name}」`)
    ccDialogVisible.value = false
    await loadData()
  } catch { /* interceptor */ }
  finally {
    importingCc.value = false
  }
}

async function handleToggleActive(row: AiConfigItem) {
  if (row.is_active) {
    await deactivateAiConfig(row.id)
    ElMessage.success(`已关闭「${row.name}」`)
  } else {
    await activateAiConfig(row.id)
    ElMessage.success(`已启用「${row.name}」`)
  }
  await loadData()
}

async function handleTest(row: AiConfigItem) {
  testingId.value = row.id
  try {
    const res = await testAiConfig(row.id)
    if (res.data.success) ElMessage.success(`连接成功：${res.data.reply}`)
    else ElMessage.error(res.data.error || '连接失败')
  } catch { /* interceptor */ }
  finally {
    testingId.value = null
  }
}

async function handleDelete(row: AiConfigItem) {
  await ElMessageBox.confirm(`确定删除配置「${row.name}」？`, '删除确认', { type: 'warning' })
  await deleteAiConfig(row.id)
  ElMessage.success('已删除')
  await loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="provider-config">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-tag v-if="ccSwitch?.available" type="success" size="small">已检测到 CC Switch</el-tag>
        <el-tag v-else type="info" size="small">未检测到 CC Switch</el-tag>
        <span class="hint">支持手动填写 API Key，或从本地 CC Switch 一键导入</span>
      </div>
      <div class="toolbar-right">
        <el-button :loading="importingCc" @click="quickImportCcSwitch">从 CC Switch 导入</el-button>
        <el-button @click="ccDialogVisible = true">选择 Provider</el-button>
        <el-button type="primary" @click="openCreate">手动新增</el-button>
      </div>
    </div>

    <div class="status-card" :class="{ ok: status?.configured }">
      <div class="status-icon"><el-icon :size="24"><Setting /></el-icon></div>
      <div>
        <div class="status-title">{{ status?.configured ? 'AI 已就绪' : 'AI 未配置' }}</div>
        <div v-if="status?.configured" class="status-detail">
          {{ status.provider_display }} · {{ status.model }} · {{ status.masked_api_key }}
        </div>
        <div v-else class="status-detail warn">请配置 API Key 或从 CC Switch 导入后再使用 AI 功能</div>
      </div>
    </div>

    <div class="page-card">
      <el-table v-loading="loading" :data="configs" stripe>
        <el-table-column prop="name" label="配置名称" min-width="160" />
        <el-table-column prop="provider_display" label="厂商" width="120" />
        <el-table-column prop="model" label="模型" min-width="140" />
        <el-table-column prop="masked_api_key" label="API Key" width="150" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" type="success" size="small">启用中</el-tag>
            <el-tag v-else type="info" size="small">未启用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              :type="row.is_active ? 'warning' : 'primary'"
              @click="handleToggleActive(row)"
            >
              {{ row.is_active ? '关闭' : '启用' }}
            </el-button>
            <el-button link type="primary" :loading="testingId === row.id" @click="handleTest(row)">测试</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑配置' : '手动新增配置'" width="560px" destroy-on-close @closed="resetForm">
      <el-form label-width="100px">
        <el-form-item label="配置名称" required>
          <el-input v-model="form.name" placeholder="如：DeepSeek 生产环境" />
        </el-form-item>
        <el-form-item label="厂商" required>
          <el-select v-model="form.provider" style="width:100%" @change="applyProviderDefaults">
            <el-option v-for="p in PROVIDERS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="editingId ? '新 API Key' : 'API Key'" :required="!editingId">
          <el-input v-model="form.api_key" :type="showApiKey ? 'text' : 'password'" :placeholder="editingId ? '留空则不修改' : '请输入 API Key'">
            <template #append>
              <el-button @click="showApiKey = !showApiKey">{{ showApiKey ? '隐藏' : '显示' }}</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item v-if="needsBaseUrl" label="Base URL">
          <el-input v-model="form.base_url" />
        </el-form-item>
        <el-form-item label="模型" required>
          <el-input v-model="form.model" />
        </el-form-item>
        <el-form-item label="温度">
          <el-slider v-model="form.temperature" :min="0" :max="1" :step="0.1" show-input />
        </el-form-item>
        <el-form-item label="Max Tokens">
          <el-input-number v-model="form.max_tokens" :min="256" :max="32000" :step="256" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="ccDialogVisible" title="从 CC Switch 导入" width="620px">
      <template v-if="ccSwitch?.available">
        <el-form label-width="100px">
          <el-form-item label="来源应用">
            <el-radio-group v-model="ccSourceApp">
              <el-radio value="claude">Claude</el-radio>
              <el-radio value="codex">Codex</el-radio>
              <el-radio value="gemini">Gemini</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="Provider">
            <el-select v-model="selectedCcProvider" style="width:100%" placeholder="选择 Provider">
              <el-option
                v-for="p in ccProviders"
                :key="p.id"
                :label="`${p.name}${p.is_current ? ' (当前)' : ''}${p.importable ? '' : ' - 不可导入'}`"
                :value="p.id"
                :disabled="!p.importable"
              />
            </el-select>
          </el-form-item>
        </el-form>
        <p class="cc-tip">读取路径：{{ ccSwitch.path }}。OAuth 登录的 Provider 无法导出 Key，请选择 API Key 类型配置。</p>
      </template>
      <el-empty v-else description="未检测到 ~/.cc-switch，请先安装并配置 CC Switch" />
      <template #footer>
        <el-button @click="ccDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importingCc" :disabled="!ccSwitch?.available" @click="confirmImportCcSwitch">导入并启用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
}
.toolbar-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.toolbar-right { display: flex; gap: 8px; flex-wrap: wrap; }
.hint { color: #6b7280; font-size: 13px; }
.status-card {
  display: flex; gap: 14px; align-items: center; padding: 16px 20px; margin-bottom: 16px;
  background: #141c28; border: 1px solid #3d2a2a; border-radius: 12px;
}
.status-card.ok { border-color: #1e4d3a; }
.status-icon {
  width: 44px; height: 44px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(239,68,68,.15); color: #f87171;
}
.status-card.ok .status-icon { background: rgba(34,197,94,.15); color: #4ade80; }
.status-title { font-weight: 600; color: #e8eaed; margin-bottom: 4px; }
.status-detail { font-size: 13px; color: #9aa0a6; }
.status-detail.warn { color: #fbbf24; }
.page-card { background: #141c28; border: 1px solid #2a3544; border-radius: 12px; padding: 16px; }
.cc-tip { margin: 0; font-size: 12px; color: #6b7280; line-height: 1.6; }
</style>

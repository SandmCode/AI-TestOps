<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { encodeConvert, getEncodeMeta } from '@/api'

interface EncodeAction {
  value: string
  label: string
  group: string
  desc: string
}

const actions = ref<EncodeAction[]>([])
const action = ref('base64_encode')
const input = ref('Hello, 测试平台!')
const output = ref('')
const salt = ref('')
const secret = ref('')
const loading = ref(false)

const HASH_ACTIONS = new Set(['md5', 'sha1', 'sha256', 'sha512', 'hmac_sha256'])

const groupedActions = computed(() => {
  const groups = new Map<string, EncodeAction[]>()
  actions.value.forEach((item) => {
    const list = groups.get(item.group) || []
    list.push(item)
    groups.set(item.group, list)
  })
  return [...groups.entries()].map(([label, options]) => ({ label, options }))
})

const currentAction = computed(() => actions.value.find((a) => a.value === action.value))

const isHash = computed(() => HASH_ACTIONS.has(action.value))
const needsSecret = computed(() => action.value === 'hmac_sha256')

const actionHint = computed(() => {
  const cur = currentAction.value
  if (!cur) return ''
  if (isHash.value) {
    return `${cur.desc}。摘要为单向计算，无法从结果反推原文。`
  }
  return cur.desc
})

async function loadMeta() {
  const res = await getEncodeMeta()
  actions.value = res.data.actions || []
  if (actions.value.length && !actions.value.some((a) => a.value === action.value)) {
    action.value = actions.value[0].value
  }
}

async function run() {
  loading.value = true
  try {
    const payload: Record<string, string> = { action: action.value, text: input.value }
    if (salt.value.trim()) payload.salt = salt.value.trim()
    if (secret.value.trim()) payload.secret = secret.value.trim()
    const res = await encodeConvert(payload)
    output.value = res.data.result ?? ''
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } }
    ElMessage.error(err.response?.data?.error || '转换失败')
  } finally {
    loading.value = false
  }
}

function copyOutput() {
  if (!output.value) return
  navigator.clipboard.writeText(output.value)
  ElMessage.success('已复制结果')
}

function swapText() {
  if (!output.value) return
  input.value = output.value
  output.value = ''
}

function clearAll() {
  input.value = ''
  output.value = ''
}

function loadSample() {
  if (isHash.value) {
    input.value = 'Pass@123456'
    salt.value = ''
    secret.value = action.value === 'hmac_sha256' ? 'my-secret-key' : ''
  } else if (action.value.includes('base64')) {
    input.value = 'Hello, 测试平台!'
  } else if (action.value.includes('url')) {
    input.value = 'name=张三&city=北京'
  } else if (action.value.includes('hex')) {
    input.value = 'Hello'
  } else {
    input.value = '<div>测试 & 编码</div>'
  }
  run()
}

watch(action, () => {
  output.value = ''
})

onMounted(async () => {
  await loadMeta()
})
</script>

<template>
  <div class="encode-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">编码转换</h1>
        <p class="page-desc">
          测试常用编解码与摘要计算：Base64 / URL / Hex、MD5 / SHA 系列等。
          「摘要哈希」用于校验密码或签名，<strong>不可逆</strong>，不是加密解密。
        </p>
      </div>
    </div>

    <div class="page-card">
      <div class="action-section">
        <div class="section-label">选择方式</div>
        <div class="action-groups">
          <div v-for="group in groupedActions" :key="group.label" class="action-group">
            <span class="group-title">{{ group.label }}</span>
            <el-radio-group v-model="action" size="small">
              <el-radio-button
                v-for="opt in group.options"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </el-radio-button>
            </el-radio-group>
          </div>
        </div>
        <p v-if="actionHint" class="action-hint">{{ actionHint }}</p>
      </div>

      <div v-if="isHash" class="extra-fields">
        <el-form inline>
          <el-form-item label="盐值 Salt（可选）">
            <el-input v-model="salt" placeholder="加盐：先拼接再哈希" style="width: 220px" clearable />
          </el-form-item>
          <el-form-item v-if="needsSecret" label="HMAC 密钥" required>
            <el-input v-model="secret" placeholder="HMAC 签名密钥" style="width: 220px" clearable />
          </el-form-item>
        </el-form>
      </div>

      <el-row :gutter="16" class="io-row">
        <el-col :span="12">
          <div class="io-head">
            <h4>输入</h4>
            <span v-if="isHash">原文</span>
            <span v-else>待转换文本</span>
          </div>
          <el-input v-model="input" type="textarea" :rows="14" placeholder="输入待处理内容" />
        </el-col>
        <el-col :span="12">
          <div class="io-head">
            <h4>输出</h4>
            <span>{{ isHash ? '摘要结果（十六进制）' : '转换结果' }}</span>
          </div>
          <el-input v-model="output" type="textarea" :rows="14" readonly placeholder="结果将显示在这里" />
        </el-col>
      </el-row>

      <div class="toolbar">
        <el-button type="primary" :loading="loading" @click="run">转换</el-button>
        <el-button @click="loadSample">填入示例</el-button>
        <el-button :disabled="!output" @click="copyOutput">复制结果</el-button>
        <el-button :disabled="!output" @click="swapText">结果填入输入</el-button>
        <el-button @click="clearAll">清空</el-button>
      </div>
    </div>

    <div class="page-card tips-card">
      <h3>常见用途</h3>
      <ul>
        <li><strong>Base64</strong>：接口 Body、Basic Auth、二进制文本传输</li>
        <li><strong>URL 编码</strong>：Query 参数、中文路径</li>
        <li><strong>MD5 / SHA</strong>：密码指纹、文件校验、接口 sign（需配合盐值）</li>
        <li><strong>HMAC-SHA256</strong>：带密钥的 API 签名（如 JWT、Webhook）</li>
        <li><strong>Hex</strong>：查看字节、与前端/crypto 调试对照</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.encode-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-desc {
  color: #9aa0a6;
  font-size: 14px;
  line-height: 1.6;
  max-width: 720px;
}

.page-desc strong {
  color: #f59e0b;
}

.action-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #2a3544;
}

.section-label {
  color: #9aa0a6;
  font-size: 12px;
  margin-bottom: 12px;
}

.action-groups {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.action-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.group-title {
  color: #e8eaed;
  font-size: 13px;
  font-weight: 600;
  min-width: 72px;
}

.action-hint {
  margin-top: 12px;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.5;
}

.extra-fields {
  margin-bottom: 16px;
  padding: 12px 14px;
  background: #141c28;
  border-radius: 8px;
  border: 1px solid #2a3544;
}

.io-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.io-head h4 {
  color: #fff;
  font-size: 14px;
}

.io-head span {
  color: #6b7280;
  font-size: 12px;
}

.io-row {
  margin-top: 4px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.tips-card h3 {
  color: #fff;
  font-size: 15px;
  margin-bottom: 12px;
}

.tips-card ul {
  color: #9aa0a6;
  font-size: 13px;
  line-height: 1.8;
  padding-left: 18px;
}

.tips-card strong {
  color: #cbd5e1;
}
</style>

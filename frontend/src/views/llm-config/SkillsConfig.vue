<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import {
  getAiSkills,
  getAiSkillsSettings,
  updateAiSkillsSettings,
  updateAiSkill,
  deleteAiSkill,
  batchDeleteAiSkills,
  uploadAiSkill,
  scanLocalSkills,
  importCcSwitchSkills,
} from '@/api'

interface SkillItem {
  id: number
  name: string
  folder_name: string
  content: string
  content_preview: string
  source_path: string
  source_type: string
  is_enabled: boolean
  sort_order: number
}

const skills = ref<SkillItem[]>([])
const skillsEnabled = ref(true)
const loading = ref(false)
const scanning = ref(false)
const importing = ref(false)
const uploading = ref(false)
const clearing = ref(false)
const previewVisible = ref(false)
const uploadVisible = ref(false)
const previewSkill = ref<SkillItem | null>(null)
const uploadMode = ref<'file' | 'manual'>('file')
const uploadFile = ref<File | null>(null)

const manualForm = reactive({
  name: '',
  folder_name: '',
  content: '',
})

const enabledCount = computed(() => skills.value.filter((s) => s.is_enabled).length)

async function loadData() {
  loading.value = true
  try {
    const [listRes, settingsRes] = await Promise.all([getAiSkills(), getAiSkillsSettings()])
    skills.value = listRes.data.results ?? listRes.data
    skillsEnabled.value = settingsRes.data.skills_enabled
  } finally {
    loading.value = false
  }
}

async function toggleGlobal(val: boolean) {
  await updateAiSkillsSettings({ skills_enabled: val })
  skillsEnabled.value = val
  ElMessage.success(val ? '已启用 Skills 注入' : '已关闭 Skills 注入')
}

async function toggleSkill(row: SkillItem, val: boolean) {
  await updateAiSkill(row.id, { is_enabled: val })
  row.is_enabled = val
}

async function handleScanLocal() {
  scanning.value = true
  try {
    const res = await scanLocalSkills()
    skills.value = res.data.skills
    ElMessage.success(`扫描完成：新增 ${res.data.created}，更新 ${res.data.updated}`)
  } catch { /* interceptor */ }
  finally {
    scanning.value = false
  }
}

async function handleImportCcSwitch() {
  importing.value = true
  try {
    const res = await importCcSwitchSkills()
    skills.value = res.data.skills
    ElMessage.success(`同步完成：新增 ${res.data.created}，更新 ${res.data.updated}，跳过 ${res.data.skipped}`)
  } catch { /* interceptor */ }
  finally {
    importing.value = false
  }
}

function openPreview(row: SkillItem) {
  previewSkill.value = row
  previewVisible.value = true
}

function openUpload() {
  uploadMode.value = 'file'
  uploadFile.value = null
  manualForm.name = ''
  manualForm.folder_name = ''
  manualForm.content = ''
  uploadVisible.value = true
}

function onFileChange(file: UploadFile) {
  uploadFile.value = file.raw ?? null
}

function onFileRemove() {
  uploadFile.value = null
}

async function submitUpload() {
  uploading.value = true
  try {
    const formData = new FormData()
    if (uploadMode.value === 'file') {
      if (!uploadFile.value) {
        ElMessage.warning('请选择 SKILL.md 或 ZIP 文件')
        return
      }
      formData.append('file', uploadFile.value)
      if (manualForm.name.trim()) formData.append('name', manualForm.name.trim())
      if (manualForm.folder_name.trim()) formData.append('folder_name', manualForm.folder_name.trim())
    } else {
      if (!manualForm.content.trim()) {
        ElMessage.warning('请填写 SKILL.md 内容')
        return
      }
      formData.append('content', manualForm.content.trim())
      if (manualForm.name.trim()) formData.append('name', manualForm.name.trim())
      if (manualForm.folder_name.trim()) formData.append('folder_name', manualForm.folder_name.trim())
    }
    const res = await uploadAiSkill(formData)
    ElMessage.success(`上传成功：新增 ${res.data.created}，更新 ${res.data.updated}`)
    uploadVisible.value = false
    await loadData()
  } catch { /* interceptor */ }
  finally {
    uploading.value = false
  }
}

async function handleDelete(row: SkillItem) {
  await ElMessageBox.confirm(`确定删除 Skill「${row.name}」？`, '删除确认', { type: 'warning' })
  await deleteAiSkill(row.id)
  ElMessage.success('已删除')
  await loadData()
}

async function handleClearAll() {
  if (!skills.value.length) {
    ElMessage.info('当前没有 Skill 可删除')
    return
  }
  await ElMessageBox.confirm(
    `确定一键删除全部 ${skills.value.length} 个 Skill？此操作不可恢复。`,
    '一键删除',
    { type: 'warning', confirmButtonText: '全部删除', confirmButtonClass: 'el-button--danger' },
  )
  clearing.value = true
  try {
    const res = await batchDeleteAiSkills()
    ElMessage.success(`已删除 ${res.data.deleted} 个 Skill`)
    await loadData()
  } catch { /* interceptor */ }
  finally {
    clearing.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="skills-config">
    <div class="toolbar">
      <div class="global-switch">
        <span>Skills 注入</span>
        <el-switch :model-value="skillsEnabled" @change="toggleGlobal" />
        <span class="hint">开启后，AI 执行时会先读取已启用的 SKILL.md 内容</span>
      </div>
      <div class="actions">
        <el-button type="primary" @click="openUpload">上传 Skill</el-button>
        <el-button :loading="scanning" @click="handleScanLocal">扫描本地</el-button>
        <el-button :loading="importing" @click="handleImportCcSwitch">CC Switch 同步</el-button>
        <el-button type="danger" plain :loading="clearing" :disabled="!skills.length" @click="handleClearAll">
          一键删除
        </el-button>
      </div>
    </div>

    <div class="info-card">
      <p>Skills 是一个文件夹 + <code>SKILL.md</code>。支持上传单个 <code>.md</code>、按文件夹打包的 <code>.zip</code>，或直接粘贴内容。</p>
      <p>当前已启用 <strong>{{ enabledCount }}</strong> / {{ skills.length }} 个 Skill{{ skillsEnabled ? '' : '（全局已关闭，不会注入）' }}。</p>
    </div>

    <div class="page-card">
      <el-table v-loading="loading" :data="skills" stripe empty-text="暂无 Skill，请上传或扫描本地">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="folder_name" label="文件夹" min-width="140" />
        <el-table-column label="来源" width="110">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.source_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_path" label="路径" min-width="220" show-overflow-tooltip />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch :model-value="row.is_enabled" @change="(v: boolean) => toggleSkill(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openPreview(row)">预览</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="uploadVisible" title="上传 Skill" width="640px" destroy-on-close>
      <el-tabs v-model="uploadMode">
        <el-tab-pane label="文件上传" name="file">
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            accept=".md,.zip"
            @change="onFileChange"
            @remove="onFileRemove"
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">拖拽或点击上传 SKILL.md / ZIP</div>
            <template #tip>
              <div class="upload-tip">
                单文件：直接上传 SKILL.md<br>
                ZIP：每个子文件夹内需包含 SKILL.md，如 <code>my-skill/SKILL.md</code>
              </div>
            </template>
          </el-upload>
          <el-form label-width="90px" style="margin-top: 16px">
            <el-form-item label="显示名称">
              <el-input v-model="manualForm.name" placeholder="可选，默认同文件夹名" />
            </el-form-item>
            <el-form-item label="文件夹名">
              <el-input v-model="manualForm.folder_name" placeholder="可选，上传 .md 时生效" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="手动填写" name="manual">
          <el-form label-width="90px">
            <el-form-item label="名称">
              <el-input v-model="manualForm.name" placeholder="如：测试设计规范" />
            </el-form-item>
            <el-form-item label="文件夹名">
              <el-input v-model="manualForm.folder_name" placeholder="如：test-design-guide" />
            </el-form-item>
            <el-form-item label="内容" required>
              <el-input
                v-model="manualForm.content"
                type="textarea"
                :rows="14"
                placeholder="# Skill 标题&#10;&#10;在此编写 SKILL.md 内容..."
              />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">确认上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="previewVisible" :title="previewSkill?.name || 'Skill 预览'" width="720px">
      <pre class="skill-preview">{{ previewSkill?.content }}</pre>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
}
.global-switch { display: flex; align-items: center; gap: 10px; color: #e8eaed; }
.hint { color: #6b7280; font-size: 13px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.info-card {
  padding: 14px 18px; margin-bottom: 16px;
  background: #141c28; border: 1px solid #2a3544; border-radius: 12px;
  color: #9aa0a6; font-size: 13px; line-height: 1.7;
}
.info-card p { margin: 0 0 6px; }
.info-card p:last-child { margin-bottom: 0; }
.info-card code { background: #1e2a3a; padding: 1px 6px; border-radius: 4px; color: #93c5fd; }
.info-card strong { color: #e8eaed; }
.page-card { background: #141c28; border: 1px solid #2a3544; border-radius: 12px; padding: 16px; }
.skill-preview {
  max-height: 60vh; overflow: auto; margin: 0; padding: 16px;
  background: #0f1419; border-radius: 8px; color: #cbd5e1;
  font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-word;
}
.upload-icon { font-size: 48px; color: #6b7280; margin-bottom: 8px; }
.upload-text { color: #9aa0a6; font-size: 14px; }
.upload-tip { color: #6b7280; font-size: 12px; line-height: 1.6; }
.upload-tip code { background: #1e2a3a; padding: 1px 4px; border-radius: 3px; }
</style>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { CaseFieldDef } from '@/composables/useCaseFieldSchema'
import {
  createCaseFieldDefinition,
  updateCaseFieldDefinition,
  deleteCaseFieldDefinition,
  resetCaseFieldDefinitions,
} from '@/api'

const props = defineProps<{
  modelValue: boolean
  projectId: number | null
  fields: CaseFieldDef[]
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  changed: []
}>()

const editVisible = ref(false)
const editing = ref<Partial<CaseFieldDef>>({})
const optionsText = ref('')

const fieldTypes = [
  { value: 'text', label: '单行文本' },
  { value: 'textarea', label: '多行文本' },
  { value: 'select', label: '下拉选择' },
  { value: 'date', label: '日期' },
  { value: 'priority', label: '优先级' },
  { value: 'passed', label: '执行状态' },
]

function close() {
  emit('update:modelValue', false)
}

function openCreate() {
  editing.value = {
    label: '',
    key: '',
    field_type: 'text',
    required: false,
    searchable: false,
    show_in_list: true,
    show_in_filter: false,
    options: [],
  }
  optionsText.value = ''
  editVisible.value = true
}

function openEdit(row: CaseFieldDef) {
  editing.value = { ...row }
  optionsText.value = (row.options || []).join('\n')
  editVisible.value = true
}

async function saveField() {
  if (!props.projectId || !editing.value.label?.trim()) {
    ElMessage.warning('请填写显示名称')
    return
  }
  const payload = {
    project: props.projectId,
    label: editing.value.label.trim(),
    key: editing.value.key?.trim() || editing.value.label.trim().replace(/\s+/g, '_'),
    field_type: editing.value.field_type || 'text',
    required: editing.value.required ?? false,
    searchable: editing.value.searchable ?? false,
    show_in_list: editing.value.show_in_list ?? true,
    show_in_filter: editing.value.show_in_filter ?? false,
    options: optionsText.value.split('\n').map((s) => s.trim()).filter(Boolean),
    storage: editing.value.is_system ? editing.value.storage : 'extra',
    column_name: editing.value.column_name || '',
    is_system: editing.value.is_system ?? false,
  }
  if (editing.value.id) {
    await updateCaseFieldDefinition(editing.value.id, payload)
    ElMessage.success('字段已更新')
  } else {
    await createCaseFieldDefinition(payload)
    ElMessage.success('字段已新增')
  }
  editVisible.value = false
  emit('changed')
}

async function handleDelete(row: CaseFieldDef) {
  if (row.is_system) {
    ElMessage.warning('系统字段不可删除，可修改名称或取消展示')
    return
  }
  await ElMessageBox.confirm(`确定删除字段「${row.label}」？`, '删除确认', { type: 'warning' })
  await deleteCaseFieldDefinition(row.id)
  ElMessage.success('已删除')
  emit('changed')
}

async function handleReset() {
  if (!props.projectId) return
  await ElMessageBox.confirm('将恢复为默认字段配置，是否继续？', '恢复默认', { type: 'warning' })
  await resetCaseFieldDefinitions(props.projectId)
  ElMessage.success('已恢复默认字段')
  emit('changed')
}

watch(() => props.modelValue, (open) => {
  if (!open) editVisible.value = false
})
</script>

<template>
  <el-dialog :model-value="modelValue" title="用例字段配置" width="760px" @update:model-value="emit('update:modelValue', $event)">
    <p class="hint">
      字段配置是唯一来源：<strong>表单</strong>显示全部字段；
      <strong>列表展示</strong>控制列表区显示哪些字段（第一个为标题）；
      <strong>筛选展示</strong>控制筛选区显示哪些字段（数量与字段均由此决定）；
      AI 生成与表单字段一致。
    </p>
    <div class="toolbar">
      <el-button type="primary" :disabled="!projectId" @click="openCreate">新增字段</el-button>
      <el-button :disabled="!projectId" @click="handleReset">恢复默认</el-button>
    </div>
    <el-table :data="fields" stripe max-height="360">
      <el-table-column prop="label" label="显示名称" min-width="120" />
      <el-table-column prop="key" label="字段键" width="120" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">{{ fieldTypes.find(t => t.value === row.field_type)?.label || row.field_type }}</template>
      </el-table-column>
      <el-table-column label="列表" width="60" align="center">
        <template #default="{ row }"><el-tag :type="row.show_in_list ? 'success' : 'info'" size="small">{{ row.show_in_list ? '是' : '否' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="筛选" width="60" align="center">
        <template #default="{ row }"><el-tag :type="row.show_in_filter ? 'success' : 'info'" size="small">{{ row.show_in_filter ? '是' : '否' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="模糊" width="60" align="center">
        <template #default="{ row }"><el-tag :type="row.searchable ? 'success' : 'info'" size="small">{{ row.searchable ? '是' : '否' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="!row.is_system" link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="close">关闭</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="editVisible" :title="editing.id ? '编辑字段' : '新增字段'" width="520px" append-to-body>
    <el-form label-width="100px">
      <el-form-item label="显示名称" required>
        <el-input v-model="editing.label" placeholder="如：标号、模块、前置条件" />
      </el-form-item>
      <el-form-item v-if="!editing.is_system" label="字段键">
        <el-input v-model="editing.key" placeholder="留空则自动生成" />
      </el-form-item>
      <el-form-item v-if="!editing.is_system" label="字段类型">
        <el-select v-model="editing.field_type" style="width:100%">
          <el-option v-for="t in fieldTypes" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="editing.field_type === 'select'" label="选项">
        <el-input v-model="optionsText" type="textarea" :rows="4" placeholder="每行一个选项" />
      </el-form-item>
      <el-form-item label="必填"><el-switch v-model="editing.required" /></el-form-item>
      <el-form-item label="列表展示"><el-switch v-model="editing.show_in_list" /></el-form-item>
      <el-form-item label="筛选展示"><el-switch v-model="editing.show_in_filter" /></el-form-item>
      <el-form-item label="模糊匹配"><el-switch v-model="editing.searchable" /></el-form-item>
      <p class="field-tip">开启后，该字段在筛选时使用模糊匹配（包含即可）</p>
    </el-form>
    <template #footer>
      <el-button @click="editVisible = false">取消</el-button>
      <el-button type="primary" @click="saveField">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint { margin: 0 0 12px; font-size: 13px; color: #9aa0a6; line-height: 1.6; }
.hint strong { color: #cbd5e1; }
.field-tip { margin: -8px 0 0; font-size: 12px; color: #6b7280; }
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>

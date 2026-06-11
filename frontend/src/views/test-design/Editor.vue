<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getProjects, getRequirements, getTestPoints,
  createTestPoint, updateTestPoint, deleteTestPoint, aiGenerateCases,
} from '@/api'

const projects = ref<{ id: number; name: string }[]>([])
const requirements = ref<{ id: number; name: string }[]>([])
const points = ref<Record<string, unknown>[]>([])
const projectId = ref<number | null>(null)
const requirementId = ref<number | null>(null)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ name: '', description: '', point_type: 'functional', design_strategy: 'default', requirement: 0 })

async function loadRequirements() {
  if (!projectId.value) return
  const res = await getRequirements({ project: projectId.value })
  requirements.value = res.data.results ?? res.data
}

async function loadPoints() {
  const params: Record<string, unknown> = {}
  if (requirementId.value) params.requirement = requirementId.value
  else if (projectId.value) {
    const reqRes = await getRequirements({ project: projectId.value })
    const reqs = reqRes.data.results ?? reqRes.data
    if (!reqs.length) { points.value = []; return }
    params.requirement = reqs.map((r: { id: number }) => r.id).join(',')
  }
  const res = await getTestPoints(requirementId.value ? { requirement: requirementId.value } : {})
  points.value = res.data.results ?? res.data
}

function openCreate() {
  if (!requirementId.value) { ElMessage.warning('请先选择需求'); return }
  editingId.value = null
  form.value = { name: '', description: '', point_type: 'functional', design_strategy: 'default', requirement: requirementId.value }
  dialogVisible.value = true
}

function openEdit(row: Record<string, unknown>) {
  editingId.value = row.id as number
  form.value = { ...row } as typeof form.value
  dialogVisible.value = true
}

async function savePoint() {
  if (!form.value.name) { ElMessage.warning('请填写名称'); return }
  if (editingId.value) {
    await updateTestPoint(editingId.value, form.value)
    ElMessage.success('更新成功')
  } else {
    await createTestPoint(form.value)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  loadPoints()
}

async function handleDelete(row: { id: number; name: string }) {
  await ElMessageBox.confirm(`删除测试点「${row.name}」？`)
  await deleteTestPoint(row.id)
  ElMessage.success('已删除')
  loadPoints()
}

async function genCases(row: { id: number }) {
  const res = await aiGenerateCases(row.id)
  ElMessage.success(`已生成 ${res.data.test_cases?.length || 0} 条用例，请到用例工厂查看`)
}

onMounted(async () => {
  const res = await getProjects()
  projects.value = res.data.results ?? res.data
  projectId.value = projects.value[0]?.id ?? null
  await loadRequirements()
  await loadPoints()
})
</script>

<template>
  <div>
    <div class="toolbar page-card">
      <el-select v-model="projectId" placeholder="项目" style="width:180px" @change="loadRequirements(); loadPoints()">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-select v-model="requirementId" placeholder="全部需求" clearable style="width:220px" @change="loadPoints">
        <el-option v-for="r in requirements" :key="r.id" :label="r.name" :value="r.id" />
      </el-select>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon> 新增测试点</el-button>
    </div>

    <div class="page-card">
      <el-table :data="points" stripe>
        <el-table-column prop="name" label="测试点" min-width="200" />
        <el-table-column prop="requirement_name" label="关联需求" width="160" />
        <el-table-column prop="point_type" label="类型" width="100" />
        <el-table-column prop="design_strategy" label="策略" width="100" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="genCases(row)">生成用例</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑测试点' : '新增测试点'" width="520px">
      <el-form label-width="90px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.point_type" style="width:100%">
            <el-option label="功能测试" value="functional" />
            <el-option label="边界测试" value="boundary" />
            <el-option label="异常测试" value="exception" />
            <el-option label="安全测试" value="security" />
          </el-select>
        </el-form-item>
        <el-form-item label="策略">
          <el-select v-model="form.design_strategy" style="width:100%">
            <el-option label="等价类" value="equivalence" />
            <el-option label="边界值" value="boundary" />
            <el-option label="场景法" value="scenario" />
            <el-option label="状态迁移" value="state" />
            <el-option label="综合" value="default" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePoint">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
</style>

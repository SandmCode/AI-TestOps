<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getProjects,
  getTestPointTree,
  createTestPoint,
  updateTestPoint,
  deleteTestPoint,
} from '@/api'

interface TreeNode {
  id: number | string
  label: string
  type?: string
  module?: string
  description?: string
  point_type?: string
  children?: TreeNode[]
}

const router = useRouter()
const projects = ref<{ id: number; name: string }[]>([])
const projectId = ref<number | null>(null)
const rawTree = ref<TreeNode[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)

const form = reactive({
  module: '',
  name: '',
  description: '',
  point_type: 'functional' as 'functional' | 'boundary' | 'exception' | 'security',
})

const pointTypeLabel: Record<string, string> = {
  functional: '功能',
  boundary: '边界',
  exception: '异常',
  security: '安全',
}

const typeColor: Record<string, string> = {
  functional: '#3b82f6',
  boundary: '#f59e0b',
  exception: '#ef4444',
  security: '#8b5cf6',
}

function isModuleNode(data: TreeNode) {
  return data.type === 'module'
}

function isPointNode(data: TreeNode) {
  return typeof data.id === 'number'
}

const treeData = computed(() => rawTree.value)

const totalCount = computed(() => {
  let n = 0
  for (const mod of rawTree.value) {
    n += mod.children?.length ?? 0
  }
  return n
})

async function loadTree() {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await getTestPointTree({ project: projectId.value })
    rawTree.value = res.data
  } finally {
    loading.value = false
  }
}

function resetForm() {
  editingId.value = null
  form.module = ''
  form.name = ''
  form.description = ''
  form.point_type = 'functional'
}

function openCreate(module = '') {
  resetForm()
  form.module = module
  dialogVisible.value = true
}

function openEdit(data: TreeNode) {
  if (!isPointNode(data)) return
  editingId.value = data.id as number
  form.module = data.module || ''
  form.name = data.label
  form.description = data.description || ''
  form.point_type = (data.point_type as typeof form.point_type) || 'functional'
  dialogVisible.value = true
}

async function savePoint() {
  if (!projectId.value) return
  if (!form.name.trim()) {
    ElMessage.warning('请填写测试点名称')
    return
  }
  const payload = {
    project: projectId.value,
    module: form.module.trim(),
    name: form.name.trim(),
    description: form.description.trim(),
    point_type: form.point_type,
  }
  if (editingId.value) {
    await updateTestPoint(editingId.value, {
      name: payload.name,
      description: payload.description,
      point_type: payload.point_type,
    })
    ElMessage.success('已更新')
  } else {
    await createTestPoint(payload)
    ElMessage.success('已新增')
  }
  dialogVisible.value = false
  await loadTree()
}

async function handleDelete(data: TreeNode) {
  if (!isPointNode(data)) return
  await ElMessageBox.confirm(`确定删除测试点「${data.label}」？关联用例也会删除。`, '删除确认', { type: 'warning' })
  await deleteTestPoint(data.id as number)
  ElMessage.success('已删除')
  await loadTree()
}

function goGenerateCases() {
  router.push({ path: '/test-case-factory/manage', query: { aiGenerate: '1', project: String(projectId.value) } })
}

watch(projectId, loadTree)
onMounted(async () => {
  const res = await getProjects()
  projects.value = res.data.results ?? res.data
  projectId.value = projects.value[0]?.id ?? null
})
</script>

<template>
  <div class="testpoint-page">
    <div class="toolbar page-card">
      <el-select v-model="projectId" placeholder="选择项目" style="width:220px">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" @click="openCreate()">
        <el-icon><Plus /></el-icon> 新增测试点
      </el-button>
      <el-button type="primary" @click="goGenerateCases">
        <el-icon><MagicStick /></el-icon> AI 生成用例
      </el-button>
      <div class="legend">
        <span><i class="dot" style="background:#3b82f6" />功能</span>
        <span><i class="dot" style="background:#f59e0b" />边界</span>
        <span><i class="dot" style="background:#ef4444" />异常</span>
        <span class="count">共 {{ totalCount }} 个测试点</span>
      </div>
    </div>

    <div class="flow-hint page-card">
      从文档解析后保存到此<strong>测试点树</strong>。确认测试点后，去「测试用例」一键 AI 生成用例。
    </div>

    <div v-loading="loading" class="page-card tree-panel">
      <el-tree
        v-if="treeData.length"
        :data="treeData"
        :props="{ label: 'label', children: 'children' }"
        default-expand-all
        node-key="id"
        :expand-on-click-node="false"
      >
        <template #default="{ data }">
          <div class="tree-row">
            <div class="tree-label">
              <el-icon v-if="isModuleNode(data)" class="mod-icon"><Folder /></el-icon>
              <i v-else class="type-dot" :style="{ background: typeColor[data.point_type || 'functional'] }" />
              <span class="name" :class="{ module: isModuleNode(data) }">{{ data.label }}</span>
              <el-tag v-if="isPointNode(data)" size="small" type="info" class="type-tag">
                {{ pointTypeLabel[data.point_type || 'functional'] }}
              </el-tag>
              <span v-if="isPointNode(data) && data.description" class="desc">{{ data.description }}</span>
            </div>
            <div class="tree-actions">
              <template v-if="isModuleNode(data)">
                <el-button link type="primary" size="small" @click.stop="openCreate(data.label)">新增</el-button>
              </template>
              <template v-else>
                <el-button link type="primary" size="small" @click.stop="openEdit(data)">编辑</el-button>
                <el-button link type="danger" size="small" @click.stop="handleDelete(data)">删除</el-button>
              </template>
            </div>
          </div>
        </template>
      </el-tree>
      <el-empty v-else description="暂无测试点，请先在「需求解析」中提取并保存" />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑测试点' : '新增测试点'"
      width="520px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form label-width="88px">
        <el-form-item label="模块">
          <el-input v-model="form.module" placeholder="如：订单模块" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="测试点名称" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.point_type">
            <el-radio value="functional">功能</el-radio>
            <el-radio value="boundary">边界</el-radio>
            <el-radio value="exception">异常</el-radio>
            <el-radio value="security">安全</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="4" placeholder="测试点描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePoint">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  margin-bottom: 16px; padding: 14px 18px;
}
.legend {
  display: flex; align-items: center; gap: 16px; margin-left: auto;
  font-size: 12px; color: #9aa0a6; flex-wrap: wrap;
}
.legend span { display: flex; align-items: center; gap: 6px; }
.legend .count { color: #6b7280; margin-left: 4px; }
.dot, .type-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.flow-hint {
  margin-bottom: 12px; padding: 10px 16px; font-size: 13px; color: #9aa0a6; line-height: 1.6;
}
.flow-hint strong { color: #cbd5e1; }
.tree-row {
  flex: 1; display: flex; align-items: center; justify-content: space-between;
  gap: 12px; min-width: 0; padding-right: 8px;
}
.tree-label {
  display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;
}
.mod-icon { color: #8b5cf6; font-size: 16px; flex-shrink: 0; }
.name { color: #e8eaed; font-size: 14px; }
.name.module { font-weight: 600; font-size: 15px; }
.type-tag { flex-shrink: 0; }
.desc {
  color: #6b7280; font-size: 12px; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; max-width: 360px;
}
.tree-actions { flex-shrink: 0; opacity: 0; transition: opacity 0.15s; }
:deep(.el-tree-node__content:hover) .tree-actions { opacity: 1; }
:deep(.el-tree) { background: transparent; color: #e8eaed; --el-tree-node-hover-bg-color: #1a2744; }
:deep(.el-tree-node__content) { height: auto; min-height: 36px; padding: 4px 0; border-radius: 6px; }
</style>

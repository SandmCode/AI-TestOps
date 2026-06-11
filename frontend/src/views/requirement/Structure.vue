<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getProjects,
  getRequirementTree,
  createRequirement,
  updateRequirement,
  deleteRequirement,
} from '@/api'

interface TreeNode {
  id: number | string
  label: string
  type?: string
  module?: string
  description?: string
  children?: TreeNode[]
}

const router = useRouter()
const projects = ref<{ id: number; name: string }[]>([])
const projectId = ref<number | null>(null)
const rawTree = ref<TreeNode[]>([])
const loading = ref(false)
const filterType = ref('')
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)

const form = reactive({
  module: '',
  name: '',
  description: '',
  requirement_type: 'feature' as 'feature' | 'constraint' | 'exception',
})

const typeColor: Record<string, string> = {
  feature: '#3b82f6',
  constraint: '#f59e0b',
  exception: '#ef4444',
  module: '#8b5cf6',
}

const typeLabel: Record<string, string> = {
  feature: '功能需求',
  constraint: '约束',
  exception: '异常场景',
}

function isModuleNode(data: TreeNode) {
  return data.type === 'module'
}

function isReqNode(data: TreeNode) {
  return typeof data.id === 'number'
}

function filterTree(nodes: TreeNode[]): TreeNode[] {
  if (!filterType.value) return nodes
  return nodes
    .map((mod) => {
      if (!isModuleNode(mod)) return mod
      const children = (mod.children || []).filter((c) => c.type === filterType.value)
      if (!children.length) return null
      return { ...mod, children }
    })
    .filter(Boolean) as TreeNode[]
}

const treeData = computed(() => filterTree(rawTree.value))

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
    const res = await getRequirementTree({ project: projectId.value })
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
  form.requirement_type = 'feature'
}

function openCreate(module = '') {
  resetForm()
  form.module = module
  dialogVisible.value = true
}

function openEdit(data: TreeNode) {
  if (!isReqNode(data)) return
  editingId.value = data.id as number
  form.module = data.module || ''
  form.name = data.label
  form.description = data.description || ''
  form.requirement_type = (data.type as typeof form.requirement_type) || 'feature'
  dialogVisible.value = true
}

async function saveRequirement() {
  if (!projectId.value) return
  if (!form.name.trim()) {
    ElMessage.warning('请填写需求名称')
    return
  }
  const payload = {
    project: projectId.value,
    module: form.module.trim(),
    name: form.name.trim(),
    description: form.description.trim(),
    requirement_type: form.requirement_type,
  }
  if (editingId.value) {
    await updateRequirement(editingId.value, payload)
    ElMessage.success('已更新')
  } else {
    await createRequirement(payload)
    ElMessage.success('已新增')
  }
  dialogVisible.value = false
  await loadTree()
}

async function handleDelete(data: TreeNode) {
  if (!isReqNode(data)) return
  await ElMessageBox.confirm(`确定删除「${data.label}」？关联测试点也会删除。`, '删除确认', { type: 'warning' })
  await deleteRequirement(data.id as number)
  ElMessage.success('已删除')
  await loadTree()
}

function goDesign(reqId?: number) {
  const query: Record<string, string> = {}
  if (projectId.value) query.project = String(projectId.value)
  if (reqId) query.requirementId = String(reqId)
  router.push({ path: '/test-design/generator', query })
}

watch(projectId, loadTree)
onMounted(async () => {
  const res = await getProjects()
  projects.value = res.data.results ?? res.data
  projectId.value = projects.value[0]?.id ?? null
})
</script>

<template>
  <div class="structure-page">
    <div class="toolbar page-card">
      <el-select v-model="projectId" placeholder="选择项目" style="width:220px">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-select v-model="filterType" placeholder="全部类型" clearable style="width:130px">
        <el-option label="功能需求" value="feature" />
        <el-option label="约束" value="constraint" />
        <el-option label="异常场景" value="exception" />
      </el-select>
      <el-button type="primary" @click="openCreate()">
        <el-icon><Plus /></el-icon> 新增需求
      </el-button>
      <el-button type="primary" @click="goDesign()">
        <el-icon><Aim /></el-icon> 去设计测试点
      </el-button>
      <div class="legend">
        <span><i class="dot" style="background:#3b82f6" />功能需求</span>
        <span><i class="dot" style="background:#f59e0b" />约束</span>
        <span><i class="dot" style="background:#ef4444" />异常场景</span>
        <span class="count">共 {{ totalCount }} 条需求</span>
      </div>
    </div>

    <div class="flow-hint page-card">
      此处管理<strong>需求条目</strong>（测什么）。确认后点击「去设计测试点」，在测试设计模块用策略推导出<strong>测试点</strong>（怎么测）。
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
              <span
                v-else-if="data.type"
                class="type-dot"
                :style="{ background: typeColor[data.type] || '#6b7280' }"
              />
              <span class="name" :class="{ module: isModuleNode(data) }">{{ data.label }}</span>
              <el-tag v-if="!isModuleNode(data) && data.type" size="small" type="info" class="type-tag">
                {{ typeLabel[data.type] || data.type }}
              </el-tag>
              <span v-if="data.description && !isModuleNode(data)" class="desc">{{ data.description }}</span>
            </div>
            <div class="tree-actions" @click.stop>
              <template v-if="isModuleNode(data)">
                <el-button link type="primary" size="small" @click="openCreate(data.label)">新增</el-button>
              </template>
              <template v-else-if="isReqNode(data)">
                <el-button link type="primary" size="small" @click="goDesign(data.id as number)">设计测试点</el-button>
                <el-button link type="primary" size="small" @click="openEdit(data)">编辑</el-button>
                <el-button link type="danger" size="small" @click="handleDelete(data)">删除</el-button>
              </template>
            </div>
          </div>
        </template>
      </el-tree>
      <el-empty v-else description="暂无需求条目，请先在「需求解析」中生成或手动新增" />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑需求' : '新增需求'"
      width="520px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form label-width="88px">
        <el-form-item label="类型" required>
          <el-radio-group v-model="form.requirement_type">
            <el-radio value="feature">功能需求</el-radio>
            <el-radio value="constraint">约束</el-radio>
            <el-radio value="exception">异常场景</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="模块">
          <el-input v-model="form.module" placeholder="如：订单模块" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="需求名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="4" placeholder="详细描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRequirement">保存</el-button>
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

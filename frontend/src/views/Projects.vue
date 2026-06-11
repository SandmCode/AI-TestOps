<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getProjects,
  createProject,
  updateProject,
  deleteProject,
  batchDeleteProjects,
} from '@/api'
import CardCheckbox from '@/components/CardCheckbox.vue'

interface ProjectItem {
  id: number
  name: string
  description: string
  owner: string
  document_count: number
  testcase_count: number
  created_at: string
  updated_at: string
}

const projects = ref<ProjectItem[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const selectedMap = reactive<Record<number, boolean>>({})
const showFilter = ref(true)

const filters = ref({
  search: '',
  owner: '',
  created_after: '',
  created_before: '',
})

const form = ref({
  name: '',
  description: '',
  owner: '',
})

const selectedIds = computed(() => projects.value.filter((p) => selectedMap[p.id]).map((p) => p.id))

const isAllSelected = computed({
  get: () => projects.value.length > 0 && projects.value.every((p) => selectedMap[p.id]),
  set: (val: boolean) => {
    projects.value.forEach((p) => { selectedMap[p.id] = val })
  },
})

const selectedCount = computed(() => selectedIds.value.length)

function resetSelection(items: { id: number }[]) {
  Object.keys(selectedMap).forEach((k) => delete selectedMap[Number(k)])
  items.forEach((item) => { selectedMap[item.id] = false })
}

function buildParams() {
  const params: Record<string, unknown> = { page_size: 500 }
  if (filters.value.search.trim()) params.search = filters.value.search.trim()
  if (filters.value.owner.trim()) params.owner = filters.value.owner.trim()
  if (filters.value.created_after) params.created_after = filters.value.created_after
  if (filters.value.created_before) params.created_before = filters.value.created_before
  return params
}

async function loadData() {
  loading.value = true
  try {
    const res = await getProjects(buildParams())
    projects.value = res.data.results ?? res.data
    resetSelection(projects.value)
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.value = { search: '', owner: '', created_after: '', created_before: '' }
  loadData()
}

function openCreate() {
  editingId.value = null
  form.value = { name: '', description: '', owner: '' }
  dialogVisible.value = true
}

function openEdit(row: ProjectItem) {
  editingId.value = row.id
  form.value = {
    name: row.name,
    description: row.description,
    owner: row.owner,
  }
  dialogVisible.value = true
}

async function saveProject() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请填写项目名称')
    return
  }
  if (editingId.value) {
    await updateProject(editingId.value, form.value)
    ElMessage.success('更新成功')
  } else {
    await createProject(form.value)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  loadData()
}

async function handleDelete(row: ProjectItem) {
  await ElMessageBox.confirm(
    `确定删除项目「${row.name}」？关联的文档和用例也会一并删除。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
  await deleteProject(row.id)
  ElMessage.success('删除成功')
  loadData()
}

async function handleBatchDelete() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先选择要删除的项目')
    return
  }
  await ElMessageBox.confirm(
    `确定批量删除选中的 ${selectedIds.value.length} 个项目？关联数据也会一并删除，此操作不可恢复。`,
    '批量删除确认',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  await batchDeleteProjects(selectedIds.value)
  ElMessage.success(`已删除 ${selectedIds.value.length} 个项目`)
  loadData()
}

function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ') ?? '-'
}

onMounted(loadData)
</script>

<template>
  <div>
    <h1 class="page-title">项目管理</h1>

    <div class="filter-card">
      <div class="filter-header">
        <span class="filter-title"><el-icon><Filter /></el-icon> 筛选条件</span>
        <el-button link type="primary" @click="showFilter = !showFilter">
          {{ showFilter ? '收起' : '展开' }}
        </el-button>
      </div>
      <el-collapse-transition>
        <div v-show="showFilter" class="filter-body">
          <el-row :gutter="16">
            <el-col :xs="24" :sm="12" :md="6">
              <div class="filter-item">
                <label>项目名称 / 描述</label>
                <el-input v-model="filters.search" placeholder="搜索项目名称或描述" clearable />
              </div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <div class="filter-item">
                <label>项目负责人</label>
                <el-input v-model="filters.owner" placeholder="输入负责人" clearable />
              </div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <div class="filter-item">
                <label>创建时间（起）</label>
                <el-date-picker v-model="filters.created_after" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" style="width:100%" />
              </div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <div class="filter-item">
                <label>创建时间（止）</label>
                <el-date-picker v-model="filters.created_before" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" style="width:100%" />
              </div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6" class="filter-actions">
              <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> 查询</el-button>
              <el-button @click="resetFilters"><el-icon><RefreshLeft /></el-icon> 重置</el-button>
            </el-col>
          </el-row>
        </div>
      </el-collapse-transition>
    </div>

    <div class="page-card list-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <label class="select-all">
            <CardCheckbox
              v-model="isAllSelected"
              :indeterminate="selectedCount > 0 && selectedCount < projects.length"
            />
            <span>全选</span>
          </label>
          <span v-if="selectedCount" class="selected-tip">已选 {{ selectedCount }} 项</span>
          <el-button v-if="selectedCount" type="danger" plain round @click="handleBatchDelete">
            <el-icon><Delete /></el-icon> 批量删除
          </el-button>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" round @click="openCreate">
            <el-icon><Plus /></el-icon> 新增项目
          </el-button>
        </div>
      </div>

      <div v-loading="loading" class="project-list">
        <div
          v-for="row in projects"
          :key="row.id"
          class="project-item"
          :class="{ selected: selectedMap[row.id] }"
        >
          <div class="checkbox-wrap" @click.stop @mousedown.stop>
            <CardCheckbox v-model="selectedMap[row.id]" />
          </div>
          <div class="item-body" @click="openEdit(row)">
            <div class="item-header">
              <span class="item-id">#{{ row.id }}</span>
              <strong class="item-name">{{ row.name }}</strong>
              <el-tag v-if="row.owner" size="small" effect="plain" type="info">{{ row.owner }}</el-tag>
            </div>
            <p v-if="row.description" class="item-desc">{{ row.description }}</p>
            <p v-else class="item-desc empty">暂无项目描述</p>
            <div class="item-meta">
              <span class="meta-badge doc">
                <el-icon><Document /></el-icon>
                {{ row.document_count }} 文档
              </span>
              <span class="meta-badge case">
                <el-icon><List /></el-icon>
                {{ row.testcase_count }} 用例
              </span>
              <span class="meta-time">
                <el-icon><Clock /></el-icon>
                {{ formatTime(row.created_at) }}
              </span>
            </div>
          </div>
          <div class="item-actions">
            <el-tooltip content="编辑" placement="top">
              <button class="action-btn edit" @click="openEdit(row)">
                <el-icon><EditPen /></el-icon>
              </button>
            </el-tooltip>
            <el-tooltip content="删除" placement="top">
              <button class="action-btn delete" @click="handleDelete(row)">
                <el-icon><Delete /></el-icon>
              </button>
            </el-tooltip>
          </div>
        </div>

        <el-empty v-if="!projects.length && !loading" description="暂无项目，点击新增项目开始" />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑项目' : '新增项目'" width="520px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="项目名称" required>
          <el-input v-model="form.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input v-model="form.description" type="textarea" :rows="4" placeholder="请输入项目描述" />
        </el-form-item>
        <el-form-item label="项目负责人">
          <el-input v-model="form.owner" placeholder="请输入负责人姓名" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveProject">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.filter-card {
  background: #1a2332;
  border: 1px solid #2a3544;
  border-radius: 12px;
  padding: 16px 20px;
}

.filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: #e8eaed;
}

.filter-body { margin-top: 16px; }

.filter-item { margin-bottom: 12px; }

.filter-item label {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}

.filter-actions {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding-bottom: 12px;
}

.list-card {
  margin-top: 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.select-all {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  color: #9aa0a6;
  font-size: 14px;
}

.select-all:hover {
  color: #e8eaed;
}

.selected-tip {
  font-size: 13px;
  color: #3b82f6;
  padding: 4px 10px;
  background: #3b82f614;
  border-radius: 20px;
}

.project-list {
  min-height: 120px;
}

.project-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 18px;
  margin-bottom: 10px;
  background: #141c28;
  border: 1px solid #2a3544;
  border-radius: 10px;
  transition: all 0.2s;
}

.project-item:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 12px rgba(59, 130, 246, 0.08);
}

.project-item.selected {
  border-color: #3b82f6;
  background: #1a2744;
}

.checkbox-wrap {
  flex-shrink: 0;
  margin-top: 4px;
  padding: 2px;
}

.item-body {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.item-id {
  font-size: 12px;
  color: #6b7280;
  min-width: 24px;
}

.item-name {
  color: #f3f4f6;
  font-size: 16px;
}

.item-desc {
  margin-top: 8px;
  font-size: 13px;
  color: #9aa0a6;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-desc.empty {
  color: #4b5563;
  font-style: italic;
}

.item-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.meta-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
}

.meta-badge.doc {
  color: #8b5cf6;
  background: #8b5cf618;
  border: 1px solid #8b5cf633;
}

.meta-badge.case {
  color: #10b981;
  background: #10b98118;
  border: 1px solid #10b98133;
}

.meta-time {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #6b7280;
  margin-left: auto;
}

.item-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  margin-top: 2px;
}

.action-btn {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.2s;
  background: transparent;
}

.action-btn.edit {
  color: #3b82f6;
  border-color: #3b82f633;
  background: #3b82f614;
}

.action-btn.edit:hover {
  background: #3b82f6;
  color: #fff;
}

.action-btn.delete {
  color: #ef4444;
  border-color: #ef444433;
  background: #ef444414;
}

.action-btn.delete:hover {
  background: #ef4444;
  color: #fff;
}

@media (max-width: 768px) {
  .item-meta {
    flex-direction: column;
    align-items: flex-start;
  }

  .meta-time {
    margin-left: 0;
  }

  .item-actions {
    flex-direction: column;
  }
}
</style>

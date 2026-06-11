<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getProjects, getKnowledgeItems, createKnowledgeItem, deleteKnowledgeItem,
} from '@/api'

const projects = ref<{ id: number; name: string }[]>([])
const items = ref<{ id: number; title: string; content: string; category: string; tags: string[] }[]>([])
const category = ref('')
const projectId = ref<number | null>(null)
const dialogVisible = ref(false)
const form = ref({ title: '', content: '', category: 'experience', project: null as number | null })

const categories = [
  { value: 'experience', label: '测试经验库' },
  { value: 'bug', label: 'Bug知识库' },
  { value: 'history', label: '历史用例库' },
]

async function loadData() {
  const params: Record<string, unknown> = {}
  if (category.value) params.category = category.value
  if (projectId.value) params.project = projectId.value
  const [itemRes, projRes] = await Promise.all([getKnowledgeItems(params), getProjects()])
  items.value = itemRes.data.results ?? itemRes.data
  projects.value = projRes.data.results ?? projRes.data
}

function openCreate() {
  form.value = { title: '', content: '', category: 'experience', project: projectId.value }
  dialogVisible.value = true
}

async function saveItem() {
  if (!form.value.title || !form.value.content) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  await createKnowledgeItem(form.value)
  ElMessage.success('添加成功')
  dialogVisible.value = false
  loadData()
}

async function handleDelete(row: { id: number; title: string }) {
  await ElMessageBox.confirm(`删除「${row.title}」？`, '确认')
  await deleteKnowledgeItem(row.id)
  ElMessage.success('已删除')
  loadData()
}

onMounted(loadData)
</script>

<template>
  <div>
    <div class="toolbar page-card">
      <el-select v-model="category" placeholder="全部分类" clearable style="width:160px" @change="loadData">
        <el-option v-for="c in categories" :key="c.value" :label="c.label" :value="c.value" />
      </el-select>
      <el-select v-model="projectId" placeholder="全部项目" clearable style="width:180px" @change="loadData">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon> 添加知识</el-button>
    </div>

    <div class="page-card">
      <el-table :data="items" stripe>
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column label="分类" width="120">
          <template #default="{ row }">
            {{ categories.find(c => c.value === row.category)?.label || row.category }}
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="300" show-overflow-tooltip />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" title="添加知识条目" width="520px">
      <el-form label-width="80px">
        <el-form-item label="分类">
          <el-select v-model="form.category" style="width:100%">
            <el-option v-for="c in categories" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="5" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveItem">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
</style>

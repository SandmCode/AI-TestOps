<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getTestReports, createTestReport, deleteTestReport } from '@/api'
import { openReportUrl } from '@/utils/reportPrompt'

interface ReportItem {
  id: number
  name: string
  report_type: string
  source_type: string
  summary: string
  pass_rate: number
  total_cases: number
  passed_cases: number
  report_url: string
  meta?: Record<string, unknown>
  created_at: string
}

const reports = ref<ReportItem[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const filterSource = ref('')

const form = ref({
  name: '',
  report_type: 'functional',
  summary: '',
  pass_rate: 0,
  total_cases: 0,
  passed_cases: 0,
  report_url: '',
})

const typeMap: Record<string, string> = {
  functional: '功能测试',
  api: '接口测试',
  performance: '性能测试',
  security: '安全测试',
  web: 'Web自动化',
}

const sourceMap: Record<string, string> = {
  manual: '手动',
  automation: '接口自动化',
  security: '安全扫描',
  stress: '接口压测',
}

async function loadData() {
  loading.value = true
  try {
    const params = filterSource.value ? { source_type: filterSource.value } : undefined
    const res = await getTestReports(params)
    reports.value = res.data.results ?? res.data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = { name: '', report_type: 'functional', summary: '', pass_rate: 0, total_cases: 0, passed_cases: 0, report_url: '' }
  dialogVisible.value = true
}

async function saveReport() {
  if (!form.value.name) {
    ElMessage.warning('请填写报告名称')
    return
  }
  await createTestReport(form.value)
  ElMessage.success('创建成功')
  dialogVisible.value = false
  loadData()
}

async function handleDelete(row: ReportItem) {
  await deleteTestReport(row.id)
  ElMessage.success('删除成功')
  loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="reports-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">测试报告</h1>
        <p class="page-desc">
          接口自动化、安全扫描、压测完成后可生成 Allure 风格报告；支持在线查看与历史归档。
        </p>
      </div>
    </div>

    <div class="page-card">
      <div class="toolbar">
        <el-select v-model="filterSource" placeholder="全部来源" clearable style="width:160px" @change="loadData">
          <el-option v-for="(label, key) in sourceMap" :key="key" :label="label" :value="key" />
        </el-select>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 手动新增
        </el-button>
      </div>

      <el-table :data="reports" v-loading="loading" stripe>
        <el-table-column prop="name" label="报告名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="source_type" label="来源" width="120">
          <template #default="{ row }">{{ sourceMap[row.source_type] || row.source_type }}</template>
        </el-table-column>
        <el-table-column prop="report_type" label="类型" width="100">
          <template #default="{ row }">{{ typeMap[row.report_type] || row.report_type }}</template>
        </el-table-column>
        <el-table-column prop="pass_rate" label="通过率" width="110">
          <template #default="{ row }">
            <el-progress :percentage="row.pass_rate" :stroke-width="8" style="width:80px" />
          </template>
        </el-table-column>
        <el-table-column label="用例" width="100">
          <template #default="{ row }">{{ row.passed_cases }}/{{ row.total_cases }}</template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ row.created_at?.slice(0, 19).replace('T', ' ') }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.report_url" size="small" type="primary" link @click="openReportUrl(row.report_url)">
              查看 Allure 报告
            </el-button>
            <el-popconfirm title="确定删除？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button size="small" type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" title="手动新增报告" width="520px">
      <el-form label-width="90px">
        <el-form-item label="报告名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="报告类型">
          <el-select v-model="form.report_type" style="width:100%">
            <el-option label="功能测试" value="functional" />
            <el-option label="接口测试" value="api" />
            <el-option label="性能测试" value="performance" />
            <el-option label="安全测试" value="security" />
          </el-select>
        </el-form-item>
        <el-form-item label="总用例数"><el-input-number v-model="form.total_cases" :min="0" /></el-form-item>
        <el-form-item label="通过数"><el-input-number v-model="form.passed_cases" :min="0" /></el-form-item>
        <el-form-item label="通过率"><el-input-number v-model="form.pass_rate" :min="0" :max="100" /></el-form-item>
        <el-form-item label="报告链接"><el-input v-model="form.report_url" placeholder="可选，外部 Allure 地址" /></el-form-item>
        <el-form-item label="摘要"><el-input v-model="form.summary" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveReport">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.reports-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-desc {
  color: #9aa0a6;
  font-size: 14px;
  margin-top: 6px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>

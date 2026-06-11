<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSystemInfo, systemMaintain } from '@/api'
import { clearAllWorkbenchCache } from '@/composables/useAnalysisSession'

interface SystemStats {
  projects: number
  analysis_records: number
  test_reports: number
  stress_runs: number
  execution_runs: number
  async_tasks: number
  chunk_sessions: number
}

const stats = ref<SystemStats | null>(null)
const loading = ref(false)
const acting = ref('')

const statItems = [
  { key: 'projects', label: '项目', color: '#3b82f6' },
  { key: 'analysis_records', label: '分析记录', color: '#8b5cf6' },
  { key: 'test_reports', label: '测试报告', color: '#10b981' },
  { key: 'stress_runs', label: '压测记录', color: '#f59e0b' },
  { key: 'execution_runs', label: '执行记录', color: '#06b6d4' },
] as const

async function fetchStats() {
  loading.value = true
  try {
    const res = await getSystemInfo()
    stats.value = res.data
  } finally {
    loading.value = false
  }
}

async function runAction(
  action: string,
  title: string,
  message: string,
  confirmType: 'warning' | 'error' = 'warning',
) {
  try {
    await ElMessageBox.confirm(message, title, {
      confirmButtonText: '确认执行',
      cancelButtonText: '取消',
      type: confirmType,
    })
  } catch {
    return
  }
  acting.value = action
  try {
    const res = await systemMaintain(action)
    ElMessage.success(res.data.message || '操作完成')
    await fetchStats()
  } finally {
    acting.value = ''
  }
}

function clearBrowserCache() {
  clearAllWorkbenchCache()
  ElMessage.success('已清空浏览器中的分析页缓存（契约/覆盖率/日志）')
}

onMounted(fetchStats)
</script>

<template>
  <div class="system-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">系统设置</h1>
        <p class="page-desc">查看数据统计，清理或格式化平台数据（AI 配置不会被删除）</p>
      </div>
      <el-button :loading="loading" @click="fetchStats">
        <el-icon><Refresh /></el-icon> 刷新统计
      </el-button>
    </header>

    <section class="stats-section page-card">
      <h3>数据概览</h3>
      <div class="stats-grid">
        <div v-for="item in statItems" :key="item.key" class="stat-item">
          <span class="stat-num" :style="{ color: item.color }">
            {{ stats?.[item.key] ?? '-' }}
          </span>
          <span class="stat-label">{{ item.label }}</span>
        </div>
      </div>
    </section>

    <section class="actions-section">
      <div class="action-card page-card">
        <div class="action-head">
          <el-icon :size="22" color="#8b5cf6"><Delete /></el-icon>
          <div>
            <h4>清理分析记录</h4>
            <p>删除契约测试、覆盖率、日志分析的全部历史记录</p>
          </div>
        </div>
        <el-button
          type="warning"
          plain
          :loading="acting === 'clear_analysis_records'"
          @click="runAction('clear_analysis_records', '清理分析记录', '将删除所有 AI 分析历史记录，此操作不可恢复。')"
        >
          清理分析记录
        </el-button>
      </div>

      <div class="action-card page-card">
        <div class="action-head">
          <el-icon :size="22" color="#10b981"><DocumentCopy /></el-icon>
          <div>
            <h4>清理测试报告</h4>
            <p>删除自动化、安全扫描、压测生成的报告记录</p>
          </div>
        </div>
        <el-button
          type="warning"
          plain
          :loading="acting === 'clear_test_reports'"
          @click="runAction('clear_test_reports', '清理测试报告', '将删除全部测试报告记录，此操作不可恢复。')"
        >
          清理测试报告
        </el-button>
      </div>

      <div class="action-card page-card">
        <div class="action-head">
          <el-icon :size="22" color="#f59e0b"><Timer /></el-icon>
          <div>
            <h4>清理运行记录</h4>
            <p>删除压测、自动化执行、异步任务等运行时数据</p>
          </div>
        </div>
        <el-button
          type="warning"
          plain
          :loading="acting === 'clear_runtime'"
          @click="runAction('clear_runtime', '清理运行记录', '将删除压测与执行记录，不影响项目和用例。')"
        >
          清理运行记录
        </el-button>
      </div>

      <div class="action-card page-card highlight">
        <div class="action-head">
          <el-icon :size="22" color="#ef4444"><RefreshRight /></el-icon>
          <div>
            <h4>一键格式化业务数据</h4>
            <p>清空项目、用例、文档、分析记录、报告等，并重建演示数据（保留 AI 配置）</p>
          </div>
        </div>
        <el-button
          type="danger"
          :loading="acting === 'format_business'"
          @click="runAction(
            'format_business',
            '一键格式化',
            '将删除所有业务数据并恢复为演示环境，AI 配置会保留。此操作不可恢复！',
            'error',
          )"
        >
          一键格式化数据
        </el-button>
      </div>

      <div class="action-card page-card">
        <div class="action-head">
          <el-icon :size="22" color="#60a5fa"><Monitor /></el-icon>
          <div>
            <h4>清空浏览器缓存</h4>
            <p>清除本机保存的契约/覆盖率/日志分析草稿（localStorage）</p>
          </div>
        </div>
        <el-button plain @click="clearBrowserCache">清空本地缓存</el-button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.system-page { max-width: 960px; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  gap: 16px;
}
.page-desc { color: #6b7280; font-size: 14px; margin-top: 6px; }
.stats-section h3 {
  font-size: 14px;
  color: #e8eaed;
  margin-bottom: 16px;
  padding-left: 10px;
  border-left: 3px solid #3b82f6;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
}
.stat-item {
  text-align: center;
  padding: 16px;
  background: #141c28;
  border-radius: 10px;
  border: 1px solid #2a3544;
}
.stat-num { display: block; font-size: 28px; font-weight: 700; line-height: 1.2; }
.stat-label { font-size: 12px; color: #9aa0a6; margin-top: 4px; }
.actions-section { display: flex; flex-direction: column; gap: 14px; }
.action-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.action-card.highlight {
  border-color: #ef444444;
  background: linear-gradient(135deg, #7f1d1d18, #1a2332);
}
.action-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex: 1;
  min-width: 240px;
}
.action-head h4 { color: #f3f4f6; font-size: 15px; margin-bottom: 4px; }
.action-head p { color: #9aa0a6; font-size: 13px; line-height: 1.5; margin: 0; }
</style>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getProjects, getExecutionRuns } from '@/api'

const projects = ref<{ id: number; name: string }[]>([])
const runs = ref<Record<string, unknown>[]>([])
const projectId = ref<number | null>(null)
const selectedRun = ref<Record<string, unknown> | null>(null)

const statusMap: Record<string, { type: string; label: string }> = {
  success: { type: 'success', label: '成功' },
  failed: { type: 'danger', label: '失败' },
  partial: { type: 'warning', label: '部分成功' },
  running: { type: 'info', label: '执行中' },
  pending: { type: 'info', label: '等待中' },
}

async function loadData() {
  const params: Record<string, unknown> = {}
  if (projectId.value) params.project = projectId.value
  const [runRes, projRes] = await Promise.all([getExecutionRuns(params), getProjects()])
  runs.value = runRes.data.results ?? runRes.data
  projects.value = projRes.data.results ?? projRes.data
  selectedRun.value = runs.value[0] || null
}

function selectRun(row: Record<string, unknown>) {
  selectedRun.value = row
}

onMounted(loadData)
</script>

<template>
  <div class="analysis-page">
    <div class="page-card list-panel">
      <div class="panel-head">
        <h3>执行记录</h3>
        <el-select v-model="projectId" placeholder="全部项目" clearable size="small" style="width:160px" @change="loadData">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </div>
      <div
        v-for="run in runs"
        :key="run.id as number"
        class="run-item"
        :class="{ active: selectedRun?.id === run.id }"
        @click="selectRun(run)"
      >
        <strong>{{ run.name }}</strong>
        <el-tag :type="(statusMap[run.status as string]?.type as 'success') || 'info'" size="small">
          {{ statusMap[run.status as string]?.label || run.status }}
        </el-tag>
        <p>{{ run.passed }}/{{ run.total }} 通过 · {{ (run.created_at as string)?.slice(0, 16).replace('T', ' ') }}</p>
      </div>
      <el-empty v-if="!runs.length" description="暂无执行记录，请先在批量执行中运行" />
    </div>

    <div v-if="selectedRun" class="page-card detail-panel">
      <h3>执行详情</h3>
      <div class="stats">
        <div class="stat"><span class="num">{{ selectedRun.total }}</span><span>总数</span></div>
        <div class="stat pass"><span class="num">{{ selectedRun.passed }}</span><span>通过</span></div>
        <div class="stat fail"><span class="num">{{ selectedRun.failed }}</span><span>失败</span></div>
      </div>
      <h4>用例结果</h4>
      <el-table :data="(selectedRun.results as object[]) || []" stripe size="small">
        <el-table-column prop="title" label="用例" min-width="200" />
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="row.passed ? 'success' : 'danger'" size="small">{{ row.passed ? '通过' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="actual" label="实际结果" show-overflow-tooltip />
      </el-table>
      <h4 style="margin-top:20px">AI 分析</h4>
      <div class="ai-box">{{ selectedRun.ai_analysis || '暂无分析' }}</div>
    </div>
  </div>
</template>

<style scoped>
.analysis-page { display: grid; grid-template-columns: 320px 1fr; gap: 16px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
h3, h4 { color: #fff; }
.run-item {
  padding: 12px; margin-bottom: 8px; background: #141c28;
  border: 1px solid #2a3544; border-radius: 8px; cursor: pointer;
}
.run-item.active { border-color: #3b82f6; background: #1a2744; }
.run-item strong { color: #f3f4f6; margin-right: 8px; }
.run-item p { color: #6b7280; font-size: 12px; margin-top: 6px; }
.stats { display: flex; gap: 20px; margin: 16px 0; }
.stat { text-align: center; padding: 16px 24px; background: #141c28; border-radius: 8px; }
.stat .num { display: block; font-size: 28px; font-weight: 700; color: #fff; }
.stat span:last-child { font-size: 12px; color: #6b7280; }
.stat.pass .num { color: #10b981; }
.stat.fail .num { color: #ef4444; }
.ai-box {
  padding: 16px; background: #141c28; border: 1px solid #2a3544;
  border-radius: 8px; color: #9aa0a6; line-height: 1.7; font-size: 14px;
}
</style>

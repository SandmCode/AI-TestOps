<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getProjects, getTestCases, getDocuments, getTestPoints, getTestReports } from '@/api'
import { APP_TITLE } from '@/config/app'

const router = useRouter()

const modules = [
  {
    step: '01',
    title: '需求中心',
    path: '/requirement-center',
    icon: 'Document',
    color: '#8b5cf6',
    gradient: 'linear-gradient(135deg, #8b5cf622, #6366f108)',
    flow: '上传文档 → AI 解析 → 测试点树',
    items: ['需求文档', 'AI 解析', '测试点树'],
  },
  {
    step: '02',
    title: '测试用例',
    path: '/test-case-factory',
    icon: 'List',
    color: '#10b981',
    gradient: 'linear-gradient(135deg, #10b98122, #14b8a608)',
    flow: '选择测试点 → AI 生成用例',
    items: ['用例管理', 'AI 生成'],
  },
  {
    step: '03',
    title: '接口测试',
    path: '/test-execution/doc-parse',
    icon: 'Connection',
    color: '#f59e0b',
    gradient: 'linear-gradient(135deg, #f59e0b22, #ef444408)',
    flow: '文档解析 → 接口自动化',
    items: ['接口文档解析', '接口自动化'],
  },
]

const aiModules = [
  { title: '契约测试', desc: 'OpenAPI 规范校验', path: '/contract-test', icon: 'Tickets', color: '#3b82f6' },
  { title: '覆盖率分析', desc: '代码/用例覆盖评估', path: '/coverage-analysis', icon: 'PieChart', color: '#10b981' },
  { title: '日志分析', desc: '错误模式识别', path: '/log-analysis', icon: 'Memo', color: '#8b5cf6' },
]

const stats = ref([
  { label: '项目', value: 0, icon: 'Folder', color: '#3b82f6' },
  { label: '文档', value: 0, icon: 'Document', color: '#8b5cf6' },
  { label: '测试点', value: 0, icon: 'Aim', color: '#06b6d4' },
  { label: '用例', value: 0, icon: 'List', color: '#10b981' },
])

const reportCount = ref(0)

const quickLinks = [
  { title: '项目管理', desc: '创建与管理测试项目', path: '/projects', icon: 'FolderOpened' },
  { title: '上传文档', desc: '需求文档上传与预览', path: '/requirement-center/documents', icon: 'Upload' },
  { title: '测试报告', desc: 'Allure 报告与压测分析', path: '/test-reports-center/list', icon: 'DataBoard' },
]

const assetChartRef = ref<HTMLElement | null>(null)
const trendChartRef = ref<HTMLElement | null>(null)
let assetChart: echarts.ECharts | null = null
let trendChart: echarts.ECharts | null = null

function renderCharts() {
  const values = stats.value.map((s) => s.value)
  const labels = stats.value.map((s) => s.label)
  const colors = stats.value.map((s) => s.color)

  if (assetChartRef.value) {
    if (!assetChart) assetChart = echarts.init(assetChartRef.value)
    assetChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { orient: 'vertical', right: 8, top: 'center', textStyle: { color: '#9aa0a6' } },
      series: [{
        type: 'pie',
        radius: ['38%', '62%'],
        center: ['38%', '50%'],
        label: { color: '#e8eaed', formatter: '{b}\n{c}' },
        data: labels.map((name, i) => ({
          name,
          value: values[i] || 0,
          itemStyle: { color: colors[i] },
        })).filter((d) => d.value > 0),
      }],
    })
  }

  if (trendChartRef.value) {
    if (!trendChart) trendChart = echarts.init(trendChartRef.value)
    const base = Math.max(...values, 1)
    trendChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 16, top: 24, bottom: 28 },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: '#9aa0a6' },
        axisLine: { lineStyle: { color: '#2a3544' } },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#9aa0a6' },
        splitLine: { lineStyle: { color: '#2a354433' } },
      },
      series: [{
        type: 'bar',
        data: values.map((v, i) => ({
          value: v,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: colors[i] },
              { offset: 1, color: colors[i] + '44' },
            ]),
            borderRadius: [6, 6, 0, 0],
          },
        })),
        barWidth: 32,
        label: { show: true, position: 'top', color: '#e8eaed' },
      }, {
        type: 'line',
        smooth: true,
        data: values.map((v) => Math.round(v * 0.6 + base * 0.15)),
        lineStyle: { color: '#f59e0b', width: 2 },
        itemStyle: { color: '#f59e0b' },
        symbol: 'circle',
        symbolSize: 8,
      }],
    })
  }
}

function onResize() {
  assetChart?.resize()
  trendChart?.resize()
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  try {
    const [projects, docs, points, cases, reports] = await Promise.all([
      getProjects(), getDocuments(), getTestPoints(), getTestCases(), getTestReports(),
    ])
    stats.value[0].value = projects.data.count ?? projects.data.results?.length ?? 0
    stats.value[1].value = docs.data.count ?? docs.data.results?.length ?? 0
    stats.value[2].value = points.data.count ?? points.data.results?.length ?? 0
    stats.value[3].value = cases.data.count ?? cases.data.results?.length ?? 0
    reportCount.value = reports.data.count ?? reports.data.results?.length ?? 0
    renderCharts()
  } catch {
    renderCharts()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  assetChart?.dispose()
  trendChart?.dispose()
})
</script>

<template>
  <div class="home">
    <section class="hero">
      <div class="hero-bg" />
      <div class="hero-grid">
        <div class="hero-content">
          <div class="hero-badge">
            <el-icon><Monitor /></el-icon>
            {{ APP_TITLE }}
          </div>
          <h1 class="hero-title">{{ APP_TITLE }}</h1>
          <p class="hero-desc">
            从需求文档到接口测试的全链路闭环 — 需求驱动、AI 增强、用例工厂、接口自动化
          </p>
          <div class="hero-actions">
            <el-button type="primary" size="large" round @click="router.push('/projects')">
              <el-icon><FolderOpened /></el-icon> 开始：创建项目
            </el-button>
            <el-button size="large" round @click="router.push('/requirement-center')">
              进入需求中心
            </el-button>
          </div>
          <div class="hero-pipeline">
            <div v-for="(m, i) in modules" :key="m.step" class="pipe-item">
              <span class="pipe-dot" :style="{ background: m.color, boxShadow: `0 0 12px ${m.color}66` }">{{ m.step }}</span>
              <span class="pipe-label">{{ m.title }}</span>
              <el-icon v-if="i < modules.length - 1" class="pipe-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
        <div class="hero-visual">
          <div class="orbit-ring ring-1" />
          <div class="orbit-ring ring-2" />
          <div class="orbit-center">
            <el-icon :size="36" color="#60a5fa"><Cpu /></el-icon>
            <span>AI 测试平台</span>
          </div>
          <div class="orbit-node n1"><el-icon><Document /></el-icon></div>
          <div class="orbit-node n2"><el-icon><Connection /></el-icon></div>
          <div class="orbit-node n3"><el-icon><DataAnalysis /></el-icon></div>
        </div>
      </div>
    </section>

    <section class="stats-grid">
      <div v-for="s in stats" :key="s.label" class="stat-card">
        <div class="stat-icon" :style="{ background: s.color + '18', color: s.color }">
          <el-icon :size="22"><component :is="s.icon" /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-num">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </div>
      </div>
      <div class="stat-card report-card">
        <div class="stat-icon" style="background:#f59e0b18;color:#f59e0b">
          <el-icon :size="22"><DataBoard /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-num">{{ reportCount }}</div>
          <div class="stat-label">测试报告</div>
        </div>
      </div>
    </section>

    <section class="charts-section">
      <div class="chart-card page-card">
        <h3>资产分布</h3>
        <div ref="assetChartRef" class="chart-box" />
      </div>
      <div class="chart-card page-card">
        <h3>数据概览</h3>
        <div ref="trendChartRef" class="chart-box" />
      </div>
    </section>

    <section class="section">
      <h2 class="section-title">AI 智能分析</h2>
      <div class="ai-grid">
        <div
          v-for="a in aiModules"
          :key="a.path"
          class="ai-card"
          :style="{ '--accent': a.color }"
          @click="router.push(a.path)"
        >
          <div class="ai-icon" :style="{ color: a.color, background: a.color + '18' }">
            <el-icon :size="22"><component :is="a.icon" /></el-icon>
          </div>
          <div>
            <strong>{{ a.title }}</strong>
            <p>{{ a.desc }}</p>
          </div>
          <el-icon class="ai-arrow"><ArrowRight /></el-icon>
        </div>
      </div>
    </section>

    <section class="section">
      <h2 class="section-title">快速开始</h2>
      <div class="quick-grid">
        <div
          v-for="q in quickLinks"
          :key="q.path"
          class="quick-card"
          @click="router.push(q.path)"
        >
          <el-icon :size="20" color="#3b82f6"><component :is="q.icon" /></el-icon>
          <div>
            <strong>{{ q.title }}</strong>
            <p>{{ q.desc }}</p>
          </div>
          <el-icon class="quick-arrow"><ArrowRight /></el-icon>
        </div>
      </div>
    </section>

    <section class="section">
      <h2 class="section-title">核心业务模块</h2>
      <div class="module-grid">
        <div
          v-for="m in modules"
          :key="m.path"
          class="module-card"
          :style="{ '--accent': m.color }"
          @click="router.push(m.path)"
        >
          <div class="module-top" :style="{ background: m.gradient }">
            <div class="module-icon" :style="{ color: m.color, borderColor: m.color + '44' }">
              <el-icon :size="26"><component :is="m.icon" /></el-icon>
            </div>
            <span class="module-step">{{ m.step }}</span>
          </div>
          <div class="module-body">
            <div class="module-head">
              <h3>{{ m.title }}</h3>
              <el-icon class="enter-icon"><Right /></el-icon>
            </div>
            <p class="module-flow">{{ m.flow }}</p>
            <div class="module-tags">
              <span v-for="item in m.items" :key="item" class="tag">{{ item }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.hero {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  margin-bottom: 24px;
  border: 1px solid #2a3544;
}

.hero-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 60% at 20% 40%, #3b82f618 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 20%, #8b5cf614 0%, transparent 55%),
    linear-gradient(160deg, #141c28 0%, #0f1419 100%);
}

.hero-grid {
  position: relative;
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 24px;
  padding: 36px 40px 24px;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  background: #3b82f618;
  border: 1px solid #3b82f633;
  color: #60a5fa;
  font-size: 13px;
  margin-bottom: 16px;
}

.hero-title {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.5px;
  margin-bottom: 12px;
  line-height: 1.3;
}

.hero-desc {
  color: #9aa0a6;
  font-size: 15px;
  line-height: 1.7;
  max-width: 520px;
  margin-bottom: 24px;
}

.hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.hero-pipeline {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid #2a354466;
  overflow-x: auto;
}

.pipe-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.pipe-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
}

.pipe-label { font-size: 13px; color: #9aa0a6; white-space: nowrap; }
.pipe-arrow { color: #4b5563; margin: 0 4px; }

.hero-visual {
  position: relative;
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.orbit-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px dashed #3b82f633;
}
.ring-1 { width: 180px; height: 180px; animation: spin 24s linear infinite; }
.ring-2 { width: 240px; height: 240px; border-color: #8b5cf622; animation: spin 36s linear infinite reverse; }

.orbit-center {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px;
  border-radius: 50%;
  background: #1a2332cc;
  border: 1px solid #3b82f644;
  color: #60a5fa;
  font-size: 12px;
  font-weight: 600;
}

.orbit-node {
  position: absolute;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: #141c28;
  border: 1px solid #2a3544;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9aa0a6;
}
.n1 { top: 20px; right: 30px; color: #8b5cf6; }
.n2 { bottom: 30px; left: 20px; color: #f59e0b; }
.n3 { bottom: 20px; right: 50px; color: #10b981; }

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #1a2332;
  border: 1px solid #2a3544;
  border-radius: 12px;
  transition: border-color 0.2s;
}

.stat-card:hover { border-color: #3b82f644; }

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-num { font-size: 28px; font-weight: 700; color: #fff; line-height: 1.2; }
.stat-label { font-size: 13px; color: #6b7280; margin-top: 2px; }

.charts-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 32px;
}

.chart-card h3 {
  color: #e8eaed;
  font-size: 14px;
  margin-bottom: 8px;
  padding-left: 8px;
  border-left: 3px solid #3b82f6;
}

.chart-box { height: 260px; }

.section { margin-bottom: 32px; }

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #e8eaed;
  margin-bottom: 16px;
  padding-left: 10px;
  border-left: 3px solid #3b82f6;
}

.ai-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.ai-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: #1a2332;
  border: 1px solid #2a3544;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.ai-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px #00000030;
}

.ai-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ai-card strong { display: block; color: #f3f4f6; font-size: 14px; margin-bottom: 4px; }
.ai-card p { color: #6b7280; font-size: 12px; margin: 0; }
.ai-arrow { margin-left: auto; color: #4b5563; }
.ai-card:hover .ai-arrow { color: var(--accent); }

.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.quick-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: #1a2332;
  border: 1px solid #2a3544;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-card:hover { border-color: #3b82f6; background: #1a2744; }
.quick-card strong { display: block; color: #f3f4f6; font-size: 14px; margin-bottom: 4px; }
.quick-card p { color: #6b7280; font-size: 12px; margin: 0; }
.quick-arrow { margin-left: auto; color: #4b5563; }
.quick-card:hover .quick-arrow { color: #3b82f6; }

.module-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.module-card {
  background: #1a2332;
  border: 1px solid #2a3544;
  border-radius: 14px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.25s ease;
}

.module-card:hover {
  border-color: var(--accent);
  transform: translateY(-3px);
  box-shadow: 0 12px 32px #00000040;
}

.module-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 20px 12px;
}

.module-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  border: 1px solid;
  background: #0f141966;
  display: flex;
  align-items: center;
  justify-content: center;
}

.module-step { font-size: 12px; font-weight: 700; color: var(--accent); opacity: 0.7; }
.module-body { padding: 0 20px 20px; }
.module-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.module-head h3 { color: #fff; font-size: 17px; font-weight: 600; }
.enter-icon { color: #4b5563; transition: color 0.2s, transform 0.2s; }
.module-card:hover .enter-icon { color: var(--accent); transform: translateX(4px); }
.module-flow { color: #6b7280; font-size: 13px; margin-bottom: 14px; font-family: Consolas, monospace; }
.module-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag {
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11px;
  color: #9aa0a6;
  background: #141c28;
  border: 1px solid #2a3544;
}

@media (max-width: 900px) {
  .hero-grid { grid-template-columns: 1fr; padding: 28px 24px 20px; }
  .hero-visual { display: none; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .charts-section { grid-template-columns: 1fr; }
  .ai-grid, .quick-grid { grid-template-columns: 1fr; }
  .module-grid { grid-template-columns: 1fr; }
  .hero-title { font-size: 24px; }
}
</style>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const strategies = [
  {
    key: 'equivalence',
    title: '等价类划分',
    desc: '将输入域划分为有效/无效等价类，每个类选取代表值设计用例，减少冗余同时保证覆盖。',
    icon: 'Grid',
    color: '#3b82f6',
  },
  {
    key: 'boundary',
    title: '边界值分析',
    desc: '关注输入边界及边界两侧值（min、max、min-1、max+1），发现 off-by-one 类缺陷。',
    icon: 'ScaleToOriginal',
    color: '#10b981',
  },
  {
    key: 'scenario',
    title: '场景法',
    desc: '基于用户实际使用场景设计端到端测试路径，覆盖主流程、分支流程和异常流程。',
    icon: 'Guide',
    color: '#8b5cf6',
  },
  {
    key: 'state',
    title: '状态迁移',
    desc: '针对有状态的对象（订单、会话等），覆盖合法/非法状态转换，验证状态机正确性。',
    icon: 'Switch',
    color: '#f59e0b',
  },
]

function useStrategy(key: string) {
  router.push({ path: '/test-design/generator', query: { strategy: key } })
}
</script>

<template>
  <div class="strategy-page">
    <p class="intro">选择测试设计策略后，AI 将按对应方法论从<strong>需求条目</strong>推导<strong>测试点</strong>。可在「AI 测试设计」中切换策略并启用 RAG 增强。</p>
    <div class="strategy-grid">
      <div v-for="s in strategies" :key="s.key" class="strategy-card" @click="useStrategy(s.key)">
        <div class="icon" :style="{ background: s.color + '22', color: s.color }">
          <el-icon :size="28"><component :is="s.icon" /></el-icon>
        </div>
        <h3>{{ s.title }}</h3>
        <p>{{ s.desc }}</p>
        <el-button type="primary" link>使用此策略 →</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.intro { color: #9aa0a6; margin-bottom: 20px; line-height: 1.6; }
.strategy-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.strategy-card {
  padding: 24px; background: #1a2332; border: 1px solid #2a3544;
  border-radius: 12px; cursor: pointer; transition: all 0.2s;
}
.strategy-card:hover { border-color: #3b82f6; transform: translateY(-2px); }
.icon { width: 52px; height: 52px; border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-bottom: 14px; }
.strategy-card h3 { color: #fff; margin-bottom: 10px; }
.strategy-card p { color: #9aa0a6; font-size: 13px; line-height: 1.7; margin-bottom: 12px; }
</style>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { APP_TITLE } from '@/config/app'

const route = useRoute()
const router = useRouter()

const activeMenu = computed(() => {
  const p = route.path
  if (p.startsWith('/requirement-center')) return '/requirement-center'
  if (p.startsWith('/test-case-factory')) return '/test-case-factory'
  if (p.startsWith('/test-execution')) return '/test-execution'
  if (p.startsWith('/test-reports-center') || p.startsWith('/test-reports')) return '/test-reports-center'
  if (p.startsWith('/llm-config')) return '/llm-config'
  return p
})

const menuGroups = [
  {
    title: '',
    items: [{ path: '/home', title: '首页', icon: 'House' }],
  },
  {
    title: '基础管理',
    items: [{ path: '/projects', title: '项目管理', icon: 'Folder' }],
  },
  {
    title: '核心业务',
    items: [
      { path: '/requirement-center', title: '需求中心', icon: 'Document' },
      { path: '/test-case-factory', title: '测试用例', icon: 'List' },
      { path: '/test-execution', title: '接口测试', icon: 'Connection' },
      { path: '/test-reports-center', title: '测试报告', icon: 'DocumentCopy' },
    ],
  },
  {
    title: '工具箱',
    items: [
      { path: '/mock-data', title: '假数据生成', icon: 'Box' },
      { path: '/json-tool', title: 'JSON工具', icon: 'DocumentChecked' },
      { path: '/encode-tool', title: '编码转换', icon: 'EditPen' },
    ],
  },
  {
    title: 'AI增强',
    items: [
      { path: '/contract-test', title: '契约测试', icon: 'Tickets' },
      { path: '/coverage', title: '覆盖率分析', icon: 'DataAnalysis' },
      { path: '/log-analysis', title: '日志分析', icon: 'Memo' },
    ],
  },
  {
    title: '系统管理',
    items: [
      { path: '/llm-config', title: '大模型配置', icon: 'Cpu' },
      { path: '/llm-config/system', title: '系统设置', icon: 'Tools' },
    ],
  },
]

function navigate(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo">
        <el-icon :size="22"><Monitor /></el-icon>
        <span>{{ APP_TITLE }}</span>
      </div>
      <nav class="menu">
        <div v-for="(group, gi) in menuGroups" :key="gi" class="menu-group">
          <div v-if="group.title" class="group-title">{{ group.title }}</div>
          <div
            v-for="item in group.items"
            :key="item.path"
            class="menu-item"
            :class="{ active: activeMenu === item.path }"
            @click="navigate(item.path)"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </div>
        </div>
      </nav>
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.layout { display: flex; height: 100vh; background: #0f1419; }
.sidebar {
  width: 220px; background: #141c28; border-right: 1px solid #2a3544;
  display: flex; flex-direction: column; flex-shrink: 0;
}
.logo {
  display: flex; align-items: center; gap: 10px; padding: 20px 16px;
  font-size: 14px; font-weight: 600; color: #fff; border-bottom: 1px solid #2a3544;
}
.menu { flex: 1; overflow-y: auto; padding: 12px 8px; }
.group-title {
  font-size: 12px; color: #6b7280; padding: 12px 12px 6px;
  text-transform: uppercase; letter-spacing: 0.5px;
}
.menu-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  margin: 2px 0; border-radius: 8px; cursor: pointer;
  color: #9aa0a6; font-size: 14px; transition: all 0.2s;
}
.menu-item:hover { background: #1e2a3a; color: #e8eaed; }
.menu-item.active { background: #2563eb; color: #fff; }
.main { flex: 1; overflow-y: auto; padding: 24px; }
</style>

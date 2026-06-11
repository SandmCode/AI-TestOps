<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { moduleTabs, moduleTitles } from '@/config/modules'

const route = useRoute()
const router = useRouter()

const moduleKey = computed(() => route.matched.find((r) => r.meta.module)?.meta.module as string || '')
const tabs = computed(() => moduleTabs[moduleKey.value] || [])
const moduleTitle = computed(() => moduleTitles[moduleKey.value] || '')

function go(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="module-layout">
    <div class="module-header">
      <h1 class="page-title">{{ moduleTitle }}</h1>
      <p class="module-flow">
        <template v-if="moduleKey === 'requirement-center'">上传文档 → AI 解析 → 测试点树</template>
        <template v-else-if="moduleKey === 'test-case-factory'">测试点 → AI 生成用例 → 管理 / 执行</template>
        <template v-else-if="moduleKey === 'test-execution'">接口文档解析 → 导入接口库 → 关联配置 → 自动化执行</template>
        <template v-else-if="moduleKey === 'llm-config'">API Key 配置 → Skills 注入 → AI 真实调用</template>
      </p>
    </div>
    <div class="module-tabs">
      <div
        v-for="tab in tabs"
        :key="tab.path"
        class="tab-item"
        :class="{ active: route.path === tab.path }"
        @click="go(tab.path)"
      >
        <el-icon><component :is="tab.icon" /></el-icon>
        <span>{{ tab.title }}</span>
      </div>
    </div>
    <router-view />
  </div>
</template>

<style scoped>
.module-layout { min-height: 100%; }
.module-header { margin-bottom: 16px; }
.module-flow { color: #6b7280; font-size: 13px; margin-top: 4px; }
.module-tabs {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin-bottom: 20px; padding-bottom: 16px;
  border-bottom: 1px solid #2a3544;
}
.tab-item {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border-radius: 20px;
  background: #141c28; border: 1px solid #2a3544;
  color: #9aa0a6; font-size: 13px; cursor: pointer;
  transition: all 0.2s;
}
.tab-item:hover { border-color: #3b82f6; color: #e8eaed; }
.tab-item.active {
  background: #2563eb; border-color: #2563eb; color: #fff;
}
</style>

<script setup lang="ts">
defineProps<{
  theme: 'contract' | 'coverage' | 'log'
  icon: string
  title: string
  desc: string
  editorLabel?: string
  hasResult?: boolean
}>()
</script>

<template>
  <div class="ai-workbench">
    <header class="ai-hero" :class="theme">
      <div class="ai-hero-main">
        <div class="ai-hero-icon">
          <el-icon :size="26"><component :is="icon" /></el-icon>
        </div>
        <div>
          <div class="ai-hero-title">{{ title }}</div>
          <div class="ai-hero-desc">{{ desc }}</div>
        </div>
      </div>
      <div v-if="$slots['hero-extra']" class="ai-hero-extra">
        <slot name="hero-extra" />
      </div>
    </header>

    <div class="ai-editor-panel">
      <div class="ai-editor-chrome">
        <div class="ai-editor-chrome-left">
          <div class="ai-dots"><span /><span /><span /></div>
          <span class="ai-editor-label">{{ editorLabel || '输入内容' }}</span>
        </div>
        <div v-if="$slots.tools" class="ai-editor-tools">
          <slot name="tools" />
        </div>
      </div>
      <div class="ai-editor-body">
        <slot name="input" />
      </div>
    </div>

    <div v-if="$slots.actions" class="ai-action-bar">
      <slot name="actions" />
    </div>

    <div v-if="hasResult" class="ai-results">
      <slot name="results" />
    </div>
    <div v-else-if="$slots.empty" class="ai-empty">
      <slot name="empty" />
    </div>
  </div>
</template>

<style scoped>
@import '@/styles/ai-analysis.css';
</style>

<script setup lang="ts">
import { ref } from 'vue'
import { stressScript } from '@/api'

const form = ref({ url: 'http://127.0.0.1:8000/api/projects/', users: 10, spawn_rate: 2, duration: '30s' })
const script = ref('')
const command = ref('')

async function generate() {
  const res = await stressScript(form.value)
  script.value = res.data.script
  command.value = res.data.config.command
}
</script>

<template>
  <div>
    <h1 class="page-title">压测工具</h1>
    <div class="page-card">
      <el-form label-width="100px" style="max-width:600px">
        <el-form-item label="目标 URL"><el-input v-model="form.url" /></el-form-item>
        <el-form-item label="并发用户数"><el-input-number v-model="form.users" :min="1" :max="1000" /></el-form-item>
        <el-form-item label="启动速率"><el-input-number v-model="form.spawn_rate" :min="1" :max="100" /></el-form-item>
        <el-form-item label="持续时间"><el-input v-model="form.duration" placeholder="30s / 1m / 5m" /></el-form-item>
        <el-form-item>
          <el-button type="primary" @click="generate">生成 Locust 脚本</el-button>
        </el-form-item>
      </el-form>

      <div v-if="script">
        <h4 style="color:#fff;margin:16px 0 8px">Locust 脚本</h4>
        <pre class="code-block">{{ script }}</pre>
        <h4 style="color:#fff;margin:16px 0 8px">运行命令</h4>
        <pre class="code-block">{{ command }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.code-block {
  background: #141c28;
  padding: 16px;
  border-radius: 8px;
  font-size: 13px;
  color: #10b981;
  white-space: pre-wrap;
}
</style>

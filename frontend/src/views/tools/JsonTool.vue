<script setup lang="ts">
import { ref } from 'vue'
import { jsonTool } from '@/api'

const input = ref('{"name":"test","items":[1,2,3]}')
const output = ref('')
const action = ref('format')

async function run() {
  const res = await jsonTool({ action: action.value, text: input.value })
  output.value = res.data.result ?? JSON.stringify(res.data, null, 2)
}
</script>

<template>
  <div>
    <h1 class="page-title">JSON 工具</h1>
    <div class="page-card">
      <el-radio-group v-model="action" style="margin-bottom:16px">
        <el-radio-button value="format">格式化</el-radio-button>
        <el-radio-button value="minify">压缩</el-radio-button>
        <el-radio-button value="validate">校验</el-radio-button>
        <el-radio-button value="to_yaml">转 YAML</el-radio-button>
      </el-radio-group>

      <el-row :gutter="16">
        <el-col :span="12">
          <h4 style="color:#fff;margin-bottom:8px">输入</h4>
          <el-input v-model="input" type="textarea" :rows="16" />
        </el-col>
        <el-col :span="12">
          <h4 style="color:#fff;margin-bottom:8px">输出</h4>
          <el-input v-model="output" type="textarea" :rows="16" readonly />
        </el-col>
      </el-row>
      <el-button type="primary" style="margin-top:16px" @click="run">执行</el-button>
    </div>
  </div>
</template>

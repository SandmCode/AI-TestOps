<script setup lang="ts">
import type { CaseFieldDef } from '@/composables/useCaseFieldSchema'

defineProps<{
  field: CaseFieldDef
  modelValue: string
}>()

const emit = defineEmits<{ 'update:modelValue': [string] }>()
</script>

<template>
  <el-select
    v-if="field.field_type === 'priority'"
    :model-value="modelValue"
    placeholder="全部"
    clearable
    style="width:100%"
    @update:model-value="emit('update:modelValue', $event || '')"
  >
    <el-option label="P0 - 紧急" value="P0" />
    <el-option label="P1 - 高" value="P1" />
    <el-option label="P2 - 中" value="P2" />
    <el-option label="P3 - 低" value="P3" />
  </el-select>
  <el-select
    v-else-if="field.field_type === 'passed'"
    :model-value="modelValue"
    placeholder="全部"
    clearable
    style="width:100%"
    @update:model-value="emit('update:modelValue', $event || '')"
  >
    <el-option label="已通过" value="passed" />
    <el-option label="已失败" value="failed" />
    <el-option label="未执行" value="pending" />
  </el-select>
  <el-select
    v-else-if="field.field_type === 'select'"
    :model-value="modelValue"
    placeholder="全部"
    clearable
    style="width:100%"
    @update:model-value="emit('update:modelValue', $event || '')"
  >
    <el-option v-for="opt in field.options" :key="opt" :label="opt" :value="opt" />
  </el-select>
  <el-date-picker
    v-else-if="field.field_type === 'date'"
    :model-value="modelValue"
    type="date"
    value-format="YYYY-MM-DD"
    placeholder="选择日期"
    style="width:100%"
    @update:model-value="emit('update:modelValue', $event || '')"
  />
  <el-input
    v-else
    :model-value="modelValue"
    :placeholder="`输入${field.label}`"
    clearable
    @update:model-value="emit('update:modelValue', $event || '')"
  />
</template>

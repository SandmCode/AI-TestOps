<script setup lang="ts">
import type { CaseFieldDef } from '@/composables/useCaseFieldSchema'

defineProps<{
  field: CaseFieldDef
  modelValue: unknown
}>()

const emit = defineEmits<{ 'update:modelValue': [unknown] }>()
</script>

<template>
  <el-input
    v-if="field.field_type === 'text'"
    :model-value="modelValue as string"
    :placeholder="`请输入${field.label}`"
    @update:model-value="emit('update:modelValue', $event)"
  />
  <el-input
    v-else-if="field.field_type === 'textarea'"
    :model-value="modelValue as string"
    type="textarea"
    :rows="3"
    :placeholder="`请输入${field.label}`"
    @update:model-value="emit('update:modelValue', $event)"
  />
  <el-select
    v-else-if="field.field_type === 'select'"
    :model-value="modelValue as string"
    style="width:100%"
    clearable
    :placeholder="`请选择${field.label}`"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-option v-for="opt in field.options" :key="opt" :label="opt" :value="opt" />
  </el-select>
  <el-date-picker
    v-else-if="field.field_type === 'date'"
    :model-value="modelValue as string"
    type="date"
    value-format="YYYY-MM-DD"
    style="width:100%"
    @update:model-value="emit('update:modelValue', $event)"
  />
  <el-select
    v-else-if="field.field_type === 'priority'"
    :model-value="modelValue as string"
    style="width:100%"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-option label="P0-紧急" value="P0" />
    <el-option label="P1-高" value="P1" />
    <el-option label="P2-中" value="P2" />
    <el-option label="P3-低" value="P3" />
  </el-select>
  <el-select
    v-else-if="field.field_type === 'passed'"
    :model-value="modelValue as boolean | null"
    clearable
    placeholder="未执行"
    style="width:100%"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-option label="通过" :value="true" />
    <el-option label="失败" :value="false" />
  </el-select>
  <el-input
    v-else
    :model-value="modelValue as string"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>

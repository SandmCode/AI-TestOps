<script setup lang="ts">
withDefaults(defineProps<{
  indeterminate?: boolean
  size?: 'sm' | 'md'
}>(), {
  indeterminate: false,
  size: 'md',
})

const model = defineModel<boolean>({ default: false })

function toggle() {
  model.value = !model.value
}
</script>

<template>
  <button
    type="button"
    class="card-checkbox"
    :class="{
      checked: model,
      indeterminate: indeterminate && !model,
      [`size-${size}`]: true,
    }"
    @click.stop="toggle"
  >
    <span class="box">
      <el-icon v-if="model" class="icon"><Check /></el-icon>
      <span v-else-if="indeterminate" class="dash" />
    </span>
  </button>
</template>

<style scoped>
.card-checkbox {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  flex-shrink: 0;
}

.box {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: 2px solid #4b5563;
  background: #0f1419;
  transition: all 0.2s ease;
}

.size-md .box {
  width: 20px;
  height: 20px;
}

.size-sm .box {
  width: 16px;
  height: 16px;
  border-radius: 4px;
}

.card-checkbox:hover .box {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.card-checkbox.checked .box,
.card-checkbox.indeterminate .box {
  border-color: #3b82f6;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.35);
}

.icon {
  color: #fff;
  font-size: 12px;
  font-weight: bold;
}

.size-sm .icon {
  font-size: 10px;
}

.dash {
  width: 10px;
  height: 2px;
  border-radius: 1px;
  background: #fff;
}

.size-sm .dash {
  width: 8px;
}
</style>

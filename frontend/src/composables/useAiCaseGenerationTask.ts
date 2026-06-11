import { computed, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getActiveAsyncTask, getAsyncTask } from '@/api'

const STORAGE_KEY = 'ai-case-generation-task-id'

export interface AsyncTaskItem {
  id: number
  task_name: string
  task_type: string
  status: 'pending' | 'running' | 'success' | 'failed'
  progress: number
  total_steps: number
  completed_steps: number
  current_step: string
  project: number | null
  result: string
  error_message: string
}

function parseResultCount(result: string): number {
  if (!result) return 0
  try {
    const data = JSON.parse(result)
    return Number(data.count) || 0
  } catch {
    return 0
  }
}

export function useAiCaseGenerationTask(onComplete?: () => void) {
  const task = ref<AsyncTaskItem | null>(null)
  let timer: ReturnType<typeof setInterval> | null = null

  const isRunning = computed(
    () => task.value?.status === 'pending' || task.value?.status === 'running',
  )

  const progress = computed(() => task.value?.progress ?? 0)

  const progressText = computed(() => {
    if (!task.value || !isRunning.value) return ''
    const { completed_steps, total_steps, current_step } = task.value
    if (current_step) {
      return `正在生成：${current_step}（${completed_steps}/${total_steps}）`
    }
    return `正在生成用例... ${progress.value}%`
  })

  function stopPolling() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  async function pollOnce(id: number) {
    const res = await getAsyncTask(id)
    task.value = res.data

    if (res.data.status === 'success') {
      stopPolling()
      localStorage.removeItem(STORAGE_KEY)
      const count = parseResultCount(res.data.result)
      ElMessage.success(`已生成 ${count} 条测试用例`)
      onComplete?.()
    } else if (res.data.status === 'failed') {
      stopPolling()
      localStorage.removeItem(STORAGE_KEY)
      const count = parseResultCount(res.data.result)
      if (count > 0) {
        ElMessage.warning(
          res.data.error_message
            ? `部分完成：已生成 ${count} 条。${res.data.error_message}`
            : `已生成 ${count} 条，但任务未完全成功`,
        )
        onComplete?.()
      } else {
        ElMessage.error(res.data.error_message || 'AI 生成失败')
      }
    }
  }

  function startPolling(id: number) {
    stopPolling()
    localStorage.setItem(STORAGE_KEY, String(id))
    pollOnce(id)
    timer = setInterval(() => pollOnce(id), 2000)
  }

  async function resumeIfActive(projectId?: number | null) {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const id = Number(stored)
      if (!Number.isNaN(id)) {
        startPolling(id)
        return
      }
    }
    const params = projectId ? { project: projectId } : undefined
    const res = await getActiveAsyncTask(params)
    if (res.data.active && res.data.id) {
      startPolling(res.data.id)
    }
  }

  function trackTask(id: number) {
    startPolling(id)
  }

  onUnmounted(() => stopPolling())

  return {
    task,
    isRunning,
    progress,
    progressText,
    trackTask,
    resumeIfActive,
    stopPolling,
  }
}

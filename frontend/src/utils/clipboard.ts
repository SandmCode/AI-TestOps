import { ElMessage } from 'element-plus'

export async function copyText(text: string, label = '内容') {
  if (!text?.trim()) {
    ElMessage.warning('没有可复制的内容')
    return false
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(`已复制${label}`)
    return true
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    try {
      document.execCommand('copy')
      ElMessage.success(`已复制${label}`)
      return true
    } catch {
      ElMessage.error('复制失败，请手动复制')
      return false
    } finally {
      document.body.removeChild(ta)
    }
  }
}

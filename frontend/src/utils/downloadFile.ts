import api from '@/api/index'
import { ElMessage } from 'element-plus'

function parseFilename(contentDisposition: string, fallback: string): string {
  if (!contentDisposition) return fallback
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;\n]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1].trim())
    } catch {
      return utf8Match[1]
    }
  }
  const plainMatch = contentDisposition.match(/filename="?([^";\n]+)"?/i)
  if (plainMatch?.[1]) return plainMatch[1].trim()
  return fallback
}

export async function downloadFromApi(apiPath: string, fallbackName: string) {
  try {
    const res = await api.get(apiPath, { responseType: 'blob' })
    const blob = res.data as Blob
    if (blob.type.includes('application/json')) {
      const text = await blob.text()
      try {
        const err = JSON.parse(text)
        if (err.error || err.detail) {
          ElMessage.error(String(err.error || err.detail))
          return false
        }
      } catch {
        /* not json error */
      }
    }
    const cd = (res.headers['content-disposition'] as string) || ''
    const filename = parseFilename(cd, fallbackName)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success(`已下载 ${filename}`)
    return true
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '下载失败'
    ElMessage.error(msg)
    return false
  }
}

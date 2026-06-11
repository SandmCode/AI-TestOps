import { ref } from 'vue'
import api, {
  chunkInit,
  chunkUploadPart,
  chunkComplete,
  chunkCancel,
  chunkStatus,
} from '@/api'

export const CHUNK_THRESHOLD = 20 * 1024 * 1024
const CHUNK_SIZE = 5 * 1024 * 1024
const RESUME_KEY = 'doc_chunk_upload_resume'

export interface UploadFormData {
  project: number
  name: string
  version: string
  doc_type: string
  content: string
}

export interface UploadResult {
  id: number
  name: string
  [key: string]: unknown
}

function fileFingerprint(file: File) {
  return `${file.name}_${file.size}_${file.lastModified}`
}

function saveResume(fingerprint: string, uploadId: string) {
  localStorage.setItem(RESUME_KEY, JSON.stringify({ fingerprint, uploadId }))
}

function loadResume(fingerprint: string): string | null {
  try {
    const raw = localStorage.getItem(RESUME_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    return data.fingerprint === fingerprint ? data.uploadId : null
  } catch {
    return null
  }
}

function clearResume() {
  localStorage.removeItem(RESUME_KEY)
}

export function useChunkUpload() {
  const progress = ref(0)
  const status = ref<'idle' | 'uploading' | 'paused' | 'merging' | 'success' | 'error'>('idle')
  const uploadId = ref('')
  const uploadedSet = ref<Set<number>>(new Set())
  const speedText = ref('')
  const errorMessage = ref('')
  const paused = ref(false)
  const currentFile = ref<File | null>(null)

  let abortFlag = false
  let lastLoaded = 0
  let lastTime = Date.now()

  function updateSpeed(bytesDone: number) {
    const now = Date.now()
    const dt = (now - lastTime) / 1000
    if (dt >= 0.5) {
      const speed = (bytesDone - lastLoaded) / dt
      if (speed > 1024 * 1024) speedText.value = `${(speed / 1024 / 1024).toFixed(1)} MB/s`
      else if (speed > 1024) speedText.value = `${(speed / 1024).toFixed(1)} KB/s`
      else speedText.value = `${speed.toFixed(0)} B/s`
      lastLoaded = bytesDone
      lastTime = now
    }
  }

  async function uploadSmall(file: File, form: UploadFormData): Promise<UploadResult> {
    const fd = new FormData()
    fd.append('project', String(form.project))
    fd.append('name', form.name)
    fd.append('version', form.version)
    fd.append('doc_type', form.doc_type)
    fd.append('content', form.content)
    fd.append('file', file)
    const res = await api.post('/documents/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600000,
      onUploadProgress: (e) => {
        if (e.total) {
          progress.value = Math.round((e.loaded / e.total) * 100)
          updateSpeed(e.loaded)
        }
      },
    })
    return res.data
  }

  async function uploadLarge(file: File, form: UploadFormData): Promise<UploadResult> {
    const fingerprint = fileFingerprint(file)
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE)
    let existingId = loadResume(fingerprint)

    if (existingId) {
      try {
        const statusRes = await chunkStatus(existingId)
        uploadId.value = existingId
        uploadedSet.value = new Set(statusRes.data.uploaded_chunks || [])
        progress.value = statusRes.data.progress || 0
      } catch {
        existingId = null
        clearResume()
      }
    }

    if (!existingId) {
      const initRes = await chunkInit({
        project: form.project,
        filename: file.name,
        file_size: file.size,
        name: form.name,
        version: form.version,
        doc_type: form.doc_type,
        content: form.content,
      })
      uploadId.value = initRes.data.upload_id
      uploadedSet.value = new Set(initRes.data.uploaded_chunks || [])
      saveResume(fingerprint, uploadId.value)
    }

    for (let i = 0; i < totalChunks; i++) {
      if (abortFlag) throw new Error('上传已取消')
      while (paused.value) {
        await new Promise((r) => setTimeout(r, 200))
        if (abortFlag) throw new Error('上传已取消')
      }
      if (uploadedSet.value.has(i)) continue

      const start = i * CHUNK_SIZE
      const end = Math.min(start + CHUNK_SIZE, file.size)
      const blob = file.slice(start, end)
      const fd = new FormData()
      fd.append('upload_id', uploadId.value)
      fd.append('chunk_index', String(i))
      fd.append('chunk', blob, `part_${i}`)

      await chunkUploadPart(fd)
      uploadedSet.value.add(i)
      progress.value = Math.round((uploadedSet.value.size / totalChunks) * 100)
      updateSpeed(end)
    }

    status.value = 'merging'
    const completeRes = await chunkComplete(uploadId.value)
    clearResume()
    return completeRes.data
  }

  async function startUpload(file: File, form: UploadFormData): Promise<UploadResult> {
    currentFile.value = file
    abortFlag = false
    paused.value = false
    errorMessage.value = ''
    progress.value = 0
    speedText.value = ''
    lastLoaded = 0
    lastTime = Date.now()
    status.value = 'uploading'

    try {
      const result = file.size >= CHUNK_THRESHOLD
        ? await uploadLarge(file, form)
        : await uploadSmall(file, form)
      status.value = 'success'
      progress.value = 100
      return result
    } catch (err: unknown) {
      status.value = 'error'
      errorMessage.value = err instanceof Error ? err.message : '上传失败'
      throw err
    }
  }

  function pause() {
    paused.value = true
    status.value = 'paused'
  }

  function resume() {
    paused.value = false
    status.value = 'uploading'
  }

  async function cancel() {
    abortFlag = true
    paused.value = false
    if (uploadId.value) {
      await chunkCancel(uploadId.value)
    }
    clearResume()
    status.value = 'idle'
    progress.value = 0
    uploadId.value = ''
    uploadedSet.value = new Set()
  }

  function reset() {
    abortFlag = false
    paused.value = false
    status.value = 'idle'
    progress.value = 0
    uploadId.value = ''
    uploadedSet.value = new Set()
    speedText.value = ''
    errorMessage.value = ''
    currentFile.value = null
  }

  return {
    progress,
    status,
    uploadId,
    speedText,
    errorMessage,
    paused,
    currentFile,
    startUpload,
    pause,
    resume,
    cancel,
    reset,
    isChunkMode: (file: File) => file.size >= CHUNK_THRESHOLD,
  }
}

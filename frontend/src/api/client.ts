import type {
  Recording,
  RecordingDetailResponse,
  PaginatedRecordings,
  DashboardStats,
  SearchResponse,
  PipelineStatus,
} from './types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  getRecordings(params?: {
    status?: string
    page?: number
    per_page?: number
    sort?: string
  }): Promise<PaginatedRecordings> {
    const q = new URLSearchParams()
    if (params?.status && params.status !== 'all') q.set('status', params.status)
    if (params?.page) q.set('page', String(params.page))
    if (params?.per_page) q.set('per_page', String(params.per_page))
    if (params?.sort) q.set('sort', params.sort)
    return request(`/recordings?${q}`)
  },

  getRecording(id: number): Promise<RecordingDetailResponse> {
    return request(`/recordings/${id}`)
  },

  getAudioUrl(id: number): string {
    return `${BASE}/recordings/${id}/audio`
  },

  async uploadRecording(file: File): Promise<{ recording: Recording; message: string }> {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/recordings/upload`, {
      method: 'POST',
      body: form,
    })
    if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`)
    return res.json()
  },

  reprocessRecording(id: number): Promise<{ message: string; recording_id: number }> {
    return request(`/recordings/${id}/reprocess`, { method: 'POST' })
  },

  deleteRecording(id: number): Promise<{ message: string }> {
    return request(`/recordings/${id}`, { method: 'DELETE' })
  },

  searchTranscripts(q: string): Promise<SearchResponse> {
    const params = new URLSearchParams({ q })
    return request(`/search?${params}`)
  },

  getStats(): Promise<DashboardStats> {
    return request('/stats')
  },

  getPipelineStatus(): Promise<PipelineStatus> {
    return request('/pipeline/status')
  },

  startPipeline(): Promise<{ message: string; watch_dir?: string }> {
    return request('/pipeline/start', { method: 'POST' })
  },

  stopPipeline(): Promise<{ message: string }> {
    return request('/pipeline/stop', { method: 'POST' })
  },
}

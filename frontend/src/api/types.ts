export type RecordingStatus = 'pending' | 'processing' | 'done' | 'error'

export interface Recording {
  id: number
  filename: string
  filepath: string
  status: RecordingStatus
  duration: number | null
  error_message: string | null
  created_at: string
  processed_at: string | null
}

export interface Segment {
  id: number
  speaker: string | null
  role: string | null
  text: string
  start_time: number
  end_time: number
  confidence: number | null
}

export interface Transcript {
  id: number
  full_text: string | null
  language: string | null
  model_used: string | null
}

export interface RecordingDetailResponse {
  recording: Recording
  transcript: Transcript | null
  segments: Segment[]
}

export interface PaginatedRecordings {
  recordings: Recording[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export interface DashboardStats {
  total_recordings: number
  by_status: {
    done: number
    pending: number
    processing: number
    error: number
  }
  avg_duration_seconds: number | null
  total_segments: number
  recordings_per_day: { date: string; count: number }[]
}

export interface SearchResult {
  recording_id: number
  filename: string
  match_type: 'transcript' | 'segment'
  speaker?: string
  text: string
  start_time?: number
  end_time?: number
}

export interface SearchResponse {
  results: SearchResult[]
  query: string
  total: number
}

export interface PipelineStatus {
  watcher_running: boolean
}

export interface ProgressMessage {
  type: 'progress' | 'completed' | 'error' | 'status'
  recording_id?: number
  filename?: string
  step?: string
  progress?: number
  message?: string
}

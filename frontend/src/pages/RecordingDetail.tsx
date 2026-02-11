import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  Download,
  FileText,
  RotateCw,
  Clock,
  Calendar,
  FileAudio,
  AlertTriangle,
} from 'lucide-react'
import { api } from '../api/client'
import type { RecordingDetailResponse, Segment } from '../api/types'
import { AudioPlayer, type AudioPlayerHandle } from '../components/AudioPlayer'
import { TranscriptViewer } from '../components/TranscriptViewer'
import { SegmentTimeline } from '../components/SegmentTimeline'
import { StatusBadge } from '../components/StatusBadge'

function formatDuration(s: number | null): string {
  if (!s) return '-'
  const min = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${min}:${sec.toString().padStart(2, '0')}`
}

function formatTimestamp(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  const ms = Math.floor((s % 1) * 1000)
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`
}

export function RecordingDetail() {
  const { id } = useParams<{ id: string }>()
  const [data, setData] = useState<RecordingDetailResponse | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const playerRef = useRef<AudioPlayerHandle>(null)

  const fetchData = useCallback(async () => {
    if (!id) return
    try {
      const res = await api.getRecording(Number(id))
      setData(res)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nie udało się pobrać danych')
    }
    setLoading(false)
  }, [id])

  useEffect(() => { fetchData() }, [fetchData])

  const handleSegmentClick = (seg: Segment) => {
    playerRef.current?.seekTo(seg.start_time)
  }

  const exportTxt = () => {
    if (!data) return
    const text = data.segments
      .map((s) => `[${formatDuration(s.start_time)}] ${s.speaker ?? '?'}: ${s.text}`)
      .join('\n')
    downloadFile(`${data.recording.filename}.txt`, text, 'text/plain')
  }

  const exportSrt = () => {
    if (!data) return
    const srt = data.segments
      .map((s, i) => `${i + 1}\n${formatTimestamp(s.start_time)} --> ${formatTimestamp(s.end_time)}\n${s.speaker ?? '?'}: ${s.text}`)
      .join('\n\n')
    downloadFile(`${data.recording.filename}.srt`, srt, 'text/srt')
  }

  const exportJson = () => {
    if (!data) return
    const json = {
      filename: data.recording.filename,
      duration: data.recording.duration,
      segments: data.segments.map((s) => ({
        speaker: s.speaker,
        role: s.role,
        start: s.start_time,
        end: s.end_time,
        text: s.text,
      })),
    }
    downloadFile(`${data.recording.filename}.json`, JSON.stringify(json, null, 2), 'application/json')
  }

  const downloadFile = (name: string, content: string, type: string) => {
    const blob = new Blob([content], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-center py-16">
        <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-3" />
        <p className="text-zinc-500">{error ?? 'Nagranie nie znalezione'}</p>
        <Link to="/recordings" className="text-blue-400 text-sm mt-2 inline-block">
          Wróć do nagrań
        </Link>
      </div>
    )
  }

  const { recording, transcript, segments } = data

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/recordings"
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-xl font-bold flex items-center gap-3">
              {recording.filename}
              <StatusBadge status={recording.status} />
            </h1>
            <div className="flex items-center gap-4 mt-1 text-sm text-zinc-500">
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" />
                {new Date(recording.created_at).toLocaleString('pl-PL')}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                {formatDuration(recording.duration)}
              </span>
              {transcript?.language && (
                <span className="flex items-center gap-1">
                  <FileText className="w-3.5 h-3.5" />
                  {transcript.language}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {recording.status === 'error' && (
            <button
              onClick={() => api.reprocessRecording(recording.id).then(fetchData)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
            >
              <RotateCw className="w-3.5 h-3.5" />
              Przetwórz ponownie
            </button>
          )}
          {segments.length > 0 && (
            <div className="flex gap-1">
              <button
                onClick={exportTxt}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
                title="Eksport TXT"
              >
                <Download className="w-3.5 h-3.5" /> TXT
              </button>
              <button
                onClick={exportSrt}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
                title="Eksport SRT"
              >
                <Download className="w-3.5 h-3.5" /> SRT
              </button>
              <button
                onClick={exportJson}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
                title="Eksport JSON"
              >
                <Download className="w-3.5 h-3.5" /> JSON
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Error message */}
      {recording.error_message && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-sm text-red-400">
          {recording.error_message}
        </div>
      )}

      {/* Audio player */}
      {recording.status === 'done' && (
        <AudioPlayer
          ref={playerRef}
          url={api.getAudioUrl(recording.id)}
          onTimeUpdate={setCurrentTime}
        />
      )}

      {/* Segment timeline */}
      {recording.status === 'done' && segments.length > 0 && (
        <SegmentTimeline
          segments={segments}
          duration={recording.duration ?? 0}
          currentTime={currentTime}
          onSegmentClick={handleSegmentClick}
        />
      )}

      {/* Metadata + Transcript */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Metadata */}
        <div className="lg:col-span-1">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
            <h3 className="text-sm font-medium text-zinc-400">Informacje</h3>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-zinc-500">Plik</dt>
                <dd className="text-zinc-300 flex items-center gap-1 truncate">
                  <FileAudio className="w-3.5 h-3.5 flex-shrink-0" />
                  {recording.filename}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500">Czas trwania</dt>
                <dd className="text-zinc-300">{formatDuration(recording.duration)}</dd>
              </div>
              <div>
                <dt className="text-zinc-500">Segmenty</dt>
                <dd className="text-zinc-300">{segments.length}</dd>
              </div>
              {transcript?.model_used && (
                <div>
                  <dt className="text-zinc-500">Model</dt>
                  <dd className="text-zinc-300">{transcript.model_used}</dd>
                </div>
              )}
              {recording.processed_at && (
                <div>
                  <dt className="text-zinc-500">Przetworzono</dt>
                  <dd className="text-zinc-300">
                    {new Date(recording.processed_at).toLocaleString('pl-PL')}
                  </dd>
                </div>
              )}
            </dl>
          </div>
        </div>

        {/* Transcript */}
        <div className="lg:col-span-3">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
            <h3 className="text-sm font-medium text-zinc-400 mb-4">Transkrypcja</h3>
            {segments.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">
                {recording.status === 'done' ? 'Brak segmentów' : 'Transkrypcja w trakcie...'}
              </p>
            ) : (
              <TranscriptViewer
                segments={segments}
                currentTime={currentTime}
                onSegmentClick={handleSegmentClick}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

import { useEffect, useState, useCallback } from 'react'
import {
  Play,
  Square,
  Activity,
  CheckCircle,
  AlertTriangle,
  Loader2,
} from 'lucide-react'
import { api } from '../api/client'
import type { PipelineStatus, ProgressMessage } from '../api/types'
import { useWebSocket } from '../hooks/useWebSocket'

export function Pipeline() {
  const [status, setStatus] = useState<PipelineStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(false)
  const [progress, setProgress] = useState<ProgressMessage | null>(null)
  const [log, setLog] = useState<ProgressMessage[]>([])

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.getPipelineStatus()
      setStatus(s)
    } catch { /* API not ready */ }
    setLoading(false)
  }, [])

  useEffect(() => { fetchStatus() }, [fetchStatus])

  useWebSocket((msg) => {
    setProgress(msg)
    setLog((prev) => [msg, ...prev].slice(0, 50))
    if (msg.type === 'completed' || msg.type === 'error') {
      fetchStatus()
    }
  })

  const toggle = async () => {
    if (!status) return
    setToggling(true)
    try {
      if (status.watcher_running) {
        await api.stopPipeline()
      } else {
        await api.startPipeline()
      }
      await fetchStatus()
    } catch { /* ignore */ }
    setToggling(false)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const isRunning = status?.watcher_running ?? false

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Pipeline</h1>
        <p className="text-sm text-zinc-500 mt-1">Zarządzanie przetwarzaniem nagrań</p>
      </div>

      {/* Status card */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div
              className={`w-12 h-12 rounded-xl flex items-center justify-center
                ${isRunning ? 'bg-green-500/20' : 'bg-zinc-800'}`}
            >
              <Activity
                className={`w-6 h-6 ${isRunning ? 'text-green-400' : 'text-zinc-500'}`}
              />
            </div>
            <div>
              <h2 className="text-lg font-semibold">
                {isRunning ? 'Watcher aktywny' : 'Watcher zatrzymany'}
              </h2>
              <p className="text-sm text-zinc-500 mt-0.5">
                {isRunning
                  ? 'Nasłuchuje na nowe pliki WAV'
                  : 'Kliknij "Uruchom", aby rozpocząć obserwację folderu'}
              </p>
            </div>
          </div>

          <button
            onClick={toggle}
            disabled={toggling}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors
              ${isRunning
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-green-600 hover:bg-green-700'
              } disabled:opacity-50`}
          >
            {toggling ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : isRunning ? (
              <Square className="w-4 h-4" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {isRunning ? 'Zatrzymaj' : 'Uruchom'}
          </button>
        </div>
      </div>

      {/* Current progress */}
      {progress && progress.type === 'progress' && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
              {progress.filename}
            </span>
            <span className="text-sm text-zinc-400">{progress.step}</span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-300"
              style={{ width: `${progress.progress ?? 0}%` }}
            />
          </div>
          <p className="text-xs text-zinc-500 mt-1">{progress.progress?.toFixed(0)}%</p>
        </div>
      )}

      {/* Log */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl">
        <div className="p-4 border-b border-zinc-800">
          <h3 className="text-sm font-medium text-zinc-400">Dziennik przetwarzania</h3>
        </div>
        <div className="divide-y divide-zinc-800/50 max-h-96 overflow-y-auto">
          {log.length === 0 ? (
            <p className="p-8 text-center text-sm text-zinc-500">
              Brak wpisów - uruchom watcher, aby rozpocząć
            </p>
          ) : (
            log.map((entry, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                {entry.type === 'completed' ? (
                  <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                ) : entry.type === 'error' ? (
                  <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                ) : (
                  <Loader2 className="w-4 h-4 text-blue-400 flex-shrink-0 animate-spin" />
                )}
                <span className="text-zinc-400 flex-1 truncate">
                  {entry.filename ?? entry.message}
                </span>
                <span className="text-xs text-zinc-600">
                  {entry.step ?? entry.type}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

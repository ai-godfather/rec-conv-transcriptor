import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  FileAudio,
  CheckCircle,
  Clock,
  AlertTriangle,
  Layers,
  Search,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { api } from '../api/client'
import type { DashboardStats, Recording, ProgressMessage } from '../api/types'
import { StatsCard } from '../components/StatsCard'
import { StatusBadge } from '../components/StatusBadge'
import { useWebSocket } from '../hooks/useWebSocket'

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [recent, setRecent] = useState<Recording[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<ProgressMessage | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([
        api.getStats(),
        api.getRecordings({ per_page: 10, sort: 'date_desc' }),
      ])
      setStats(s)
      setRecent(r.recordings)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nie udało się pobrać danych')
    }
    setLoading(false)
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  useWebSocket((msg) => {
    setProgress(msg)
    if (msg.type === 'completed') fetchData()
  })

  const formatDuration = (s: number | null) => {
    if (!s) return '-'
    const min = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${min}:${sec.toString().padStart(2, '0')}`
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertTriangle className="w-10 h-10 text-red-400" />
        <p className="text-sm text-zinc-400">{error}</p>
        <button
          onClick={fetchData}
          className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm transition-colors"
        >
          Spróbuj ponownie
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Panel</h1>
          <p className="text-sm text-zinc-500 mt-1">Przegląd systemu transkrypcji</p>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Szybkie wyszukiwanie..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && search.trim()) {
                window.location.href = `/search?q=${encodeURIComponent(search)}`
              }
            }}
            className="pl-9 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-sm
              focus:outline-none focus:border-zinc-600 w-64"
          />
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatsCard
          title="Wszystkie nagrania"
          value={stats?.total_recordings ?? 0}
          icon={FileAudio}
          color="text-blue-400"
        />
        <StatsCard
          title="Przetworzone"
          value={stats?.by_status.done ?? 0}
          icon={CheckCircle}
          color="text-green-400"
        />
        <StatsCard
          title="Oczekujące"
          value={stats?.by_status.pending ?? 0}
          icon={Clock}
          color="text-yellow-400"
        />
        <StatsCard
          title="Błędy"
          value={stats?.by_status.error ?? 0}
          icon={AlertTriangle}
          color="text-red-400"
        />
        <StatsCard
          title="Segmenty"
          value={stats?.total_segments ?? 0}
          icon={Layers}
          color="text-purple-400"
        />
      </div>

      {/* Progress bar */}
      {progress && progress.type === 'progress' && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">
              Przetwarzanie: {progress.filename}
            </span>
            <span className="text-sm text-zinc-400">{progress.step}</span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-300"
              style={{ width: `${progress.progress ?? 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Chart */}
      {stats?.recordings_per_day && stats.recordings_per_day.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-medium text-zinc-400 mb-4">
            Nagrania w ostatnich 30 dniach
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stats.recordings_per_day}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="date"
                tick={{ fill: '#71717a', fontSize: 11 }}
                tickFormatter={(v: string) => v.slice(5)}
              />
              <YAxis tick={{ fill: '#71717a', fontSize: 11 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#18181b',
                  border: '1px solid #27272a',
                  borderRadius: '8px',
                  fontSize: 12,
                }}
              />
              <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Nagrania" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Recent recordings */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl">
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <h2 className="text-sm font-medium text-zinc-400">Ostatnie nagrania</h2>
          <Link to="/recordings" className="text-xs text-blue-400 hover:text-blue-300">
            Zobacz wszystkie
          </Link>
        </div>
        <div className="divide-y divide-zinc-800/50">
          {recent.length === 0 ? (
            <p className="p-8 text-center text-sm text-zinc-500">Brak nagrań</p>
          ) : (
            recent.map((rec) => (
              <Link
                key={rec.id}
                to={`/recordings/${rec.id}`}
                className="flex items-center gap-4 px-4 py-3 hover:bg-zinc-800/50 transition-colors"
              >
                <FileAudio className="w-4 h-4 text-zinc-500 flex-shrink-0" />
                <span className="flex-1 text-sm truncate">{rec.filename}</span>
                <span className="text-xs text-zinc-500">{formatDuration(rec.duration)}</span>
                <StatusBadge status={rec.status} />
                <span className="text-xs text-zinc-600 min-w-[80px] text-right">
                  {new Date(rec.created_at).toLocaleDateString('pl-PL')}
                </span>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

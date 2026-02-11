import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  FileAudio,
  ChevronLeft,
  ChevronRight,
  Upload,
  Trash2,
  RotateCw,
  ArrowUpDown,
} from 'lucide-react'
import { api } from '../api/client'
import type { Recording, PaginatedRecordings } from '../api/types'
import { StatusBadge } from '../components/StatusBadge'
import { FileUploader } from '../components/FileUploader'

const STATUS_TABS = [
  { key: 'all', label: 'Wszystkie' },
  { key: 'pending', label: 'Oczekujące' },
  { key: 'processing', label: 'Przetwarzanie' },
  { key: 'done', label: 'Gotowe' },
  { key: 'error', label: 'Błędy' },
]

export function Recordings() {
  const [data, setData] = useState<PaginatedRecordings | null>(null)
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [sortDesc, setSortDesc] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.getRecordings({
        status,
        page,
        per_page: 20,
        sort: sortDesc ? 'date_desc' : 'date_asc',
      })
      setData(res)
    } catch { /* API not ready */ }
    setLoading(false)
  }, [status, page, sortDesc])

  useEffect(() => { fetchData() }, [fetchData])

  const toggleSort = () => {
    setSortDesc((d) => !d)
  }

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm('Czy na pewno chcesz usunąć to nagranie?')) return
    try {
      await api.deleteRecording(id)
      fetchData()
    } catch { /* ignore */ }
  }

  const handleReprocess = async (id: number, e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    try {
      await api.reprocessRecording(id)
      fetchData()
    } catch { /* ignore */ }
  }

  const formatDuration = (s: number | null) => {
    if (!s) return '-'
    const min = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${min}:${sec.toString().padStart(2, '0')}`
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Nagrania</h1>
          <p className="text-sm text-zinc-500 mt-1">
            {data ? `${data.total} nagrań łącznie` : 'Ładowanie...'}
          </p>
        </div>
        <button
          onClick={() => setShowUpload(!showUpload)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
        >
          <Upload className="w-4 h-4" />
          Prześlij pliki
        </button>
      </div>

      {showUpload && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <FileUploader onUploaded={() => { setShowUpload(false); fetchData() }} />
        </div>
      )}

      {/* Status tabs */}
      <div className="flex gap-1 bg-zinc-900 p-1 rounded-lg w-fit">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => { setStatus(tab.key); setPage(1) }}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors
              ${status === tab.key
                ? 'bg-zinc-700 text-zinc-100'
                : 'text-zinc-400 hover:text-zinc-200'
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead className="border-b border-zinc-800">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                Nazwa pliku
              </th>
              <th
                className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider cursor-pointer hover:text-zinc-200"
                onClick={toggleSort}
              >
                <div className="flex items-center gap-1">
                  Data
                  <ArrowUpDown className="w-3 h-3 text-blue-400" />
                </div>
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                Czas trwania
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                Status
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">
                Akcje
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center">
                  <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
                </td>
              </tr>
            ) : !data?.recordings.length ? (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-sm text-zinc-500">
                  Brak nagrań
                </td>
              </tr>
            ) : (
              data.recordings.map((rec: Recording) => (
                <tr key={rec.id} className="hover:bg-zinc-800/30 transition-colors">
                  <td className="px-4 py-3">
                    <Link
                      to={`/recordings/${rec.id}`}
                      className="flex items-center gap-2 text-sm hover:text-blue-400 transition-colors"
                    >
                      <FileAudio className="w-4 h-4 text-zinc-500 flex-shrink-0" />
                      <span className="truncate max-w-[300px]">{rec.filename}</span>
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm text-zinc-400">
                    {new Date(rec.created_at).toLocaleString('pl-PL', {
                      day: '2-digit',
                      month: '2-digit',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </td>
                  <td className="px-4 py-3 text-sm text-zinc-400 font-mono">
                    {formatDuration(rec.duration)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={rec.status} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      {rec.status === 'error' && (
                        <button
                          onClick={(e) => handleReprocess(rec.id, e)}
                          className="p-1.5 hover:bg-zinc-700 rounded-lg transition-colors"
                          title="Przetwórz ponownie"
                        >
                          <RotateCw className="w-4 h-4 text-zinc-400" />
                        </button>
                      )}
                      <button
                        onClick={(e) => handleDelete(rec.id, e)}
                        className="p-1.5 hover:bg-zinc-700 rounded-lg transition-colors"
                        title="Usuń"
                      >
                        <Trash2 className="w-4 h-4 text-zinc-400 hover:text-red-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="border-t border-zinc-800 px-4 py-3 flex items-center justify-between">
            <span className="text-sm text-zinc-500">
              Strona {data.page} z {data.total_pages}
            </span>
            <div className="flex gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 hover:bg-zinc-800 disabled:opacity-30 rounded-lg transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page === data.total_pages}
                className="p-1.5 hover:bg-zinc-800 disabled:opacity-30 rounded-lg transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

import { useEffect, useState, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search as SearchIcon, FileAudio } from 'lucide-react'
import { api } from '../api/client'
import type { SearchResult } from '../api/types'

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  const search = useCallback(async (q: string) => {
    if (!q.trim()) return
    setLoading(true)
    setSearched(true)
    try {
      const res = await api.searchTranscripts(q.trim())
      setResults(res.results)
    } catch {
      setResults([])
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    const q = searchParams.get('q')
    if (q) {
      setQuery(q)
      search(q)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      setSearchParams({ q: query.trim() })
      search(query.trim())
    }
  }

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  const highlightText = (text: string, q: string) => {
    if (!q.trim()) return text
    const regex = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
    const parts = text.split(regex)
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark key={i} className="bg-yellow-500/30 text-yellow-200 rounded px-0.5">
          {part}
        </mark>
      ) : (
        part
      )
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Wyszukiwanie</h1>
        <p className="text-sm text-zinc-500 mt-1">Szukaj w transkrypcjach nagrań</p>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-3">
        <div className="relative flex-1">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Wpisz szukany tekst..."
            className="w-full pl-10 pr-4 py-3 bg-zinc-900 border border-zinc-800 rounded-xl text-sm
              focus:outline-none focus:border-zinc-600 placeholder:text-zinc-600"
            autoFocus
          />
        </div>
        <button
          type="submit"
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-xl text-sm font-medium transition-colors"
        >
          Szukaj
        </button>
      </form>

      {/* Results */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : searched && results.length === 0 ? (
        <div className="text-center py-16">
          <SearchIcon className="w-12 h-12 text-zinc-700 mx-auto mb-3" />
          <p className="text-zinc-500">Brak wyników dla &quot;{query}&quot;</p>
        </div>
      ) : (
        <div className="space-y-2">
          {results.length > 0 && (
            <p className="text-sm text-zinc-500">{results.length} wyników</p>
          )}
          {results.map((result, i) => (
            <Link
              key={i}
              to={`/recordings/${result.recording_id}${result.start_time != null ? `?t=${result.start_time}` : ''}`}
              className="block bg-zinc-900 border border-zinc-800 rounded-xl p-4 hover:border-zinc-700 transition-colors"
            >
              <div className="flex items-center gap-3 mb-2">
                <FileAudio className="w-4 h-4 text-zinc-500" />
                <span className="text-sm text-zinc-300">{result.filename}</span>
                {result.start_time != null && (
                  <span className="text-xs font-mono text-zinc-500">
                    {formatTime(result.start_time)}
                  </span>
                )}
                {result.speaker && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-700 text-zinc-300">
                    {result.speaker}
                  </span>
                )}
                <span className="text-xs text-zinc-600">{result.match_type}</span>
              </div>
              <p className="text-sm text-zinc-400 leading-relaxed">
                {highlightText(result.text, query)}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

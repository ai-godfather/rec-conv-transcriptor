import type { Segment } from '../api/types'

interface TranscriptViewerProps {
  segments: Segment[]
  currentTime?: number
  onSegmentClick?: (segment: Segment) => void
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function TranscriptViewer({ segments, currentTime, onSegmentClick }: TranscriptViewerProps) {
  const roleLabel = (role: string | null) => {
    if (role === 'agent') return 'Konsultant'
    if (role === 'customer') return 'Klient'
    return 'Nieznany'
  }

  return (
    <div className="space-y-1">
      {segments.map((seg) => {
        const isActive =
          currentTime !== undefined &&
          currentTime >= seg.start_time &&
          currentTime < seg.end_time

        const isAgent = seg.role === 'agent'
        const isCustomer = seg.role === 'customer'

        return (
          <div
            key={seg.id}
            onClick={() => onSegmentClick?.(seg)}
            className={`flex gap-3 p-3 rounded-lg cursor-pointer transition-all group
              ${isActive
                ? isAgent
                  ? 'bg-agent-dim/50 border border-agent/30'
                  : isCustomer
                    ? 'bg-customer-dim/50 border border-customer/30'
                    : 'bg-zinc-800 border border-zinc-600'
                : 'hover:bg-zinc-800/50 border border-transparent'
              }`}
          >
            <div className="flex flex-col items-end min-w-[60px] pt-0.5">
              <span className="text-xs font-mono text-zinc-500">
                {formatTime(seg.start_time)}
              </span>
            </div>

            <div
              className={`w-1 rounded-full self-stretch flex-shrink-0
                ${isAgent ? 'bg-agent' : isCustomer ? 'bg-customer' : 'bg-zinc-600'}`}
            />

            <div className="flex-1 min-w-0">
              <span className={`text-xs font-medium mb-1 block
                ${isAgent ? 'text-agent' : isCustomer ? 'text-customer' : 'text-zinc-400'}`}>
                {roleLabel(seg.role)} ({seg.speaker ?? '?'})
              </span>
              <p className="text-sm text-zinc-300 leading-relaxed">{seg.text}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

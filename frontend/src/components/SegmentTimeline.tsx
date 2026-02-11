import type { Segment } from '../api/types'

interface SegmentTimelineProps {
  segments: Segment[]
  duration: number
  currentTime?: number
  onSegmentClick?: (segment: Segment) => void
}

export function SegmentTimeline({ segments, duration, currentTime, onSegmentClick }: SegmentTimelineProps) {
  if (duration <= 0) return null

  const pct = (t: number) => `${(t / duration) * 100}%`

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
      <h3 className="text-sm font-medium text-zinc-400">Oś czasu rozmówców</h3>

      <div className="relative h-10 bg-zinc-800 rounded-lg overflow-hidden">
        {segments.map((seg) => {
          const isAgent = seg.role === 'agent'
          const isCustomer = seg.role === 'customer'
          return (
            <div
              key={seg.id}
              className={`absolute top-0 h-full cursor-pointer transition-opacity hover:opacity-90
                ${isAgent ? 'bg-agent/60' : isCustomer ? 'bg-customer/60' : 'bg-zinc-600/60'}`}
              style={{
                left: pct(seg.start_time),
                width: pct(seg.end_time - seg.start_time),
              }}
              title={`${seg.speaker ?? '?'}: ${seg.text.slice(0, 50)}...`}
              onClick={() => onSegmentClick?.(seg)}
            />
          )
        })}

        {currentTime !== undefined && currentTime > 0 && (
          <div
            className="absolute top-0 h-full w-0.5 bg-white z-10 pointer-events-none"
            style={{ left: pct(currentTime) }}
          />
        )}
      </div>

      <div className="flex gap-4 text-xs text-zinc-500">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-agent/60" />
          Konsultant
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-customer/60" />
          Klient
        </div>
      </div>
    </div>
  )
}

import type { RecordingStatus } from '../api/types'

const statusConfig: Record<RecordingStatus, { label: string; classes: string }> = {
  pending: { label: 'Oczekujące', classes: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  processing: { label: 'Przetwarzanie', classes: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  done: { label: 'Gotowe', classes: 'bg-green-500/20 text-green-400 border-green-500/30' },
  error: { label: 'Błąd', classes: 'bg-red-500/20 text-red-400 border-red-500/30' },
}

export function StatusBadge({ status }: { status: RecordingStatus }) {
  const cfg = statusConfig[status]
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${cfg.classes}`}>
      {status === 'processing' && (
        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mr-1.5 animate-pulse" />
      )}
      {cfg.label}
    </span>
  )
}

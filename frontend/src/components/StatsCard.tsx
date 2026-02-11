import type { LucideIcon } from 'lucide-react'

interface StatsCardProps {
  title: string
  value: string | number
  icon: LucideIcon
  trend?: string
  color?: string
}

export function StatsCard({ title, value, icon: Icon, trend, color = 'text-zinc-400' }: StatsCardProps) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 hover:border-zinc-700 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-zinc-400">{title}</span>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <div className="text-2xl font-semibold text-zinc-100">{value}</div>
      {trend && <p className="text-xs text-zinc-500 mt-1">{trend}</p>}
    </div>
  )
}

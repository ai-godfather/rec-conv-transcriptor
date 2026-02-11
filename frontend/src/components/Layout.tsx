import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  FileAudio,
  Search,
  Settings,
  Activity,
} from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Panel' },
  { to: '/recordings', icon: FileAudio, label: 'Nagrania' },
  { to: '/search', icon: Search, label: 'Szukaj' },
  { to: '/pipeline', icon: Settings, label: 'Pipeline' },
]

export function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-zinc-950 border-r border-zinc-800 flex flex-col">
        <div className="p-5 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <Activity className="w-6 h-6 text-blue-500" />
            <span className="font-semibold text-lg">Transkrypcje</span>
          </div>
          <p className="text-xs text-zinc-500 mt-1">Call Center Panel</p>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                ${isActive
                  ? 'bg-zinc-800 text-zinc-100'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-zinc-800">
          <p className="text-xs text-zinc-600 text-center">v1.0.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-zinc-950">
        <div className="max-w-7xl mx-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

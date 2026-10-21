import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  FlaskConical,
  Shield,
  Zap,
  Sun,
  Moon,
} from 'lucide-react'

const nav = [
  { to: '/', label: 'Defense Evaluation', icon: Zap },
  { to: '/defense-testing', label: 'Defense Testing', icon: FlaskConical },
  { to: '/dashboard', label: 'Defense Dashboard', icon: LayoutDashboard },
]

export default function Layout() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try { return localStorage.getItem('dashboard-theme') === 'light' ? 'light' : 'dark' }
    catch { return 'dark' }
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('dashboard-theme', theme) } catch { /* Theme still works without storage. */ }
  }, [theme])

  return (
    <div className="flex min-h-screen bg-cyber-bg">
      <button
        type="button"
        className="theme-toggle"
        onClick={() => setTheme(current => current === 'dark' ? 'light' : 'dark')}
        aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      >
        {theme === 'dark' ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
      </button>
      <aside className="w-64 shrink-0 border-r border-gray-800 bg-cyber-surface flex flex-col">
        <div className="p-5 border-b border-gray-800">
          <div className="flex items-start gap-2 text-cyan-400">
            <Shield className="w-7 h-7 shrink-0" />
            <div>
              <span className="font-bold text-sm leading-tight block">
                Autonomous Cyber Defense &amp; Response Engine
              </span>
            </div>
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="p-6 pt-16 max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

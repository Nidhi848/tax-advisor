import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', icon: '💬', label: 'Chat' },
  { to: '/calculator', icon: '🧮', label: 'Tax Calculator' },
  { to: '/documents', icon: '📄', label: 'Document Entry' },
  { to: '/scenarios', icon: '📊', label: 'Scenarios' },
  { to: '/profile', icon: '👤', label: 'Profile' },
]

export default function Sidebar() {
  return (
    <aside className="w-56 bg-slate-800 text-white flex flex-col">
      <div className="p-6 border-b border-slate-700">
        <h1 className="font-semibold text-lg">Tax Advisor</h1>
        <p className="text-slate-400 text-sm mt-1">2025 US Federal</p>
      </div>
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {navItems.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                isActive ? 'bg-slate-700 text-white' : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
              }`
            }
          >
            <span className="text-xl">{icon}</span>
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-slate-700 text-xs text-slate-400">
        <p>💾 All data stored locally</p>
        <p className="mt-0.5">🔒 Only tax figures sent to Claude API</p>
        <p className="mt-0.5">Never your name or employer</p>
      </div>
    </aside>
  )
}

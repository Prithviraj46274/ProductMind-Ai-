import React, { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useWorkspace } from '../../context/WorkspaceContext'
import {
  LayoutDashboard,
  MessageSquareText,
  Sparkles,
  SlidersHorizontal,
  FileText,
  Milestone,
  BotMessageSquare,
  TrendingUp,
  Layers,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  LogOut,
  Building2,
  Plus,
  Check,
  X,
  Loader2,
} from 'lucide-react'

export function Sidebar({ collapsed, setCollapsed }) {
  const { currentUser, logout } = useAuth()
  const {
    workspaces,
    currentWorkspace,
    selectWorkspace,
    createWorkspace,
    isLoadingWorkspaces,
  } = useWorkspace()

  const [isWorkspaceMenuOpen, setIsWorkspaceMenuOpen] = useState(false)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [newWorkspaceName, setNewWorkspaceName] = useState('')
  const [createError, setCreateError] = useState(null)
  const [isSubmittingWorkspace, setIsSubmittingWorkspace] = useState(false)

  const handleCreateWorkspace = async (e) => {
    e.preventDefault()
    if (!newWorkspaceName.trim()) return

    setIsSubmittingWorkspace(true)
    setCreateError(null)

    const res = await createWorkspace({ name: newWorkspaceName.trim() })
    setIsSubmittingWorkspace(false)
    if (res.success) {
      setNewWorkspaceName('')
      setIsCreateModalOpen(false)
      setIsWorkspaceMenuOpen(false)
    } else {
      setCreateError(res.error || 'Failed to create workspace')
    }
  }

  const navItems = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Product Analytics', path: '/analytics', icon: TrendingUp, badge: 'Data' },
    { name: 'Feedback Explorer', path: '/feedback', icon: MessageSquareText },
    { name: 'Feature Aggregation', path: '/aggregation', icon: Layers, badge: 'New' },
    { name: 'Prioritization', path: '/prioritization', icon: SlidersHorizontal },
    { name: 'PRD Studio', path: '/prd-generator', icon: FileText },
    { name: 'Roadmap', path: '/roadmap', icon: Milestone },
    { name: 'AI Copilot', path: '/copilot', icon: BotMessageSquare, badge: 'Live' },
  ]

  return (
    <aside
      className={`relative flex flex-col shrink-0 bg-white dark:bg-navy-900 border-r border-slate-200 dark:border-slate-800/80 transition-all duration-300 z-30 select-none ${
        collapsed ? 'w-18' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-slate-200 dark:border-slate-800/80">
        <NavLink to="/" className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-600 via-brand-500 to-electric-500 flex items-center justify-center text-white font-black shadow-glow-sm shrink-0">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <div className="flex flex-col truncate">
              <span className="font-bold text-sm tracking-tight text-slate-900 dark:text-white flex items-center gap-1.5">
                Product Mind
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-500/10 text-brand-600 dark:text-brand-400 font-extrabold border border-brand-500/20">
                  AI
                </span>
              </span>
              <span className="text-[11px] text-slate-400 dark:text-slate-500 truncate">
                Product Intelligence
              </span>
            </div>
          )}
        </NavLink>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Workspace Selector (Non-collapsed) */}
      {!collapsed && (
        <div className="relative px-3 my-2">
          <button
            type="button"
            onClick={() => setIsWorkspaceMenuOpen(!isWorkspaceMenuOpen)}
            className="w-full text-left px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-navy-950/70 border border-slate-200/80 dark:border-slate-800/60 hover:border-brand-500/50 flex items-center justify-between gap-2 transition-all cursor-pointer group"
          >
            <div className="flex items-center gap-2.5 truncate">
              <div className="w-6 h-6 rounded-md bg-brand-500/10 dark:bg-brand-500/20 flex items-center justify-center text-brand-600 dark:text-brand-400 shrink-0">
                <Building2 className="w-3.5 h-3.5" />
              </div>
              <div className="flex flex-col truncate">
                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                  {currentWorkspace?.name || currentUser?.workspaceName || 'Select Workspace'}
                </span>
                <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
                  {currentWorkspace?.plan ? `${currentWorkspace.plan.toUpperCase()} Plan` : 'Live Workspace'}
                </span>
              </div>
            </div>
            <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isWorkspaceMenuOpen ? 'rotate-180' : ''}`} />
          </button>

          {/* Workspace Switcher Popover */}
          {isWorkspaceMenuOpen && (
            <div className="absolute top-full left-3 right-3 mt-1.5 p-1.5 bg-white dark:bg-navy-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-50 animate-in fade-in zoom-in-95 duration-100">
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 py-1">
                Workspaces
              </div>
              <div className="max-h-48 overflow-y-auto space-y-0.5">
                {workspaces.map((ws) => {
                  const isCurrent = (currentWorkspace?.id === ws.id || currentWorkspace?.slug === ws.slug)
                  return (
                    <button
                      key={ws.id}
                      onClick={() => {
                        selectWorkspace(ws.id)
                        setIsWorkspaceMenuOpen(false)
                      }}
                      className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition-colors cursor-pointer ${
                        isCurrent
                          ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/70 dark:text-brand-300 font-medium'
                          : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                      }`}
                    >
                      <span className="truncate">{ws.name}</span>
                      {isCurrent && <Check className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400 shrink-0" />}
                    </button>
                  )
                })}
              </div>
              <div className="border-t border-slate-100 dark:border-slate-800 mt-1 pt-1">
                <button
                  onClick={() => {
                    setIsWorkspaceMenuOpen(false)
                    setIsCreateModalOpen(true)
                  }}
                  className="w-full flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-brand-600 hover:bg-brand-50 dark:text-brand-400 dark:hover:bg-slate-800/80 transition-colors cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Create Workspace</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Navigation List */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-2 space-y-0.5">
        {navItems.map(item => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `group relative flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/70 dark:text-brand-300 font-semibold shadow-sm border border-brand-200/60 dark:border-brand-800/50'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100/80 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-slate-200'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0 transition-transform group-hover:scale-105" />
              {!collapsed && <span className="truncate">{item.name}</span>}
              {!collapsed && item.badge && (
                <span className="ml-auto text-[9px] font-bold px-1.5 py-0.2 rounded-full bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20">
                  {item.badge}
                </span>
              )}

              {/* Tooltip in collapsed mode */}
              {collapsed && (
                <div className="absolute left-full ml-3 px-2.5 py-1 bg-slate-900 text-white text-xs rounded-md shadow-xl whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-50">
                  {item.name}
                </div>
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* Settings link & User profile bottom pill */}
      <div className="p-3 border-t border-slate-200 dark:border-slate-800/80 space-y-2">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `group relative flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-150 ${
              isActive
                ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/70 dark:text-brand-300 font-semibold shadow-sm border border-brand-200/60 dark:border-brand-800/50'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100/80 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-slate-200'
            }`
          }
        >
          <Settings className="w-4 h-4 shrink-0 transition-transform group-hover:scale-105" />
          {!collapsed && <span className="truncate">Settings</span>}
          {collapsed && (
            <div className="absolute left-full ml-3 px-2.5 py-1 bg-slate-900 text-white text-xs rounded-md shadow-xl whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-50">
              Settings
            </div>
          )}
        </NavLink>

        <div className="flex items-center justify-between gap-2 p-1.5 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200/80 dark:border-slate-800/60">
          <div className="flex items-center gap-2.5 truncate">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-600 to-electric-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
              {currentUser?.avatar || 'PM'}
            </div>
            {!collapsed && (
              <div className="flex flex-col truncate">
                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                  {currentUser?.name || 'Alex Rivera'}
                </span>
                <span className="text-[10px] text-slate-400 dark:text-slate-500 truncate">
                  {currentUser?.role || 'Lead PM'}
                </span>
              </div>
            )}
          </div>

          {!collapsed && (
            <button
              onClick={logout}
              title="Sign Out"
              className="p-1.5 text-slate-400 hover:text-rose-500 dark:hover:text-rose-400 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Create Workspace Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-md bg-white dark:bg-navy-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-brand-600 dark:text-brand-400" />
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Create New Workspace
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsCreateModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {createError && (
              <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/50 text-rose-600 dark:text-rose-400 text-xs">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateWorkspace} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Workspace Name
                </label>
                <input
                  type="text"
                  value={newWorkspaceName}
                  onChange={(e) => setNewWorkspaceName(e.target.value)}
                  placeholder="e.g. Acme Product Ops"
                  required
                  autoFocus
                  className="w-full px-3 py-2 rounded-lg text-sm bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500 text-slate-900 dark:text-white placeholder-slate-400"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-3 py-2 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingWorkspace || !newWorkspaceName.trim()}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 disabled:opacity-50 transition-colors flex items-center gap-1.5"
                >
                  {isSubmittingWorkspace && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Create Workspace</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </aside>
  )
}

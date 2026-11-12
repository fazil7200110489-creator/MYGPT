import React, { useState } from 'react'
import {
  Plus, Search, MessageSquare, Trash2, Edit2, Check, X,
  Settings, HelpCircle, ChevronLeft, ChevronRight, Sparkles
} from 'lucide-react'

export interface Conversation {
  id: string
  title: string
  updated_at: number
  created_at?: number
  message_count?: number
  last_preview?: string
  active_document_name?: string
}

export interface ConversationSidebarProps {
  conversations: Conversation[]
  activeId: string
  onSelect: (id: string) => void
  onNewChat: () => void
  onDelete: (id: string, e: React.MouseEvent) => void
  onRename: (id: string, newTitle: string) => Promise<void>
  isOpen: boolean
  onToggle: () => void
  onOpenSettings?: () => void
  onOpenHelp?: () => void
}

export const ConversationSidebar: React.FC<ConversationSidebarProps> = ({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  onRename,
  isOpen,
  onToggle,
  onOpenSettings,
  onOpenHelp
}) => {
  const [search, setSearch] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')

  // Filter conversations by search term
  const filtered = conversations.filter(c =>
    (c.title || 'Untitled Conversation').toLowerCase().includes(search.toLowerCase())
  )

  // Categorize by time
  const now = Date.now() / 1000
  const oneDay = 86400
  const sevenDays = 7 * oneDay

  const todayChats = filtered.filter(c => (now - (c.updated_at || now)) < oneDay)
  const last7DaysChats = filtered.filter(c => {
    const diff = now - (c.updated_at || now)
    return diff >= oneDay && diff < sevenDays
  })
  const olderChats = filtered.filter(c => (now - (c.updated_at || now)) >= sevenDays)

  const handleStartRename = (c: Conversation, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingId(c.id)
    setEditTitle(c.title || 'New Chat')
  }

  const handleSaveRename = async (id: string, e?: React.MouseEvent | React.FormEvent) => {
    if (e) e.stopPropagation()
    if (editTitle.trim()) {
      await onRename(id, editTitle.trim())
    }
    setEditingId(null)
  }

  const handleCancelRename = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingId(null)
  }

  if (!isOpen) {
    return (
      <div className="flex flex-col items-center py-4 px-2 border-r border-slate-200/80 bg-slate-50/70 h-full w-14 transition-all">
        <button
          onClick={onToggle}
          className="p-2 rounded-xl text-slate-500 hover:bg-slate-200/70 hover:text-slate-800 transition-colors mb-4"
          title="Open sidebar"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
        <button
          onClick={onNewChat}
          className="p-2.5 rounded-xl bg-slate-900 text-white shadow-xs hover:bg-slate-800 transition-all"
          title="New Chat"
        >
          <Plus className="h-4.5 w-4.5" />
        </button>
      </div>
    )
  }

  const renderSection = (title: string, list: Conversation[]) => {
    if (list.length === 0) return null

    return (
      <div className="mb-4">
        <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </div>
        <div className="space-y-0.5">
          {list.map(c => {
            const isActive = c.id === activeId
            const isEditing = c.id === editingId

            return (
              <div
                key={c.id}
                onClick={() => onSelect(c.id)}
                className={`group relative flex items-center justify-between rounded-xl px-3 py-2 text-xs font-medium cursor-pointer transition-all ${
                  isActive
                    ? 'bg-white text-slate-900 shadow-xs border border-slate-200/90 font-semibold'
                    : 'text-slate-600 hover:bg-slate-200/60 hover:text-slate-900'
                }`}
              >
                {isEditing ? (
                  <div className="flex items-center gap-1.5 w-full" onClick={e => e.stopPropagation()}>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={e => setEditTitle(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') handleSaveRename(c.id)
                        if (e.key === 'Escape') setEditingId(null)
                      }}
                      autoFocus
                      className="flex-1 bg-white border border-slate-300 rounded-md px-1.5 py-0.5 text-xs text-slate-900 focus:outline-hidden focus:border-slate-500"
                    />
                    <button
                      onClick={e => handleSaveRename(c.id, e)}
                      className="p-1 text-emerald-600 hover:bg-emerald-50 rounded-md"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={handleCancelRename}
                      className="p-1 text-slate-400 hover:bg-slate-100 rounded-md"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-2.5 truncate flex-1 mr-2">
                      <MessageSquare className={`h-3.5 w-3.5 shrink-0 ${isActive ? 'text-slate-800' : 'text-slate-400'}`} />
                      <span className="truncate">{c.title || 'Untitled Conversation'}</span>
                    </div>

                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={e => handleStartRename(c, e)}
                        className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                        title="Rename conversation"
                      >
                        <Edit2 className="h-3 w-3" />
                      </button>
                      <button
                        onClick={e => onDelete(c.id, e)}
                        className="p-1 rounded-md text-slate-400 hover:text-red-600 hover:bg-red-50"
                        title="Delete conversation"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  </>
                )}
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <aside className="flex flex-col h-full w-64 border-r border-slate-200/90 bg-slate-50/80 backdrop-blur-xl shrink-0 select-none">
      {/* Top Header: Logo & Sidebar Toggle */}
      <div className="flex items-center justify-between px-4 py-3.5 border-b border-slate-200/70">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-linear-to-tr from-slate-900 to-slate-700 text-white shadow-xs">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-slate-900">MYGPT</h1>
            <p className="text-[10px] text-slate-400 font-medium">Local AI Assistant</p>
          </div>
        </div>

        <button
          onClick={onToggle}
          className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-200/70 hover:text-slate-700 transition-colors"
          title="Collapse sidebar"
        >
          <ChevronLeft className="h-4.5 w-4.5" />
        </button>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="flex w-full items-center justify-between rounded-xl border border-slate-200/90 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-800 shadow-2xs transition-all hover:border-slate-300 hover:bg-slate-50 active:scale-98"
        >
          <div className="flex items-center gap-2">
            <Plus className="h-4 w-4 text-slate-700" />
            <span>New Chat</span>
          </div>
          <span className="text-[10px] text-slate-400 font-normal">Ctrl+N</span>
        </button>
      </div>

      {/* Search Input */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search conversations..."
            className="w-full rounded-lg border border-slate-200/80 bg-white/70 pl-8 pr-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-hidden focus:border-slate-400 focus:bg-white transition-all"
          />
        </div>
      </div>

      {/* Conversations Scroll Area */}
      <div className="flex-1 overflow-y-auto px-3 py-1">
        {filtered.length === 0 ? (
          <div className="text-center py-8 text-xs text-slate-400">
            {search ? 'No matching conversations' : 'No conversations yet'}
          </div>
        ) : (
          <>
            {renderSection('Today', todayChats)}
            {renderSection('Previous 7 Days', last7DaysChats)}
            {renderSection('Older', olderChats)}
          </>
        )}
      </div>

      {/* Bottom Settings & Help */}
      <div className="border-t border-slate-200/80 p-2 space-y-0.5 bg-slate-100/50">
        <button
          onClick={onOpenSettings}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-slate-600 hover:bg-white hover:text-slate-900 transition-colors"
        >
          <Settings className="h-4 w-4 text-slate-400" />
          <span>Settings</span>
        </button>
        <button
          onClick={onOpenHelp}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-slate-600 hover:bg-white hover:text-slate-900 transition-colors"
        >
          <HelpCircle className="h-4 w-4 text-slate-400" />
          <span>Help & Shortcuts</span>
        </button>
      </div>
    </aside>
  )
}

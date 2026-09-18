import React, { useState, useEffect, useRef } from 'react'
import {
  Send, Bot, User, Sparkles, RefreshCw, Shield,
  FileSpreadsheet, CheckCircle2, Download, Paperclip, X, AlertCircle,
  Table, Plus, MessageSquare, Trash2, ChevronLeft, Search, UserCheck
} from 'lucide-react'
import { api } from '../services/api'
import { ExcelViewerModal } from './ExcelViewerModal'

interface AttachedDoc {
  id: string
  filename: string
  file_type: string
  document_type?: string
  size_kb?: number
  upload_time?: string
}

interface ChatMessage {
  id: string
  sender: 'user' | 'assistant'
  text: string
  department?: string
  intent?: string
  sources?: Array<{ doc_id: string; title: string }>
  actions?: string[]
  files?: Array<{ file_id?: string; filename: string; type: string; size_kb?: number; data_base64?: string }>
  requires_approval?: boolean
  execution_steps?: string[]
  status?: string
  timestamp: string
  tool_results?: any
}

interface ConversationItem {
  id: string
  title: string
  updated_at: number
  created_at?: number
  message_count?: number
  last_preview?: string
  active_document_name?: string
  document_count?: number
}

interface AIStatus {
  company_ai: string
  mygpt: string
  answer_model: string
  answer_model_status: string
  external_ai: boolean
  device?: string
  runtime?: string
}

export const CompanyAIChat: React.FC = () => {
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string>(() => {
    return localStorage.getItem('mygpt_active_conversation') || 'company_session_' + Math.random().toString(36).substring(2, 9)
  })
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sidebarSearch, setSidebarSearch] = useState('')

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [userRole, setUserRole] = useState<'EMPLOYEE' | 'HR_MANAGER' | 'FINANCE_MANAGER' | 'TECH_ADMIN' | 'ADMIN'>('EMPLOYEE')
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null)
  const [attachedDocs, setAttachedDocs] = useState<AttachedDoc[]>([])
  const [activeDocId, setActiveDocId] = useState<string | null>(null)
  const [stagedFiles, setStagedFiles] = useState<File[]>([])
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [viewerModal, setViewerModal] = useState<{ isOpen: boolean; fileId: string | null; filename: string }>({
    isOpen: false,
    fileId: null,
    filename: ''
  })

  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Save active conversation id to localStorage
  useEffect(() => {
    if (activeConversationId) {
      localStorage.setItem('mygpt_active_conversation', activeConversationId)
    }
  }, [activeConversationId])

  // Fetch conversations list and AI status on mount
  const loadConversationsList = async () => {
    try {
      const list = await api.getConversations()
      if (Array.isArray(list)) {
        setConversations(list)
      }
    } catch (err) {
      console.error('Failed to load conversations list:', err)
    }
  }

  useEffect(() => {
    loadConversationsList()
    const checkStatus = async () => {
      try {
        const status = await api.getAIStatus()
        setAiStatus(status)
      } catch (err) {
        console.error('Failed to get AI status:', err)
      }
    }
    checkStatus()
    const interval = setInterval(checkStatus, 60000)
    return () => clearInterval(interval)
  }, [])

  // Load active conversation messages and documents upon switching
  useEffect(() => {
    const loadActiveChat = async () => {
      if (!activeConversationId) return
      setIsLoading(true)
      try {
        const conv = await api.getConversation(activeConversationId)
        if (conv && Array.isArray(conv.messages)) {
          setMessages(conv.messages)
        } else {
          setMessages([])
        }

        // Restore documents
        if (conv && Array.isArray(conv.documents) && conv.documents.length > 0) {
          const restoredDocs: AttachedDoc[] = conv.documents.map((d: any) => ({
            id: d.id || d.document_id,
            filename: d.filename || d.name,
            file_type: d.file_type || '.xlsx',
            document_type: d.document_type || 'EXCEL',
            size_kb: d.file_size ? Math.round(d.file_size / 1024) : 24,
            upload_time: d.upload_time ? new Date(d.upload_time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Saved'
          }))
          setAttachedDocs(restoredDocs)
          setActiveDocId(conv.active_document_id || (restoredDocs[0] ? restoredDocs[0].id : null))
        } else {
          setAttachedDocs([])
          setActiveDocId(null)
        }
      } catch (err) {
        console.error('Failed to restore conversation:', err)
      } finally {
        setIsLoading(false)
      }
    }
    loadActiveChat()
  }, [activeConversationId])

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Create new conversation
  const handleNewChat = () => {
    const newId = 'company_session_' + Math.random().toString(36).substring(2, 9)
    setActiveConversationId(newId)
    setMessages([])
    setAttachedDocs([])
    setActiveDocId(null)
    setStagedFiles([])
    setInputValue('')
  }

  // Delete conversation
  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await api.deleteConversation(convId)
      setConversations(prev => prev.filter(c => c.id !== convId))
      if (activeConversationId === convId) {
        handleNewChat()
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err)
    }
  }

  // Handle Multi-file selection staging
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    const newFileList = Array.from(files)
    setStagedFiles(prev => [...prev, ...newFileList])
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleRemoveStagedFile = (index: number) => {
    setStagedFiles(prev => prev.filter((_, i) => i !== index))
  }

  // Upload staged files if any
  const uploadStagedFiles = async (): Promise<AttachedDoc[]> => {
    if (stagedFiles.length === 0) return []
    setIsUploading(true)
    setUploadError(null)

    try {
      const res = await api.uploadMultipleCompanyDocuments(
        stagedFiles,
        activeConversationId,
        userRole,
        `user_${userRole.toLowerCase()}`
      )

      if (res.success && Array.isArray(res.documents)) {
        const newlyUploaded: AttachedDoc[] = res.documents.map((d: any) => ({
          id: d.doc_id || d.id,
          filename: d.filename,
          file_type: d.file_type,
          document_type: d.document_type || 'EXCEL',
          size_kb: Math.round(24),
          upload_time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }))

        setAttachedDocs(prev => {
          const ids = new Set(newlyUploaded.map(n => n.id))
          return [...prev.filter(d => !ids.has(d.id)), ...newlyUploaded]
        })
        if (newlyUploaded.length > 0) {
          setActiveDocId(newlyUploaded[newlyUploaded.length - 1].id)
        }
        setStagedFiles([])
        return newlyUploaded
      }
      return []
    } catch (err: any) {
      console.error('Upload failed:', err)
      setUploadError(err.message || 'Multiple file upload failed')
      return []
    } finally {
      setIsUploading(false)
    }
  }

  // Send message
  const handleSendMessage = async (textToSend?: string) => {
    const rawText = (textToSend ?? inputValue).trim()
    if (!rawText && stagedFiles.length === 0) return

    let userMessageText = rawText
    let newlyUploaded: AttachedDoc[] = []

    if (stagedFiles.length > 0) {
      newlyUploaded = await uploadStagedFiles()
      if (!userMessageText) {
        userMessageText = `Uploaded ${newlyUploaded.map(f => f.filename).join(', ')}`
      }
    }

    const currentDoc = activeDocId || (attachedDocs.length > 0 ? attachedDocs[attachedDocs.length - 1].id : undefined)

    // Add user message to state
    const userMsg: ChatMessage = {
      id: 'usr_' + Date.now(),
      sender: 'user',
      text: userMessageText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }

    setMessages(prev => [...prev, userMsg])
    setInputValue('')
    setIsLoading(true)

    try {
      const response = await api.sendCompanyChat({
        message: userMessageText,
        sessionId: activeConversationId,
        conversationId: activeConversationId,
        userRole: userRole,
        userId: `user_${userRole.toLowerCase()}`,
        documentId: currentDoc
      })

      const assistantMsg: ChatMessage = {
        id: 'asst_' + Date.now(),
        sender: 'assistant',
        text: response.answer,
        department: response.department,
        intent: response.intent,
        sources: response.sources || [],
        actions: response.actions || [],
        files: response.files || [],
        requires_approval: response.requires_approval,
        execution_steps: response.execution_steps || [],
        status: response.status || 'success',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        tool_results: response.tool_results
      }

      setMessages(prev => [...prev, assistantMsg])
      // Refresh sidebar conversation list to reflect updated title & timestamps
      loadConversationsList()
    } catch (err: any) {
      console.error('Chat error:', err)
      const errorMsg: ChatMessage = {
        id: 'err_' + Date.now(),
        sender: 'assistant',
        text: `⚠️ **Error:** ${err.message || 'Failed to process request. Please try again.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
  }

  // Filter conversations for sidebar
  const filteredConversations = conversations.filter(c =>
    c.title?.toLowerCase().includes(sidebarSearch.toLowerCase()) ||
    c.last_preview?.toLowerCase().includes(sidebarSearch.toLowerCase())
  )

  // Group conversations by date (Today, Yesterday, Previous 7 Days, Older)
  const groupConversations = () => {
    const today: ConversationItem[] = []
    const yesterday: ConversationItem[] = []
    const prevWeek: ConversationItem[] = []
    const older: ConversationItem[] = []

    const now = Date.now() / 1000
    const oneDay = 86400
    const sevenDays = 7 * oneDay

    filteredConversations.forEach(c => {
      const diff = now - (c.updated_at || now)
      if (diff < oneDay) {
        today.push(c)
      } else if (diff < 2 * oneDay) {
        yesterday.push(c)
      } else if (diff < sevenDays) {
        prevWeek.push(c)
      } else {
        older.push(c)
      }
    })

    return { today, yesterday, prevWeek, older }
  }

  const { today, yesterday, prevWeek, older } = groupConversations()

  return (
    <div className="flex h-full w-full bg-[var(--background)] text-[var(--text)] overflow-hidden font-sans">
      {/* Left Sidebar (ChatGPT-Style) */}
      <div
        className={`bg-[#0c101b] border-r border-[var(--border)] flex flex-col transition-all duration-300 z-20 shrink-0 ${
          sidebarOpen ? 'w-64 md:w-72' : 'w-0 -translate-x-full overflow-hidden'
        }`}
      >
        {/* Sidebar Header: New Chat Button */}
        <div className="p-3 border-b border-[var(--border)]">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-semibold py-2.5 px-4 rounded-xl shadow-md transition-all text-xs md:text-sm cursor-pointer"
          >
            <Plus size={16} />
            <span>New Chat</span>
          </button>
        </div>

        {/* Search Input */}
        <div className="p-3 border-b border-[var(--border)]">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 text-[var(--text-dim)]" size={14} />
            <input
              type="text"
              placeholder="Search conversations..."
              value={sidebarSearch}
              onChange={e => setSidebarSearch(e.target.value)}
              className="w-full bg-[#151c2c] text-xs text-[var(--text)] placeholder-[var(--text-dim)] pl-8 pr-3 py-1.5 rounded-lg border border-[var(--border)] focus:outline-none focus:border-[var(--accent)]"
            />
          </div>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-4 text-xs">
          {today.length > 0 && (
            <div>
              <div className="px-2.5 py-1 text-[10px] font-bold text-[var(--text-dim)] uppercase tracking-wider">Today</div>
              <div className="space-y-1">
                {today.map(c => renderConversationRow(c))}
              </div>
            </div>
          )}

          {yesterday.length > 0 && (
            <div>
              <div className="px-2.5 py-1 text-[10px] font-bold text-[var(--text-dim)] uppercase tracking-wider">Yesterday</div>
              <div className="space-y-1">
                {yesterday.map(c => renderConversationRow(c))}
              </div>
            </div>
          )}

          {prevWeek.length > 0 && (
            <div>
              <div className="px-2.5 py-1 text-[10px] font-bold text-[var(--text-dim)] uppercase tracking-wider">Previous 7 Days</div>
              <div className="space-y-1">
                {prevWeek.map(c => renderConversationRow(c))}
              </div>
            </div>
          )}

          {older.length > 0 && (
            <div>
              <div className="px-2.5 py-1 text-[10px] font-bold text-[var(--text-dim)] uppercase tracking-wider">Older</div>
              <div className="space-y-1">
                {older.map(c => renderConversationRow(c))}
              </div>
            </div>
          )}

          {conversations.length === 0 && (
            <div className="text-center py-10 text-[var(--text-dim)]">
              <MessageSquare size={24} className="mx-auto mb-2 opacity-40" />
              <p className="font-medium">No chat history</p>
              <p className="text-[11px] opacity-75">Click 'New Chat' to start.</p>
            </div>
          )}
        </div>

        {/* Sidebar Footer */}
        <div className="p-3 border-t border-[var(--border)] bg-[#090d16] flex items-center justify-between text-xs text-[var(--text-muted)]">
          <div className="flex items-center gap-2">
            <Shield size={14} className="text-[var(--accent)]" />
            <span className="font-semibold text-[var(--text)]">MYGPT AI</span>
          </div>
          <select
            value={userRole}
            onChange={e => setUserRole(e.target.value as any)}
            className="bg-[#151c2c] border border-[var(--border)] rounded-md px-2 py-1 text-[11px] text-[var(--text)] focus:outline-none focus:border-[var(--accent)] cursor-pointer"
          >
            <option value="EMPLOYEE">Employee</option>
            <option value="HR_MANAGER">HR Manager</option>
            <option value="FINANCE_MANAGER">Finance</option>
            <option value="TECH_ADMIN">Tech Admin</option>
            <option value="ADMIN">Admin</option>
          </select>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative bg-[var(--background)]">
        {/* Top Header */}
        <header className="h-14 border-b border-[var(--border)] bg-[#0d121f]/90 backdrop-blur-md flex items-center justify-between px-4 md:px-6 z-10 shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1.5 text-[var(--text-muted)] hover:text-white hover:bg-[#151c2c] rounded-lg transition-colors cursor-pointer"
              title={sidebarOpen ? 'Collapse sidebar' : 'Open sidebar'}
            >
              <ChevronLeft className={`transition-transform duration-200 ${!sidebarOpen ? 'rotate-180' : ''}`} size={18} />
            </button>
            <div className="flex items-center gap-2.5">
              <span className="font-bold text-[var(--text)] text-sm tracking-tight truncate max-w-xs md:max-w-md">
                {conversations.find(c => c.id === activeConversationId)?.title || 'Company AI Workspace'}
              </span>
              <span className="text-[10px] font-semibold text-[var(--text-muted)] bg-[#151c2c] border border-[var(--border)] px-2 py-0.5 rounded-full">
                {userRole.replace('_', ' ')}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs">
            {attachedDocs.length > 0 && (
              <div className="flex items-center gap-1.5 bg-[#151c2c] border border-[var(--border)] px-2.5 py-1 rounded-full text-[var(--text-muted)] text-[11px]">
                <FileSpreadsheet size={13} className="text-emerald-400" />
                <span className="font-medium text-[var(--text)]">{attachedDocs.length} Active Document{attachedDocs.length > 1 ? 's' : ''}</span>
              </div>
            )}
            <div className="flex items-center gap-1.5 text-emerald-400 font-medium bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>{aiStatus?.answer_model || 'Qwen AI'} Online</span>
            </div>
          </div>
        </header>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6 max-w-4xl w-full mx-auto">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 text-[var(--text-muted)]">
              <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-[var(--accent)] mb-4 shadow-lg">
                <Sparkles size={28} />
              </div>
              <h2 className="text-xl font-bold text-[var(--text)] mb-2">Welcome to MYGPT Company AI</h2>
              <p className="max-w-md text-xs md:text-sm text-[var(--text-muted)] mb-6 leading-relaxed">
                Deterministic verified calculations across Finance, HR, and Tech. Attach multiple spreadsheets for instant reconciliation, metric extraction, and reporting.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-lg text-left">
                <button
                  onClick={() => handleSendMessage('Give me the full summary of the document')}
                  className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--accent)] hover:bg-[#162032] text-xs text-[var(--text)] transition-all shadow-sm cursor-pointer"
                >
                  📊 <strong className="text-white">Excel Summary:</strong> "Give me the full summary"
                </button>
                <button
                  onClick={() => handleSendMessage('What is the highest transaction?')}
                  className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--accent)] hover:bg-[#162032] text-xs text-[var(--text)] transition-all shadow-sm cursor-pointer"
                >
                  📈 <strong className="text-white">Maximum Value:</strong> "What is the highest transaction?"
                </button>
                <button
                  onClick={() => handleSendMessage('Which mode has the highest transaction?')}
                  className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--accent)] hover:bg-[#162032] text-xs text-[var(--text)] transition-all shadow-sm cursor-pointer"
                >
                  🏷️ <strong className="text-white">Group Max:</strong> "Which mode has the highest transaction?"
                </button>
                <button
                  onClick={() => handleSendMessage('What are the headings of the excel?')}
                  className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--accent)] hover:bg-[#162032] text-xs text-[var(--text)] transition-all shadow-sm cursor-pointer"
                >
                  📋 <strong className="text-white">Columns:</strong> "What are the headings?"
                </button>
              </div>
            </div>
          ) : (
            messages.map(msg => renderMessage(msg))
          )}

          {isLoading && (
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-white shrink-0 text-xs shadow-md">
                <Bot size={16} />
              </div>
              <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl rounded-tl-xs p-4 shadow-md flex items-center gap-2.5 text-xs text-[var(--text-muted)]">
                <RefreshCw size={14} className="animate-spin text-[var(--accent)]" />
                <span>Thinking & calculating verified result...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input & Staging Bar */}
        <div className="border-t border-[var(--border)] bg-[#090d16] p-3 md:p-4 max-w-4xl w-full mx-auto">
          {/* Staged files chips bar */}
          {stagedFiles.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2.5 p-2 bg-[#151c2c] border border-[var(--border)] rounded-xl">
              {stagedFiles.map((f, i) => (
                <div key={i} className="flex items-center gap-1.5 bg-[#1a2336] border border-[#2b3952] px-3 py-1 rounded-lg text-xs shadow-xs text-[var(--text)]">
                  <FileSpreadsheet size={13} className="text-emerald-400" />
                  <span className="font-medium max-w-xs truncate">{f.name}</span>
                  <span className="text-[10px] text-[var(--text-dim)]">({Math.round(f.size / 1024)} KB)</span>
                  <button
                    onClick={() => handleRemoveStagedFile(i)}
                    className="text-[var(--text-dim)] hover:text-rose-400 ml-1 cursor-pointer"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {uploadError && (
            <div className="mb-2.5 p-2.5 text-xs bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-xl flex items-center gap-2">
              <AlertCircle size={14} />
              <span>{uploadError}</span>
            </div>
          )}

          <div className="flex items-end gap-2 bg-[#151c2c] border border-[var(--border)] rounded-2xl p-2 focus-within:border-[var(--accent)] focus-within:ring-2 focus-within:ring-indigo-500/20 shadow-lg transition-all">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="p-2.5 text-[var(--text-dim)] hover:text-white hover:bg-[#202b40] rounded-xl transition-colors cursor-pointer"
              title="Attach files (multi-selection supported)"
            >
              <Paperclip size={18} />
            </button>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              multiple
              accept=".xlsx,.xls,.csv,.pdf,.docx,.txt"
              className="hidden"
            />

            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSendMessage()
                }
              }}
              placeholder={stagedFiles.length > 0 ? "Add a message or press Send to process attached files..." : "Ask Company AI anything (e.g. 'What is the highest transaction?', 'Compare these two files')..."}
              rows={1}
              className="flex-1 bg-transparent border-0 resize-none text-xs md:text-sm py-2 px-1 text-[var(--text)] placeholder-[var(--text-dim)] focus:outline-none max-h-32 min-h-[38px]"
            />

            <button
              onClick={() => handleSendMessage()}
              disabled={isLoading || (!inputValue.trim() && stagedFiles.length === 0)}
              className={`p-2.5 rounded-xl font-medium transition-all ${
                inputValue.trim() || stagedFiles.length > 0
                  ? 'bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white shadow-md cursor-pointer'
                  : 'bg-[#202b40] text-gray-500 cursor-not-allowed'
              }`}
            >
              <Send size={16} />
            </button>
          </div>
          <div className="text-[11px] text-center text-[var(--text-dim)] mt-2">
            MYGPT Company AI produces deterministic verified business calculations.
          </div>
        </div>
      </div>

      {/* Full Excel Viewer Modal */}
      {viewerModal.isOpen && (
        <ExcelViewerModal
          isOpen={viewerModal.isOpen}
          onClose={() => setViewerModal({ isOpen: false, fileId: null, filename: '' })}
          fileId={viewerModal.fileId}
          filename={viewerModal.filename}
          userRole={userRole}
          userId={`user_${userRole.toLowerCase()}`}
        />
      )}
    </div>
  )

  // Helper row renderer for left sidebar
  function renderConversationRow(conv: ConversationItem) {
    const isActive = conv.id === activeConversationId
    return (
      <div
        key={conv.id}
        onClick={() => setActiveConversationId(conv.id)}
        className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-all ${
          isActive
            ? 'bg-[var(--accent)]/15 border border-[var(--accent)]/40 text-white font-semibold shadow-xs'
            : 'text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[#151c2c] border border-transparent'
        }`}
      >
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <MessageSquare size={14} className={isActive ? 'text-[var(--accent)]' : 'text-[var(--text-dim)]'} />
          <span className="truncate">{conv.title || 'Untitled Conversation'}</span>
        </div>
        <button
          onClick={e => handleDeleteConversation(conv.id, e)}
          className="opacity-0 group-hover:opacity-100 text-[var(--text-dim)] hover:text-rose-400 p-1 rounded-md transition-opacity cursor-pointer"
          title="Delete chat"
        >
          <Trash2 size={13} />
        </button>
      </div>
    )
  }

  // Authoritative clean message renderer
  function renderMessage(msg: ChatMessage) {
    const isUser = msg.sender === 'user'

    if (isUser) {
      return (
        <div key={msg.id} className="flex justify-end items-start gap-2.5">
          <div className="bg-[var(--accent)] text-white rounded-2xl rounded-tr-xs px-4 py-3 max-w-lg shadow-md text-xs md:text-sm leading-relaxed">
            {msg.text}
          </div>
          <div className="w-8 h-8 rounded-xl bg-[#1e293b] border border-[var(--border)] text-[var(--text-muted)] flex items-center justify-center shrink-0 text-xs">
            <User size={15} />
          </div>
        </div>
      )
    }

    const tool = msg.tool_results || {}
    const hasExcelPreview = tool.card_type === 'excel_preview' || tool.card_type === 'comparison_matrix' || tool.card_type === 'table_view'
    const files = msg.files || []

    return (
      <div key={msg.id} className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white flex items-center justify-center shrink-0 text-xs shadow-md">
          <Bot size={16} />
        </div>

        <div className="flex-1 space-y-3 max-w-2xl">
          {/* ChatGPT-style clean header with subtle badge */}
          <div className="flex items-center gap-2 text-[11px] text-[var(--text-dim)] font-medium">
            <span className="font-semibold text-[var(--text-muted)]">MYGPT AI</span>
            <span>•</span>
            <span className="flex items-center gap-1 text-emerald-400 font-semibold">
              <CheckCircle2 size={12} /> Verified Result
            </span>
            <span>•</span>
            <span>{msg.timestamp}</span>
          </div>

          {/* Assistant Text Answer */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl rounded-tl-xs p-4 md:p-5 shadow-md text-xs md:text-sm text-[var(--text)] leading-relaxed whitespace-pre-line">
            {msg.text}
          </div>

          {/* Structured UI Component Renderers */}
          {tool.card_type === 'metric_card' && (
            <div className="bg-[#151c2c] border border-[var(--border)] rounded-xl p-4 shadow-md">
              <div className="text-[10px] uppercase font-bold text-[var(--text-dim)] tracking-wider mb-1">
                {tool.title || 'Calculated Metric'}
              </div>
              <div className="text-2xl font-bold text-indigo-400 mb-1">
                {tool.primary_value}
              </div>
              {tool.secondary_value && (
                <div className="text-xs text-[var(--text-muted)] mb-3">{tool.secondary_value}</div>
              )}

              {tool.details && (
                <div className="mt-3 pt-3 border-t border-[var(--border)] grid grid-cols-2 gap-2 text-xs bg-[#101624] p-3 rounded-lg">
                  {tool.details.transaction_id && (
                    <div><span className="text-[var(--text-dim)]">Transaction ID:</span> <span className="font-semibold text-[var(--text)]">{tool.details.transaction_id}</span></div>
                  )}
                  {tool.details.date && (
                    <div><span className="text-[var(--text-dim)]">Date:</span> <span className="font-semibold text-[var(--text)]">{tool.details.date}</span></div>
                  )}
                  {tool.details.status && (
                    <div><span className="text-[var(--text-dim)]">Status:</span> <span className="font-semibold text-[var(--text)]">{tool.details.status}</span></div>
                  )}
                  {tool.details.mode && (
                    <div><span className="text-[var(--text-dim)]">Mode:</span> <span className="font-semibold text-[var(--text)]">{tool.details.mode}</span></div>
                  )}
                </div>
              )}
            </div>
          )}

          {tool.card_type === 'table_view' && (
            <div className="bg-[#151c2c] border border-[var(--border)] rounded-xl p-4 shadow-md overflow-hidden">
              <div className="text-sm font-semibold text-[var(--text)] mb-2.5">{tool.title}</div>
              <div className="overflow-x-auto border border-[var(--border)] rounded-lg">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#101624] text-[var(--text-muted)] font-semibold border-b border-[var(--border)]">
                    <tr>
                      {(tool.headers || ['Group', 'Value', 'Records', 'Volume']).map((h: string, idx: number) => (
                        <th key={idx} className="p-2.5">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {(tool.rows || []).map((row: any, rIdx: number) => (
                      <tr key={rIdx} className="hover:bg-[#1a2336]/60">
                        <td className="p-2.5 font-semibold text-[var(--text)]">{row.Group || row[tool.headers?.[0]]}</td>
                        <td className="p-2.5 text-indigo-400 font-bold">{row['Highest Value'] || row['Lowest Value'] || row[tool.headers?.[1]]}</td>
                        <td className="p-2.5 text-[var(--text-muted)]">{row.Count || row.Records || row[tool.headers?.[2]]}</td>
                        <td className="p-2.5 text-[var(--text-muted)] font-medium">{row['Total Volume'] || row[tool.headers?.[3]]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tool.card_type === 'column_list' && (
            <div className="bg-[#151c2c] border border-[var(--border)] rounded-xl p-4 shadow-md">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-[var(--text)]">Workbook Columns ({tool.column_count})</span>
                <span className="text-[11px] text-[var(--text-dim)]">{tool.total_records?.toLocaleString()} Records</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {(tool.columns || []).map((col: string, idx: number) => (
                  <div key={idx} className="bg-[#101624] border border-[var(--border)] rounded-lg p-2 text-xs font-mono text-[var(--text)] truncate">
                    {idx + 1}. {col}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Resume Comparison Card */}
          {tool.card_type === 'resume_comparison' && tool.candidate_a && tool.candidate_b && (
            <div className="bg-[#151c2c] border border-[var(--border)] rounded-xl p-4 md:p-5 shadow-md space-y-4">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
                <div className="flex items-center gap-2">
                  <UserCheck className="text-indigo-400" size={18} />
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text)]">Resume Comparison</span>
                </div>
                <span className="text-[11px] font-semibold bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 px-2.5 py-0.5 rounded-full">
                  Target Role: {tool.target_role || 'HR Position'}
                </span>
              </div>

              {/* Side-by-Side Candidate Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Candidate A */}
                <div className={`p-3.5 rounded-xl border ${tool.best_candidate === tool.candidate_a.candidate_name ? 'bg-indigo-950/30 border-indigo-500/50' : 'bg-[#101624] border-[var(--border)]'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-sm text-[var(--text)]">{tool.candidate_a.candidate_name}</span>
                    {tool.candidate_a.alignment_score && (
                      <span className="text-xs font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-md border border-indigo-500/20">
                        {tool.candidate_a.alignment_score}% Match
                      </span>
                    )}
                  </div>
                  <div className="text-xs space-y-1.5 text-[var(--text-muted)]">
                    <div><span className="text-[var(--text-dim)]">Experience:</span> <span className="font-medium text-[var(--text)]">{tool.candidate_a.total_experience || 'N/A'}</span></div>
                    {tool.candidate_a.skills && tool.candidate_a.skills.length > 0 && (
                      <div className="pt-1">
                        <span className="text-[var(--text-dim)] block text-[11px] mb-1">Key Skills:</span>
                        <div className="flex flex-wrap gap-1">
                          {tool.candidate_a.skills.slice(0, 4).map((s: string, idx: number) => (
                            <span key={idx} className="bg-[#1a2336] text-[10px] text-[var(--text)] px-1.5 py-0.5 rounded border border-[var(--border)]">{s}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Candidate B */}
                <div className={`p-3.5 rounded-xl border ${tool.best_candidate === tool.candidate_b.candidate_name ? 'bg-indigo-950/30 border-indigo-500/50' : 'bg-[#101624] border-[var(--border)]'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-sm text-[var(--text)]">{tool.candidate_b.candidate_name}</span>
                    {tool.candidate_b.alignment_score && (
                      <span className="text-xs font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-md border border-indigo-500/20">
                        {tool.candidate_b.alignment_score}% Match
                      </span>
                    )}
                  </div>
                  <div className="text-xs space-y-1.5 text-[var(--text-muted)]">
                    <div><span className="text-[var(--text-dim)]">Experience:</span> <span className="font-medium text-[var(--text)]">{tool.candidate_b.total_experience || 'N/A'}</span></div>
                    {tool.candidate_b.skills && tool.candidate_b.skills.length > 0 && (
                      <div className="pt-1">
                        <span className="text-[var(--text-dim)] block text-[11px] mb-1">Key Skills:</span>
                        <div className="flex flex-wrap gap-1">
                          {tool.candidate_b.skills.slice(0, 4).map((s: string, idx: number) => (
                            <span key={idx} className="bg-[#1a2336] text-[10px] text-[var(--text)] px-1.5 py-0.5 rounded border border-[var(--border)]">{s}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Competency Reconciliation Matrix */}
              {tool.matrix && tool.matrix.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-[var(--border)]">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-dim)]">Competency Breakdown</div>
                  <div className="divide-y divide-[var(--border)] border border-[var(--border)] rounded-lg overflow-hidden bg-[#101624]">
                    {tool.matrix.map((m: any, mIdx: number) => (
                      <div key={mIdx} className="p-3 text-xs space-y-1 hover:bg-[#162032]">
                        <div className="font-semibold text-indigo-300">{m.criteria}</div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[var(--text-muted)] pt-1">
                          <div><span className="font-medium text-[var(--text)]">{tool.candidate_a.candidate_name}:</span> {m.candidate_a_evidence}</div>
                          <div><span className="font-medium text-[var(--text)]">{tool.candidate_b.candidate_name}:</span> {m.candidate_b_evidence}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Generated Excel Preview Card */}
          {tool.card_type === 'excel_preview' && (
            <div className="bg-[#151c2c] border border-[var(--border)] rounded-xl p-4 shadow-md space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <FileSpreadsheet size={20} className="text-emerald-400" />
                  <div>
                    <div className="text-xs font-bold text-[var(--text)]">{tool.filename}</div>
                    <div className="text-[11px] text-[var(--text-dim)]">
                      Excel • {tool.total_rows ? `${tool.total_rows.toLocaleString()} rows` : 'Calculated Results'} • {tool.total_columns || 2} cols
                    </div>
                  </div>
                </div>
              </div>

              {tool.preview_rows && tool.preview_rows.length > 0 && (
                <div className="border border-[var(--border)] rounded-lg overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-[#101624] border-b border-[var(--border)] font-semibold text-[var(--text-muted)]">
                      <tr>
                        {(tool.columns || []).map((col: string, idx: number) => (
                          <th key={idx} className="p-2.5 whitespace-nowrap">{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {tool.preview_rows.slice(0, 5).map((row: any, rIdx: number) => (
                        <tr key={rIdx} className="hover:bg-[#1a2336]/60">
                          {(tool.columns || []).map((col: string, cIdx: number) => (
                            <td key={cIdx} className="p-2.5 whitespace-nowrap text-[var(--text)] font-medium">
                              {String(row[col] ?? '')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Action Buttons: Preview as Primary, Download as Secondary */}
              <div className="flex items-center gap-2.5 pt-1">
                {tool.file_id && (
                  <button
                    onClick={() => setViewerModal({ isOpen: true, fileId: tool.file_id, filename: tool.filename })}
                    className="flex-1 flex items-center justify-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2 px-3.5 rounded-lg text-xs transition-colors shadow-sm cursor-pointer"
                  >
                    <Table size={14} />
                    <span>Open Full Preview</span>
                  </button>
                )}

                {tool.file_id && (
                  <button
                    onClick={() => api.downloadCompanyFile(tool.file_id, tool.filename, userRole, `user_${userRole.toLowerCase()}`)}
                    className="flex items-center justify-center gap-1.5 bg-[#1a2336] hover:bg-[#232f48] text-[var(--text)] border border-[var(--border)] font-semibold py-2 px-3.5 rounded-lg text-xs transition-colors cursor-pointer"
                  >
                    <Download size={14} />
                    <span>Download Excel</span>
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Download File Chips if generated and not already shown */}
          {!hasExcelPreview && files.length > 0 && (
            <div className="space-y-2">
              {files.map((file, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-[#151c2c] border border-[var(--border)] rounded-xl text-xs shadow-md">
                  <div className="flex items-center gap-2.5">
                    <FileSpreadsheet className="text-emerald-400" size={18} />
                    <div>
                      <div className="font-semibold text-[var(--text)]">{file.filename}</div>
                      <div className="text-[11px] text-[var(--text-dim)]">{file.type} • {file.size_kb || 24} KB</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {file.file_id && (
                      <button
                        onClick={() => setViewerModal({ isOpen: true, fileId: file.file_id || null, filename: file.filename })}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-xs cursor-pointer"
                      >
                        <Table size={13} />
                        <span>Preview</span>
                      </button>
                    )}
                    <button
                      onClick={() => api.downloadCompanyFile(file.file_id || '', file.filename, userRole, `user_${userRole.toLowerCase()}`, file.data_base64)}
                      className="bg-[#1a2336] hover:bg-[#232f48] text-[var(--text)] border border-[var(--border)] px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
                    >
                      <Download size={13} />
                      <span>Download</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }
}

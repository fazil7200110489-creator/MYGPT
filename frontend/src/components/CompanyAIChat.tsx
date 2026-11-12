import React, { useState, useEffect, useRef } from 'react'
import { Sparkles, ChevronRight, X } from 'lucide-react'
import { api } from '../services/api'
import { ConversationSidebar, type Conversation } from './chat/ConversationSidebar'
import { ChatInput } from './chat/ChatInput'
import { ChatMessageItem } from './chat/ChatMessageItem'
import { FilePill } from './chat/FilePill'
import { ExcelViewerModal } from './ExcelViewerModal'

interface AttachedDoc {
  id: string
  filename: string
  file_type?: string
  document_type?: string
  size_kb?: number
  upload_time?: string
}

interface ChatMessage {
  id: string
  sender: 'user' | 'assistant'
  text: string
  answer_type?: string
  structured_data?: any
  files?: Array<{ file_id?: string; filename: string; type: string; size_kb?: number; data_base64?: string }>
  timestamp?: string
}

export const CompanyAIChat: React.FC = () => {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string>(() => {
    return localStorage.getItem('mygpt_active_conversation') || 'mygpt_session_' + Math.random().toString(36).substring(2, 9)
  })
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [stagedFiles, setStagedFiles] = useState<File[]>([])
  const [activeDocId, setActiveDocId] = useState<string | null>(null)
  const [activeDocName, setActiveDocName] = useState<string | null>(null)

  // Modals
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [viewerModal, setViewerModal] = useState<{ isOpen: boolean; fileId: string | null; filename: string }>({
    isOpen: false,
    fileId: null,
    filename: ''
  })

  const messagesEndRef = useRef<HTMLDivElement | null>(null)

  // Persist active conversation id
  useEffect(() => {
    if (activeConversationId) {
      localStorage.setItem('mygpt_active_conversation', activeConversationId)
    }
  }, [activeConversationId])

  // Load conversations list
  const loadConversations = async () => {
    try {
      const list = await api.getConversations()
      if (Array.isArray(list)) {
        setConversations(list)
      }
    } catch (err) {
      console.error('Failed to load conversations:', err)
    }
  }

  useEffect(() => {
    loadConversations()
  }, [])

  // Load active conversation messages and documents
  useEffect(() => {
    const loadChat = async () => {
      if (!activeConversationId) return
      setIsLoading(true)
      try {
        const conv = await api.getConversation(activeConversationId)
        if (conv && Array.isArray(conv.messages)) {
          setMessages(conv.messages)
        } else {
          setMessages([])
        }

        // Restore active document
        if (conv && conv.active_document_name) {
          setActiveDocName(conv.active_document_name)
          setActiveDocId(conv.active_document_id || null)
        } else if (conv && Array.isArray(conv.documents) && conv.documents.length > 0) {
          const lastDoc = conv.documents[conv.documents.length - 1]
          setActiveDocName(lastDoc.filename || lastDoc.name)
          setActiveDocId(lastDoc.id || lastDoc.document_id)
        } else {
          setActiveDocName(null)
          setActiveDocId(null)
        }
      } catch (err) {
        console.error('Failed to load conversation messages:', err)
        setMessages([])
      } finally {
        setIsLoading(false)
      }
    }
    loadChat()
  }, [activeConversationId])

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Keyboard shortcut Ctrl+N for new chat
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault()
        handleNewChat()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Create new chat
  const handleNewChat = () => {
    const newId = 'mygpt_session_' + Math.random().toString(36).substring(2, 9)
    setActiveConversationId(newId)
    setMessages([])
    setActiveDocId(null)
    setActiveDocName(null)
    setStagedFiles([])
    setInputValue('')
  }

  // Delete chat
  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await api.deleteConversation(id)
      setConversations(prev => prev.filter(c => c.id !== id))
      if (activeConversationId === id) {
        handleNewChat()
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err)
    }
  }

  // Rename chat
  const handleRenameConversation = async (id: string, newTitle: string) => {
    try {
      await api.renameConversation(id, newTitle)
      setConversations(prev => prev.map(c => c.id === id ? { ...c, title: newTitle } : c))
    } catch (err) {
      console.error('Failed to rename conversation:', err)
    }
  }

  // File staging
  const handleAddFiles = (files: File[]) => {
    setStagedFiles(prev => [...prev, ...files])
  }

  const handleRemoveFile = (index: number) => {
    setStagedFiles(prev => prev.filter((_, i) => i !== index))
  }

  // Upload staged files
  const uploadStagedFiles = async (): Promise<AttachedDoc[]> => {
    if (stagedFiles.length === 0) return []
    setIsUploading(true)

    try {
      const res = await api.uploadMultipleCompanyDocuments(
        stagedFiles,
        activeConversationId,
        'EMPLOYEE',
        'current_user'
      )

      if (res.success && Array.isArray(res.documents) && res.documents.length > 0) {
        const newlyUploaded: AttachedDoc[] = res.documents.map((d: any) => ({
          id: d.doc_id || d.id,
          filename: d.filename,
          file_type: d.file_type || '.xlsx',
          document_type: d.document_type || 'EXCEL',
          size_kb: Math.round(d.file_size ? d.file_size / 1024 : 24),
          upload_time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }))

        const latest = newlyUploaded[newlyUploaded.length - 1]
        setActiveDocId(latest.id)
        setActiveDocName(latest.filename)
        setStagedFiles([])
        return newlyUploaded
      }
      return []
    } catch (err) {
      console.error('Upload failed:', err)
      return []
    } finally {
      setIsUploading(false)
    }
  }

  // Send message
  const handleSendMessage = async (customText?: string) => {
    const rawText = (customText ?? inputValue).trim()
    if (!rawText && stagedFiles.length === 0) return

    let userText = rawText
    if (stagedFiles.length > 0) {
      const uploaded = await uploadStagedFiles()
      if (!userText) {
        userText = `Uploaded ${uploaded.map(u => u.filename).join(', ')}`
      }
    }

    const userMsg: ChatMessage = {
      id: 'usr_' + Date.now(),
      sender: 'user',
      text: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }

    setMessages(prev => [...prev, userMsg])
    setInputValue('')
    setIsLoading(true)

    try {
      const res = await api.sendCompanyChat({
        message: userText,
        sessionId: activeConversationId,
        conversationId: activeConversationId,
        documentId: activeDocId || undefined
      })

      const assistantMsg: ChatMessage = {
        id: 'asst_' + Date.now(),
        sender: 'assistant',
        text: res.answer,
        answer_type: res.answer_type,
        structured_data: res.structured_data,
        files: res.files || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }

      setMessages(prev => [...prev, assistantMsg])
      if (res.active_document) {
        setActiveDocName(res.active_document)
      }
      loadConversations()
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

  // Active chat title
  const currentConv = conversations.find(c => c.id === activeConversationId)
  const chatTitle = currentConv?.title || 'New Chat'

  return (
    <div className="flex h-screen w-full bg-slate-50 text-slate-800 font-sans overflow-hidden">
      {/* 1. Left Sidebar */}
      <ConversationSidebar
        conversations={conversations}
        activeId={activeConversationId}
        onSelect={setActiveConversationId}
        onNewChat={handleNewChat}
        onDelete={handleDeleteConversation}
        onRename={handleRenameConversation}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(prev => !prev)}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenHelp={() => setHelpOpen(true)}
      />

      {/* 2. Main Chat Canvas */}
      <main className="flex-1 flex flex-col h-full bg-white relative overflow-hidden">
        {/* Top Minimalist Header */}
        <header className="flex items-center justify-between px-6 py-3 border-b border-slate-100 bg-white/80 backdrop-blur-md shrink-0 z-10">
          <div className="flex items-center gap-3 min-w-0">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors"
                title="Expand sidebar"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
            )}
            <h2 className="text-sm font-semibold text-slate-900 truncate">
              {chatTitle}
            </h2>
          </div>

          {/* Active File Pill (if active document attached) */}
          <div className="flex items-center gap-2">
            {activeDocName && (
              <FilePill
                filename={activeDocName}
                onClear={() => {
                  setActiveDocName(null)
                  setActiveDocId(null)
                }}
                onInspect={() => {
                  if (activeDocId) {
                    setViewerModal({ isOpen: true, fileId: activeDocId, filename: activeDocName })
                  }
                }}
              />
            )}
          </div>
        </header>

        {/* Message Feed Area */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6">
          <div className="max-w-4xl mx-auto space-y-4">
            {messages.length === 0 ? (
              /* Empty State / Welcome Screen */
              <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-md mb-4">
                  <Sparkles className="h-7 w-7" />
                </div>
                <h3 className="text-xl font-bold text-slate-900 tracking-tight mb-2">
                  What can I help you with today?
                </h3>
                <p className="text-sm text-slate-500 max-w-md mb-8">
                  MYGPT is your general-purpose local AI assistant. Analyze spreadsheets, compare test cases, write code, or ask general questions.
                </p>

                {/* Prompt Suggestions */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-lg">
                  <button
                    onClick={() => handleSendMessage('How many differences?')}
                    className="flex flex-col text-left p-3.5 rounded-xl border border-slate-200/90 bg-white hover:border-slate-300 hover:bg-slate-50 transition-all text-xs shadow-2xs group"
                  >
                    <span className="font-semibold text-slate-800 group-hover:text-slate-900">
                      Compare flight test cases
                    </span>
                    <span className="text-slate-400 text-[11px] mt-0.5">
                      "How many differences?"
                    </span>
                  </button>

                  <button
                    onClick={() => handleSendMessage('What is photosynthesis?')}
                    className="flex flex-col text-left p-3.5 rounded-xl border border-slate-200/90 bg-white hover:border-slate-300 hover:bg-slate-50 transition-all text-xs shadow-2xs group"
                  >
                    <span className="font-semibold text-slate-800 group-hover:text-slate-900">
                      Explain science & concepts
                    </span>
                    <span className="text-slate-400 text-[11px] mt-0.5">
                      "What is photosynthesis?"
                    </span>
                  </button>

                  <button
                    onClick={() => handleSendMessage('What is the capital of France?')}
                    className="flex flex-col text-left p-3.5 rounded-xl border border-slate-200/90 bg-white hover:border-slate-300 hover:bg-slate-50 transition-all text-xs shadow-2xs group"
                  >
                    <span className="font-semibold text-slate-800 group-hover:text-slate-900">
                      World knowledge
                    </span>
                    <span className="text-slate-400 text-[11px] mt-0.5">
                      "What is the capital of France?"
                    </span>
                  </button>

                  <button
                    onClick={() => handleSendMessage('Write a linked list reverse function in Python')}
                    className="flex flex-col text-left p-3.5 rounded-xl border border-slate-200/90 bg-white hover:border-slate-300 hover:bg-slate-50 transition-all text-xs shadow-2xs group"
                  >
                    <span className="font-semibold text-slate-800 group-hover:text-slate-900">
                      Write & debug code
                    </span>
                    <span className="text-slate-400 text-[11px] mt-0.5">
                      "Reverse linked list in Python"
                    </span>
                  </button>
                </div>
              </div>
            ) : (
              /* Message List */
              messages.map(msg => (
                <ChatMessageItem
                  key={msg.id}
                  message={msg}
                  onDownloadFile={(fileId, filename, dataBase64) => {
                    api.downloadCompanyFile(fileId, filename, 'EMPLOYEE', 'current_user', dataBase64)
                  }}
                  onInspectFile={(fileId, filename) => {
                    setViewerModal({ isOpen: true, fileId, filename })
                  }}
                />
              ))
            )}

            {/* Assistant Loading Skeleton */}
            {isLoading && (
              <div className="flex gap-4 py-4 px-4">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white font-bold text-xs mt-0.5 animate-pulse">
                  AI
                </div>
                <div className="flex-1 space-y-2 pt-1">
                  <div className="h-4 bg-slate-200/70 rounded-md w-1/3 animate-pulse" />
                  <div className="h-4 bg-slate-100 rounded-md w-2/3 animate-pulse" />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Floating Chat Input at Bottom */}
        <ChatInput
          value={inputValue}
          onChange={setInputValue}
          onSend={() => handleSendMessage()}
          isLoading={isLoading}
          isUploading={isUploading}
          stagedFiles={stagedFiles}
          onAddFiles={handleAddFiles}
          onRemoveFile={handleRemoveFile}
        />
      </main>

      {/* Excel Sheet Viewer Modal */}
      <ExcelViewerModal
        isOpen={viewerModal.isOpen}
        onClose={() => setViewerModal({ isOpen: false, fileId: null, filename: '' })}
        fileId={viewerModal.fileId}
        filename={viewerModal.filename}
      />

      {/* Settings Modal */}
      {settingsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <h3 className="text-base font-bold text-slate-900">Settings</h3>
              <button
                onClick={() => setSettingsOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:bg-slate-100 text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-4 text-xs text-slate-600">
              <div className="flex items-center justify-between py-2 border-b border-slate-50">
                <div>
                  <div className="font-semibold text-slate-800">Local AI Engine</div>
                  <div className="text-[11px] text-slate-400">Qwen3-4B (Q4_K_M GGUF)</div>
                </div>
                <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800">
                  Active
                </span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-slate-50">
                <div>
                  <div className="font-semibold text-slate-800">Spreadsheet Processor</div>
                  <div className="text-[11px] text-slate-400">Deterministic Excel Engine</div>
                </div>
                <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-[11px] font-semibold text-blue-800">
                  Ready
                </span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-slate-50">
                <div>
                  <div className="font-semibold text-slate-800">Privacy & Execution</div>
                  <div className="text-[11px] text-slate-400">100% Local Inference (Offline)</div>
                </div>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-800">
                  Private
                </span>
              </div>
            </div>
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setSettingsOpen(false)}
                className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-slate-800 transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Help & Shortcuts Modal */}
      {helpOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <h3 className="text-base font-bold text-slate-900">Help & Keyboard Shortcuts</h3>
              <button
                onClick={() => setHelpOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:bg-slate-100 text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-3 text-xs text-slate-600">
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-800 font-medium">New Chat</span>
                <kbd className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[11px] text-slate-600">
                  Ctrl + N
                </kbd>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-800 font-medium">Send Message</span>
                <kbd className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[11px] text-slate-600">
                  Enter
                </kbd>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-800 font-medium">New Line in Chat</span>
                <kbd className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[11px] text-slate-600">
                  Shift + Enter
                </kbd>
              </div>
              <div className="pt-2 text-[11px] text-slate-500 leading-relaxed">
                <strong className="text-slate-700">Tip:</strong> When uploading spreadsheets or documents, MYGPT treats the file as the data source and your question as the operation to execute.
              </div>
            </div>
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setHelpOpen(false)}
                className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-slate-800 transition-colors"
              >
                Got It
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

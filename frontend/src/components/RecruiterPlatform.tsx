import React, { useState, useEffect, useRef } from 'react'
import {
  Users, Upload, Search, CheckSquare, Square, Trash2,
  Sparkles, Bot, User, Send, ChevronRight, RefreshCw, FileText
} from 'lucide-react'
import { api } from '../services/api'
import { AnswerRenderer } from './AnswerRenderer'

interface Candidate {
  candidate_id: string
  candidate_name: string
  designation?: string
  total_experience?: string
  skills?: string[]
  education?: any[]
  doc_id?: string
  filename?: string
  overall_score?: number
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  intent?: string
  candidateScope?: any
  data?: any
  loading?: boolean
}

export function RecruiterPlatform() {
  // Candidate Pool State
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [loadingPool, setLoadingPool] = useState<boolean>(false)
  const [uploading, setUploading] = useState<boolean>(false)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  // Chat State
  const [messages, setMessages] = useState<Message[]>([])
  const [inputQuery, setInputQuery] = useState<string>('')
  const [chatLoading, setChatLoading] = useState<boolean>(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // Fetch Uploaded Candidates
  const fetchPool = async () => {
    setLoadingPool(true)
    try {
      const res = await api.getCandidatePool()
      setCandidates(res.candidates || [])
    } catch (err) {
      console.error('Failed to fetch uploaded resumes:', err)
    } finally {
      setLoadingPool(false)
    }
  }

  useEffect(() => {
    fetchPool()
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Batch Upload Multiple Resumes
  const handleBatchUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploading(true)
    try {
      const fileList = Array.from(files)
      await api.uploadBatchResumes(fileList)
      await fetchPool()
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `✅ Successfully uploaded and processed **${fileList.length} resume(s)** into knowledge base. You can now select specific resumes or ask queries across all uploaded resumes!`
        }
      ])
    } catch (err: any) {
      console.error(err)
      alert(err.message || 'Batch upload failed')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  // Delete Single Resume from Pool
  const handleDeleteResume = async (docId?: string, candidateId?: string) => {
    const targetId = candidateId || docId
    if (!targetId) return
    try {
      if (candidateId) {
        await api.deleteCandidateFromPool(candidateId)
      } else if (docId) {
        await api.deleteDocument(docId)
      }
      setSelectedIds(prev => prev.filter(id => id !== candidateId && id !== docId))
      await fetchPool()
    } catch (err) {
      console.error('Failed to delete single resume:', err)
    }
  }

  // Toggle Selection
  const toggleSelectCandidate = (id: string) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    )
  }

  const toggleSelectAll = () => {
    if (selectedIds.length === filteredCandidates.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(filteredCandidates.map(c => c.candidate_id))
    }
  }

  // Send Query to Multi-Resume AI
  const handleSendQuery = async (queryText?: string) => {
    const q = (queryText || inputQuery).trim()
    if (!q || chatLoading) return

    setInputQuery('')
    const userMsg: Message = { role: 'user', content: q }
    const loadingMsg: Message = { role: 'assistant', content: '', loading: true }

    setMessages(prev => [...prev, userMsg, loadingMsg])
    setChatLoading(true)

    try {
      const res = await api.queryRecruiterPlatform(
        q,
        'multi_resume_session',
        selectedIds.length > 0 ? selectedIds : undefined
      )

      let answerText = ''
      if (res.data?.formatted?.markdown_text) {
        answerText = res.data.formatted.markdown_text
      } else if (typeof res.data === 'string') {
        answerText = res.data
      } else {
        answerText = JSON.stringify(res.data, null, 2)
      }

      setMessages(prev => {
        const updated = [...prev]
        const lastIdx = updated.length - 1
        updated[lastIdx] = {
          role: 'assistant',
          content: answerText,
          intent: res.intent,
          candidateScope: res.candidate_scope,
          data: res.data
        }
        return updated
      })
    } catch (err: any) {
      console.error('Multi-Resume AI query error:', err)
      setMessages(prev => {
        const updated = [...prev]
        const lastIdx = updated.length - 1
        updated[lastIdx] = {
          role: 'assistant',
          content: `⚠️ AI Error: ${err.message || 'Failed to process request'}`
        }
        return updated
      })
    } finally {
      setChatLoading(false)
    }
  }

  // Filtered List
  const filteredCandidates = candidates.filter(c => {
    const nameMatch = (c.candidate_name || '').toLowerCase().includes(searchQuery.toLowerCase())
    const filenameMatch = (c.filename || '').toLowerCase().includes(searchQuery.toLowerCase())
    const skillMatch = (c.skills || []).some(s => s.toLowerCase().includes(searchQuery.toLowerCase()))
    return nameMatch || filenameMatch || skillMatch
  })

  return (
    <div className="flex flex-col h-full bg-slate-50 text-slate-800 overflow-hidden">
      {/* Top Bar Header */}
      <div className="px-6 py-3.5 bg-white border-b border-slate-200 flex items-center justify-between gap-4 shrink-0 shadow-2xs">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 bg-gradient-to-tr from-purple-600 to-indigo-600 rounded-xl flex items-center justify-center text-white shadow-sm">
            <Users className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-base font-black text-slate-900 tracking-tight flex items-center gap-2">
              Multi-Resume AI Assistant
              <span className="text-[10px] bg-purple-100 text-purple-700 font-bold px-2 py-0.5 rounded-full border border-purple-200 uppercase tracking-wider">
                ChatGPT for Multiple Resumes
              </span>
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Upload multiple resumes and chat naturally to compare, rank, search, summarize, or extract details.
            </p>
          </div>
        </div>

        {/* Upload Button */}
        <label className={`flex items-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-xs cursor-pointer transition-all ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
          <Upload className="h-4 w-4" />
          <span>{uploading ? 'Processing Resumes...' : 'Upload Multiple Resumes'}</span>
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.txt"
            onChange={handleBatchUpload}
            className="hidden"
          />
        </label>
      </div>

      {/* Main Split Interface */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* LEFT SIDE: Uploaded Resumes Sidebar */}
        <div className="w-full md:w-1/3 lg:w-3/12 border-r border-slate-200 bg-white flex flex-col h-full overflow-hidden shrink-0">
          {/* Search bar */}
          <div className="p-3 border-b border-slate-150 bg-slate-50/50">
            <div className="relative">
              <Search className="h-3.5 w-3.5 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search uploaded resumes..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full text-xs pl-8 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          {/* Scope indicator & Select all */}
          <div className="px-3 py-2 bg-slate-100/70 border-b border-slate-200 text-xs font-semibold flex items-center justify-between text-slate-700">
            <span className="flex items-center gap-1.5 text-[11px]">
              <Sparkles className="h-3.5 w-3.5 text-purple-600" />
              {selectedIds.length > 0 ? (
                <span className="font-bold text-purple-700">{selectedIds.length} Selected (Scope)</span>
              ) : (
                <span>All {candidates.length} Resumes (Scope)</span>
              )}
            </span>

            {filteredCandidates.length > 0 && (
              <button
                onClick={toggleSelectAll}
                className="text-[10.5px] font-bold text-purple-700 hover:text-purple-900 underline cursor-pointer"
              >
                {selectedIds.length === filteredCandidates.length ? 'Deselect All' : 'Select All'}
              </button>
            )}
          </div>

          {/* Uploaded Resumes List */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {loadingPool ? (
              <div className="p-6 text-center text-xs text-slate-400 flex flex-col items-center gap-2">
                <RefreshCw className="h-5 w-5 animate-spin text-purple-600" />
                <span>Loading uploaded resumes...</span>
              </div>
            ) : filteredCandidates.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                <FileText className="h-8 w-8 text-slate-300 mx-auto mb-2" />
                <p className="font-bold text-slate-600 text-xs">No resumes uploaded yet</p>
                <p className="mt-1 text-[11px]">Upload multiple PDF or DOCX resumes to start chatting.</p>
              </div>
            ) : (
              filteredCandidates.map(cand => {
                const isChecked = selectedIds.includes(cand.candidate_id)
                return (
                  <div
                    key={cand.candidate_id}
                    className={`group flex items-center justify-between p-2.5 rounded-xl border transition-all duration-150 text-xs ${
                      isChecked
                        ? 'bg-purple-50 text-purple-900 font-bold border-purple-200 shadow-2xs'
                        : 'bg-white text-slate-700 hover:bg-slate-50 border-slate-200/80'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 overflow-hidden flex-1">
                      <button
                        onClick={() => toggleSelectCandidate(cand.candidate_id)}
                        className="text-purple-600 hover:scale-105 transition-transform cursor-pointer shrink-0"
                      >
                        {isChecked ? (
                          <CheckSquare className="h-4 w-4 text-purple-600 fill-purple-100" />
                        ) : (
                          <Square className="h-4 w-4 text-slate-300 hover:text-slate-400" />
                        )}
                      </button>

                      <div className="flex flex-col truncate">
                        <span className="truncate font-bold text-slate-900 text-xs">
                          {cand.candidate_name}
                        </span>
                        <span className="text-[10px] text-slate-400 truncate">
                          {cand.filename || cand.designation || 'Resume Document'}
                        </span>
                      </div>
                    </div>

                    <button
                      onClick={() => handleDeleteResume(cand.doc_id, cand.candidate_id)}
                      className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-600 transition-all cursor-pointer shrink-0"
                      title="Delete resume"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* RIGHT SIDE: ChatGPT Conversational AI Interface */}
        <div className="w-full md:w-2/3 lg:w-9/12 bg-white flex flex-col h-full overflow-hidden">
          {/* Chat Messages Feed */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 bg-slate-50/40">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400">
                <div className="h-14 w-14 bg-purple-50 text-purple-600 rounded-3xl flex items-center justify-center mb-4 border border-purple-100 shadow-sm">
                  <Bot className="h-7 w-7" />
                </div>
                <h2 className="font-extrabold text-slate-800 text-base">Conversational Multi-Resume AI</h2>
                <p className="text-xs text-slate-500 mt-1 max-w-md leading-relaxed">
                  Ask natural questions across all uploaded resumes. The AI automatically compares, ranks, summarizes, searches, or extracts details.
                </p>

                {/* Natural Query Suggestion Chips */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 mt-8 w-full max-w-lg">
                  <button
                    onClick={() => handleSendQuery('Compare these resumes')}
                    className="text-xs font-semibold bg-white hover:bg-purple-50 border border-slate-200 hover:border-purple-300 p-3 rounded-xl text-left text-slate-700 transition-all flex items-center justify-between shadow-2xs cursor-pointer"
                  >
                    <span>⚖️ "Compare these resumes"</span>
                    <ChevronRight className="h-4 w-4 text-slate-400" />
                  </button>
                  <button
                    onClick={() => handleSendQuery('Rank candidates for Frontend Developer')}
                    className="text-xs font-semibold bg-white hover:bg-purple-50 border border-slate-200 hover:border-purple-300 p-3 rounded-xl text-left text-slate-700 transition-all flex items-center justify-between shadow-2xs cursor-pointer"
                  >
                    <span>🏆 "Rank for Frontend Developer"</span>
                    <ChevronRight className="h-4 w-4 text-slate-400" />
                  </button>
                  <button
                    onClick={() => handleSendQuery('Who has better React experience?')}
                    className="text-xs font-semibold bg-white hover:bg-purple-50 border border-slate-200 hover:border-purple-300 p-3 rounded-xl text-left text-slate-700 transition-all flex items-center justify-between shadow-2xs cursor-pointer"
                  >
                    <span>⚡ "Who has better React experience?"</span>
                    <ChevronRight className="h-4 w-4 text-slate-400" />
                  </button>
                  <button
                    onClick={() => handleSendQuery('Give me all phone numbers and emails')}
                    className="text-xs font-semibold bg-white hover:bg-purple-50 border border-slate-200 hover:border-purple-300 p-3 rounded-xl text-left text-slate-700 transition-all flex items-center justify-between shadow-2xs cursor-pointer"
                  >
                    <span>📞 "Give me all phone numbers & emails"</span>
                    <ChevronRight className="h-4 w-4 text-slate-400" />
                  </button>
                  <button
                    onClick={() => handleSendQuery('Who knows AWS?')}
                    className="text-xs font-semibold bg-white hover:bg-purple-50 border border-slate-200 hover:border-purple-300 p-3 rounded-xl text-left text-slate-700 transition-all flex items-center justify-between shadow-2xs cursor-pointer"
                  >
                    <span>🔍 "Who knows AWS?"</span>
                    <ChevronRight className="h-4 w-4 text-slate-400" />
                  </button>
                  <button
                    onClick={() => handleSendQuery('Summarize all uploaded resumes')}
                    className="text-xs font-semibold bg-white hover:bg-purple-50 border border-slate-200 hover:border-purple-300 p-3 rounded-xl text-left text-slate-700 transition-all flex items-center justify-between shadow-2xs cursor-pointer"
                  >
                    <span>📋 "Summarize all uploaded resumes"</span>
                    <ChevronRight className="h-4 w-4 text-slate-400" />
                  </button>
                </div>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex gap-3 max-w-4xl mx-auto ${msg.role === 'user' ? 'self-end flex-row-reverse' : 'self-start'}`}
                >
                  <div className={`p-2 rounded-full shrink-0 h-max border ${
                    msg.role === 'user'
                      ? 'bg-purple-600 border-purple-700 text-white shadow-xs'
                      : 'bg-white border-slate-200 text-purple-700 shadow-xs'
                  }`}>
                    {msg.role === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </div>

                  <div className="flex flex-col gap-1 max-w-[88%]">
                    <div className={`rounded-2xl px-4 py-3.5 text-xs leading-relaxed shadow-2xs ${
                      msg.role === 'user'
                        ? 'bg-purple-600 text-white rounded-tr-none font-medium'
                        : 'bg-white text-slate-800 border border-slate-200/90 rounded-tl-none'
                    }`}>
                      {msg.role === 'user' ? (
                        msg.content
                      ) : msg.loading ? (
                        <div className="flex items-center gap-2 text-slate-500">
                          <RefreshCw className="h-4 w-4 animate-spin text-purple-600" />
                          <span>AI is analyzing uploaded resumes...</span>
                        </div>
                      ) : (
                        <AnswerRenderer content={msg.content} question={messages[idx - 1]?.content || ''} />
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
            <div ref={chatEndRef} />
          </div>

          {/* ChatGPT Style Input Bar */}
          <div className="p-4 bg-white border-t border-slate-200 shrink-0">
            <form
              onSubmit={e => {
                e.preventDefault()
                handleSendQuery()
              }}
              className="max-w-4xl mx-auto flex items-center gap-2"
            >
              <input
                type="text"
                placeholder={
                  selectedIds.length > 0
                    ? `Ask about ${selectedIds.length} selected resume(s)... (e.g. "Compare them", "Who has more experience?")`
                    : 'Ask anything about all uploaded resumes... (e.g. "Rank for Frontend Developer", "Show contact details")'
                }
                value={inputQuery}
                onChange={e => setInputQuery(e.target.value)}
                disabled={chatLoading}
                className="flex-1 text-xs px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-purple-500 focus:bg-white text-slate-800 placeholder-slate-400 transition-all shadow-2xs"
              />
              <button
                type="submit"
                disabled={!inputQuery.trim() || chatLoading}
                className="bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white font-bold px-4 py-3 rounded-xl shadow-xs transition-all cursor-pointer flex items-center gap-1.5"
              >
                <span>Send</span>
                <Send className="h-3.5 w-3.5" />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}

import React from 'react'
import {
  FileText, Upload, Search, Trash2, ChevronRight, Sparkles, Code
} from 'lucide-react'

export interface LeftSidebarProps {
  documents: any[]
  activeDocId: string | null
  uploading: boolean
  sidebarSearch: string
  devMode: boolean
  onSearchChange: (val: string) => void
  onSelectDocument: (id: string) => void
  onDeleteDocument: (id: string, e: React.MouseEvent) => void
  onFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void
  onToggleDevMode: () => void
}

export function LeftSidebar({
  documents,
  activeDocId,
  uploading,
  sidebarSearch,
  devMode,
  onSearchChange,
  onSelectDocument,
  onDeleteDocument,
  onFileUpload,
  onToggleDevMode
}: LeftSidebarProps) {
  const filteredDocs = documents.filter(doc =>
    doc.filename.toLowerCase().includes(sidebarSearch.toLowerCase())
  )

  return (
    <div className="w-80 border-r border-slate-200/80 bg-white flex flex-col h-full shrink-0 shadow-2xs">
      {/* Header Banner */}
      <div className="p-4 border-b border-slate-150 flex items-center justify-between bg-slate-50/60">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 text-white flex items-center justify-center font-black text-sm shadow-md">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-extrabold text-slate-900 text-sm tracking-tight leading-none">
              MyGPT Studio
            </h1>
            <span className="text-[10px] font-bold text-indigo-600 uppercase tracking-wider">
              Resume Intelligence Platform
            </span>
          </div>
        </div>
      </div>

      {/* Upload Button */}
      <div className="p-4 border-b border-slate-150">
        <label className={`flex items-center justify-center gap-2 w-full p-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold text-xs rounded-xl shadow-sm cursor-pointer transition-all duration-200 ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
          <Upload className="h-4 w-4" />
          <span>{uploading ? 'Processing Resume...' : 'Upload New Resume'}</span>
          <input type="file" onChange={onFileUpload} accept=".pdf,.docx,.doc,.txt" multiple className="hidden" />
        </label>
      </div>

      {/* Search Bar */}
      <div className="px-4 py-3 border-b border-slate-150">
        <div className="relative">
          <Search className="h-3.5 w-3.5 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search candidate documents..."
            value={sidebarSearch}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full text-xs pl-8 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:border-indigo-500 focus:bg-white transition-all"
          />
        </div>
      </div>

      {/* Document List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2 mb-2 flex items-center justify-between">
          <span>Candidate Resumes ({filteredDocs.length})</span>
        </div>

        {filteredDocs.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-400">
            No candidate documents found. Upload a PDF or DOCX resume to start.
          </div>
        ) : (
          filteredDocs.map((doc) => {
            const isActive = doc.id === activeDocId
            return (
              <div
                key={doc.id}
                onClick={() => onSelectDocument(doc.id)}
                className={`group flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all duration-200 text-xs ${
                  isActive
                    ? 'bg-indigo-50/80 text-indigo-900 font-bold border border-indigo-200/80 shadow-2xs'
                    : 'text-slate-700 hover:bg-slate-50 hover:text-slate-900 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-2.5 overflow-hidden">
                  <FileText className={`h-4 w-4 shrink-0 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
                  <span className="truncate">{doc.filename}</span>
                </div>

                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => onDeleteDocument(doc.id, e)}
                    className="p-1 hover:text-rose-600 text-slate-400 transition-colors"
                    title="Delete document"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                  <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Footer & Developer Mode Toggle */}
      <div className="p-3 border-t border-slate-150 bg-slate-50/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Code className="h-4 w-4 text-slate-500" />
          <span className="text-xs font-bold text-slate-700">Developer Mode</span>
        </div>

        <button
          onClick={onToggleDevMode}
          className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer ${
            devMode ? 'bg-indigo-600' : 'bg-slate-300'
          }`}
          title="Toggle developer mode panels"
        >
          <span
            className={`block w-4 h-4 rounded-full bg-white transition-transform absolute top-1 left-1 shadow-xs ${
              devMode ? 'translate-x-5' : 'translate-x-0'
            }`}
          />
        </button>
      </div>
    </div>
  )
}

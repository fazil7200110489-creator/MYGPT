import React, { useRef, useEffect } from 'react'
import { Send, Paperclip, X, FileSpreadsheet, FileText, FileCode, File, Loader2 } from 'lucide-react'

export interface ChatInputProps {
  value: string
  onChange: (val: string) => void
  onSend: () => void
  isLoading: boolean
  isUploading: boolean
  stagedFiles: File[]
  onAddFiles: (files: File[]) => void
  onRemoveFile: (index: number) => void
  placeholder?: string
}

export const ChatInput: React.FC<ChatInputProps> = ({
  value,
  onChange,
  onSend,
  isLoading,
  isUploading,
  stagedFiles,
  onAddFiles,
  onRemoveFile,
  placeholder = "Message MYGPT... (e.g. 'How many differences?', 'What is photosynthesis?')"
}) => {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      const scrollHeight = textareaRef.current.scrollHeight
      textareaRef.current.style.height = `${Math.min(scrollHeight, 200)}px`
    }
  }, [value])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if ((value.trim() || stagedFiles.length > 0) && !isLoading && !isUploading) {
        onSend()
      }
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onAddFiles(Array.from(e.target.files))
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const canSubmit = (value.trim().length > 0 || stagedFiles.length > 0) && !isLoading && !isUploading

  return (
    <div className="w-full max-w-4xl mx-auto px-4 pb-4">
      {/* Container */}
      <div className="relative rounded-2xl border border-slate-200/90 bg-white/95 backdrop-blur-xl shadow-lg transition-all focus-within:border-slate-400 focus-within:shadow-xl">
        {/* Staged Files Preview */}
        {stagedFiles.length > 0 && (
          <div className="flex flex-wrap gap-2 p-3 pb-1 border-b border-slate-100">
            {stagedFiles.map((file, idx) => {
              const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls') || file.name.endsWith('.csv')
              const isCode = ['.py', '.js', '.ts', '.html', '.css', '.json'].some(ext => file.name.endsWith(ext))
              const isDoc = ['.pdf', '.docx', '.doc', '.txt'].some(ext => file.name.endsWith(ext))

              return (
                <div
                  key={idx}
                  className="flex items-center gap-2 rounded-xl bg-slate-50 border border-slate-200/80 px-2.5 py-1 text-xs text-slate-700 shadow-2xs"
                >
                  <div className={`p-1 rounded-md ${
                    isExcel ? 'bg-emerald-100 text-emerald-700' :
                    isCode ? 'bg-indigo-100 text-indigo-700' :
                    isDoc ? 'bg-blue-100 text-blue-700' : 'bg-slate-200 text-slate-700'
                  }`}>
                    {isExcel ? <FileSpreadsheet className="h-3.5 w-3.5" /> :
                     isCode ? <FileCode className="h-3.5 w-3.5" /> :
                     isDoc ? <FileText className="h-3.5 w-3.5" /> : <File className="h-3.5 w-3.5" />}
                  </div>
                  <div className="flex flex-col">
                    <span className="font-semibold text-slate-800 truncate max-w-[180px]">{file.name}</span>
                    <span className="text-[10px] text-slate-400">{(file.size / 1024).toFixed(1)} KB</span>
                  </div>
                  <button
                    onClick={() => onRemoveFile(idx)}
                    className="ml-1 p-0.5 rounded-full hover:bg-slate-200 text-slate-400 hover:text-slate-600 transition-colors"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {/* Text Input Row */}
        <div className="flex items-end gap-2 p-3">
          {/* File Attachment Button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading || isUploading}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors disabled:opacity-50"
            title="Attach Excel spreadsheet or document"
          >
            <Paperclip className="h-4.5 w-4.5" />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".xlsx,.xls,.csv,.pdf,.docx,.doc,.txt,.py,.js,.ts,.html,.css"
            onChange={handleFileChange}
            className="hidden"
          />

          {/* Expanding Textarea */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            disabled={isLoading}
            className="flex-1 resize-none bg-transparent py-1.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-hidden max-h-[200px] leading-relaxed"
          />

          {/* Send Button */}
          <button
            type="button"
            onClick={onSend}
            disabled={!canSubmit}
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-all ${
              canSubmit
                ? 'bg-slate-900 text-white shadow-md hover:bg-slate-800 active:scale-95'
                : 'bg-slate-100 text-slate-300 cursor-not-allowed'
            }`}
            title="Send message"
          >
            {isLoading || isUploading ? (
              <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>

      {/* Local AI Privacy Footer */}
      <div className="mt-2 text-center text-[11px] text-slate-400">
        MYGPT runs locally on your machine. All documents and conversations remain confidential.
      </div>
    </div>
  )
}

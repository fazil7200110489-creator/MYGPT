import React, { useState } from 'react'
import { Copy, Check, Download, FileSpreadsheet, Eye } from 'lucide-react'
import { ComparisonCard } from './ComparisonCard'
import { TenderExtractionCard } from './TenderExtractionCard'
import { AnswerRenderer } from '../AnswerRenderer'

export interface ChatMessageItemProps {
  message: {
    id: string
    sender: 'user' | 'assistant'
    text: string
    answer_type?: string
    structured_data?: any
    files?: Array<{ file_id?: string; filename: string; type: string; size_kb?: number; data_base64?: string }>
    timestamp?: string
  }
  onDownloadFile?: (fileId: string, filename: string, dataBase64?: string) => void
  onInspectFile?: (fileId: string, filename: string) => void
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  onDownloadFile,
  onInspectFile
}) => {
  const [copied, setCopied] = useState(false)
  const isUser = message.sender === 'user'

  const handleCopy = () => {
    navigator.clipboard.writeText(message.text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const isTenderExtraction =
    message.answer_type === 'tender_extraction' &&
    Boolean(message.structured_data?.tender_extraction)

  const isComparison = !isTenderExtraction && (
    message.answer_type === 'comparison' ||
    Boolean(message.structured_data?.total_differences) ||
    (message.text.includes('Differences Found') && message.text.includes('Price Difference'))
  )

  if (isUser) {
    return (
      <div className="flex justify-end py-3 px-4">
        <div className="max-w-[75%] rounded-2xl bg-slate-900 px-4 py-3 text-white shadow-sm text-sm leading-relaxed">
          <p className="whitespace-pre-wrap">{message.text}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-4 py-4 px-4 hover:bg-slate-50/50 transition-colors">
      {/* Assistant Avatar */}
      <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-xl bg-linear-to-tr from-slate-900 to-slate-700 text-white shadow-2xs font-bold text-xs mt-0.5">
        AI
      </div>

      {/* Assistant Content Canvas */}
      <div className="flex-1 min-w-0 space-y-2 text-sm text-slate-800">
        {/* Tender Extraction Card, Comparison Card, or Standard Markdown */}
        {isTenderExtraction ? (
          <div>
            <TenderExtractionCard extraction={message.structured_data.tender_extraction} />
          </div>
        ) : isComparison ? (
          <div>
            <ComparisonCard data={message.structured_data} content={message.text} />
          </div>
        ) : (
          <div className="prose prose-sm prose-slate max-w-none">
            <AnswerRenderer content={message.text} question="" />
          </div>
        )}

        {/* Generated Files Row (e.g. XLSX export) */}
        {message.files && message.files.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2">
            {message.files.map((file, idx) => (
              <div
                key={idx}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 shadow-2xs"
              >
                <FileSpreadsheet className="h-4 w-4 text-emerald-600" />
                <span className="font-semibold text-slate-800 truncate max-w-[200px]">{file.filename}</span>
                <span className="text-[10px] text-slate-400">Excel</span>
                {file.file_id && onDownloadFile && (
                  <button
                    onClick={() => onDownloadFile(file.file_id!, file.filename, file.data_base64)}
                    className="ml-1 p-1 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
                    title="Download Excel file"
                  >
                    <Download className="h-3.5 w-3.5" />
                  </button>
                )}
                {file.file_id && onInspectFile && (
                  <button
                    onClick={() => onInspectFile(file.file_id!, file.filename)}
                    className="p-1 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
                    title="Preview spreadsheet"
                  >
                    <Eye className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Bottom Message Actions */}
        <div className="flex items-center gap-2 pt-1 opacity-60 hover:opacity-100 transition-opacity">
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
            title="Copy answer"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-600" />
                <span className="text-emerald-700 font-medium">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

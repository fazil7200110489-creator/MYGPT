import React, { useState } from 'react'
import { Copy, Check, Download, FileSpreadsheet, Eye, Sparkles, LayoutDashboard, ChevronDown, ChevronUp } from 'lucide-react'
import { ComparisonCard } from './ComparisonCard'
import { TenderExtractionCard } from './TenderExtractionCard'
import { TenderIntelligenceCard } from './TenderIntelligenceCard'
import { AnswerRenderer } from '../AnswerRenderer'

export interface ChatMessageItemProps {
  message: {
    id: string
    sender: 'user' | 'assistant'
    text: string
    answer_type?: string
    structured_data?: any
    suggested_questions?: string[]
    files?: Array<{ file_id?: string; filename: string; type: string; size_kb?: number; data_base64?: string }>
    timestamp?: string
  }
  onDownloadFile?: (fileId: string, filename: string, dataBase64?: string) => void
  onInspectFile?: (fileId: string, filename: string) => void
  onSelectSuggestion?: (question: string) => void
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  onDownloadFile,
  onInspectFile,
  onSelectSuggestion
}) => {
  const [copied, setCopied] = useState(false)
  const [showDetailedAnalysis, setShowDetailedAnalysis] = useState(false)
  const isUser = message.sender === 'user'

  const handleCopy = () => {
    navigator.clipboard.writeText(message.text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const hasTenderIntelligence = Boolean(message.structured_data?.tender_intelligence)

  const isTenderExtraction =
    !hasTenderIntelligence &&
    message.answer_type === 'tender_extraction' &&
    Boolean(message.structured_data?.tender_extraction)

  const isComparison = !hasTenderIntelligence && !isTenderExtraction && (
    message.answer_type === 'comparison' ||
    Boolean(message.structured_data?.total_differences) ||
    (message.text.includes('Differences Found') && message.text.includes('Price Difference'))
  )

  const suggestions: string[] =
    message.suggested_questions ||
    message.structured_data?.suggested_questions ||
    []

  const sanitizedText = React.useMemo(() => {
    if (!message.text) return ''
    const trimmed = message.text.trim()
    if (trimmed.startsWith('{') && trimmed.includes('}')) {
      try {
        const m = trimmed.match(/(\{[\s\S]*\})/)
        if (m) {
          const parsed = JSON.parse(m[1])
          if (typeof parsed === 'object' && parsed !== null) {
            const ans = parsed.answer || parsed.direct_answer || parsed.performance_security_requirement || parsed.pbg_requirement || parsed.response || parsed.summary || ''
            const ev = parsed.tender_evidence || parsed.evidence || (Array.isArray(parsed.sources) ? parsed.sources.map((s: any) => `Page ${s.page_number || s}`).join(', ') : parsed.sources) || ''
            const interp = parsed.consultant_interpretation || parsed.interpretation || parsed.implication || ''
            const act = parsed.recommended_action || parsed.action || parsed.recommendation || ''

            let ansText = ans
            if (!ansText) {
              const parts: string[] = []
              for (const [k, v] of Object.entries(parsed)) {
                if (!['sources', 'page', 'evidence', 'interpretation', 'action'].includes(k.toLowerCase())) {
                  parts.push(`- **${k.replace(/_/g, ' ')}**: ${v}`)
                }
              }
              ansText = parts.join('\n')
            }

            return `### 📌 Answer\n${ansText}\n\n### 📄 Tender Evidence\n${ev || 'Tender Document Clauses'}\n\n### 💡 Consultant Interpretation\n${interp || 'Bidders must verify compliance strictly against tender clauses to avoid pre-qualification disqualification.'}\n\n### 🎯 Recommended Action\n${act || 'Verify mandatory requirements and seek formal pre-bid clarification if needed.'}`
          }
        }
      } catch {
        // Fall back to original text
      }
    }
    return message.text
  }, [message.text])

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
      <div className="flex-1 min-w-0 space-y-3 text-sm text-slate-800">
        {/* Tender Extraction Card, Comparison Card, or Conversational Markdown */}
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
            <AnswerRenderer content={sanitizedText} question="" />
          </div>
        )}

        {/* Optional Detailed Analysis Toggle for Tender Intelligence */}
        {hasTenderIntelligence && (
          <div className="pt-2">
            <button
              onClick={() => setShowDetailedAnalysis(prev => !prev)}
              className="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50/70 hover:bg-indigo-100/80 px-3.5 py-1.5 text-xs font-semibold text-indigo-900 transition-all shadow-2xs"
            >
              <LayoutDashboard className="w-3.5 h-3.5 text-indigo-600" />
              <span>{showDetailedAnalysis ? 'Hide Detailed Analysis' : '📊 View Detailed Tender Analysis (11 Dimensions)'}</span>
              {showDetailedAnalysis ? (
                <ChevronUp className="w-3.5 h-3.5 text-indigo-600" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-indigo-600" />
              )}
            </button>

            {showDetailedAnalysis && (
              <div className="mt-3 p-2 rounded-xl border border-slate-200 bg-slate-50/50 shadow-inner">
                <TenderIntelligenceCard report={message.structured_data.tender_intelligence} />
              </div>
            )}
          </div>
        )}

        {/* Dynamic Suggested Questions */}
        {suggestions.length > 0 && (
          <div className="pt-3 border-t border-slate-100 mt-2 space-y-2">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-blue-600" />
              <span>Suggested Questions</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => onSelectSuggestion && onSelectSuggestion(q)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-800 bg-blue-50/80 hover:bg-blue-100 hover:text-blue-950 border border-blue-200/90 rounded-full px-3 py-1.5 transition-all text-left shadow-2xs hover:shadow-xs active:scale-[0.98] cursor-pointer"
                >
                  <span>{q}</span>
                </button>
              ))}
            </div>
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

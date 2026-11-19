import React, { useState, useEffect } from 'react'
import {
  X,
  FileText,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  AlertCircle,
  Copy,
  Check,
  Maximize2,
  Minimize2
} from 'lucide-react'
import { StatusBadge } from './StatusBadge'
import type { VerificationStatusType } from './types'

export interface PdfEvidenceViewerProps {
  isOpen: boolean
  onClose: () => void
  documentId?: string
  filename: string
  targetPage: number
  evidenceText?: string
  clauseHeading?: string
  category?: string
  verificationStatus?: VerificationStatusType | string
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export const PdfEvidenceViewer: React.FC<PdfEvidenceViewerProps> = ({
  isOpen,
  onClose,
  documentId,
  filename,
  targetPage,
  evidenceText,
  clauseHeading,
  category,
  verificationStatus = 'VERIFIED'
}) => {
  const [currentPage, setCurrentPage] = useState<number>(targetPage || 1)
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null)
  const [isLoadingPdf, setIsLoadingPdf] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)

  // Sync page when targetPage changes
  useEffect(() => {
    if (targetPage && targetPage > 0) {
      setCurrentPage(targetPage)
    }
  }, [targetPage])

  // Fetch PDF binary blob when modal opens
  useEffect(() => {
    let active = true
    let createdUrl: string | null = null

    if (isOpen && documentId) {
      setIsLoadingPdf(true)
      setPdfError(null)

      const url = `${BASE_URL}/api/company/files/${documentId}/download?user_role=EMPLOYEE&user_id=dev_user`

      fetch(url)
        .then(async res => {
          if (!res.ok) {
            throw new Error(`Failed to load document (${res.status} ${res.statusText})`)
          }
          const blob = await res.blob()
          if (!active) return
          const pdfBlob = new Blob([blob], { type: 'application/pdf' })
          createdUrl = window.URL.createObjectURL(pdfBlob)
          setPdfBlobUrl(createdUrl)
          setIsLoadingPdf(false)
        })
        .catch(err => {
          if (!active) return
          console.error('Failed to load PDF for evidence viewer:', err)
          setPdfError(err.message || 'Unable to load PDF preview')
          setIsLoadingPdf(false)
        })
    }

    return () => {
      active = false
      if (createdUrl) {
        window.URL.revokeObjectURL(createdUrl)
      }
    }
  }, [isOpen, documentId])

  if (!isOpen) return null

  const handleCopyEvidence = () => {
    if (evidenceText) {
      navigator.clipboard.writeText(evidenceText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const pdfUrlWithPage = pdfBlobUrl ? `${pdfBlobUrl}#page=${currentPage}&toolbar=1&navpanes=0` : ''

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/70 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4">
      <div
        className={`bg-white rounded-xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden transition-all duration-200 ${
          isFullscreen ? 'w-full h-full' : 'w-full max-w-6xl h-[92vh]'
        }`}
      >
        {/* Top Header */}
        <header className="px-4 py-3 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600/30 border border-blue-400/40 text-blue-300 shrink-0">
              <FileText className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-white truncate max-w-md">
                  {filename || 'Tender Document'}
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-blue-500/20 text-blue-300 border border-blue-400/30">
                  Page {currentPage}
                </span>
              </div>
              <div className="text-[11px] text-slate-400">
                PDF Evidence Inspector • Ground-truth source comparison
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsFullscreen(prev => !prev)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>
            {pdfBlobUrl && (
              <a
                href={pdfBlobUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs text-slate-300 hover:text-white hover:bg-slate-800 transition-colors border border-slate-700"
                title="Open PDF in new tab"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Open in Tab</span>
              </a>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-rose-900/50 transition-colors"
              title="Close Viewer (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* Main Content: Split Screen (Left: Extracted Clause & Findings, Right: Live PDF Page) */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          
          {/* Left Panel: Extracted Ground-Truth Finding & Evidence */}
          <div className="w-full md:w-96 lg:w-[420px] bg-slate-50 border-r border-slate-200 flex flex-col shrink-0 overflow-y-auto p-4 space-y-4">
            
            {/* Finding Card */}
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  {category || 'Tender Clause Evidence'}
                </span>
                <StatusBadge status={verificationStatus} size="sm" />
              </div>

              {clauseHeading && (
                <h3 className="font-bold text-slate-900 text-sm leading-snug">
                  {clauseHeading}
                </h3>
              )}

              {/* Verbatim Supporting Evidence Text */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span className="font-semibold flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
                    Supporting Tender Text
                  </span>
                  {evidenceText && (
                    <button
                      onClick={handleCopyEvidence}
                      className="inline-flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-800"
                    >
                      {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                      <span>{copied ? 'Copied' : 'Copy'}</span>
                    </button>
                  )}
                </div>

                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono text-slate-800 leading-relaxed max-h-60 overflow-y-auto whitespace-pre-wrap">
                  {evidenceText || 'No verbatim evidence snippet recorded for this citation.'}
                </div>
              </div>

              {/* Source Document Citation Tag */}
              <div className="pt-2 border-t border-slate-100 flex flex-col gap-1 text-xs text-slate-500">
                <div>
                  <strong>Document:</strong> <span className="font-mono text-slate-700">{filename}</span>
                </div>
                <div>
                  <strong>Source Page:</strong> <span className="font-mono font-bold text-blue-700">Page {currentPage}</span>
                </div>
              </div>
            </div>

            {/* Quick Page Navigator */}
            <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-700">Page Jump:</span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  className="p-1 rounded hover:bg-slate-100 text-slate-600 border border-slate-200"
                  title="Previous Page"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>
                <input
                  type="number"
                  min={1}
                  value={currentPage}
                  onChange={e => setCurrentPage(parseInt(e.target.value) || 1)}
                  className="w-14 px-1.5 py-0.5 text-center font-mono font-bold text-slate-800 border border-slate-200 rounded"
                />
                <button
                  onClick={() => setCurrentPage(p => p + 1)}
                  className="p-1 rounded hover:bg-slate-100 text-slate-600 border border-slate-200"
                  title="Next Page"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Inspector Instruction */}
            <div className="p-3 bg-blue-50/60 rounded-xl border border-blue-100 text-xs text-blue-900 space-y-1">
              <div className="font-semibold flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                Independent Verification Note
              </div>
              <p className="text-[11.5px] text-blue-800 leading-relaxed">
                Compare the extracted condition on the left against the official PDF on the right. You can scroll through pages or use the browser PDF controls.
              </p>
            </div>
          </div>

          {/* Right Panel: Official PDF Document Canvas */}
          <div className="flex-1 bg-slate-200 relative flex flex-col overflow-hidden">
            {isLoadingPdf && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 z-10 gap-2">
                <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-xs font-semibold text-slate-600">Loading original tender PDF...</span>
              </div>
            )}

            {pdfError ? (
              <div className="flex-1 flex flex-col items-center justify-center p-6 text-center bg-white">
                <AlertCircle className="w-10 h-10 text-amber-500 mb-2" />
                <h4 className="font-bold text-slate-800 text-sm">PDF Preview Unavailable</h4>
                <p className="text-xs text-slate-500 max-w-sm mt-1">{pdfError}</p>
                {documentId && (
                  <a
                    href={`${BASE_URL}/api/company/files/${documentId}/download?user_role=EMPLOYEE&user_id=dev_user`}
                    className="mt-3 px-3 py-1.5 bg-slate-900 text-white rounded-lg text-xs font-semibold hover:bg-slate-800"
                    download={filename}
                  >
                    Download Original PDF
                  </a>
                )}
              </div>
            ) : pdfBlobUrl ? (
              <iframe
                key={`${pdfBlobUrl}-${currentPage}`}
                src={pdfUrlWithPage}
                title={`Tender PDF: ${filename} (Page ${currentPage})`}
                className="w-full h-full border-none"
              />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}


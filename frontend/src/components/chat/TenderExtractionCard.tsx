import React, { useState } from 'react'
import {
  FileText,
  DollarSign,
  Calendar,
  Tag,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  EyeOff,
  FileSearch
} from 'lucide-react'

export interface TenderConflictAlternative {
  value: string
  source_file?: string | null
  source_page?: number | null
  source_sheet?: string | null
  source_text?: string | null
  reason?: string | null
}

export interface TenderFieldEvidence {
  field_name: string
  label: string
  section: string
  value: string
  source_file?: string | null
  source_page?: number | null
  source_sheet?: string | null
  source_text?: string | null
  confidence: number
  status: 'VERIFIED' | 'NEEDS_REVIEW' | 'NOT_FOUND' | 'AMBIGUOUS' | 'UNREADABLE'
  notes?: string | null
  alternatives?: TenderConflictAlternative[]
}

export interface TenderExtractionPayload {
  source_files?: string[]
  total_pages?: number
  ocr_pages_count?: number
  unreadable_pages_count?: number
  fields_found_count?: number
  fields_not_found_count?: number
  fields_ambiguous_count?: number
  basic_information?: Record<string, TenderFieldEvidence>
  financial_information?: Record<string, TenderFieldEvidence>
  important_dates?: Record<string, TenderFieldEvidence>
  additional_information?: Record<string, TenderFieldEvidence>
  missing_fields?: string[]
  conflicting_fields?: Array<{
    field_name: string
    label: string
    primary_value: string
    status: string
    source_file?: string
    source_page?: number
    alternatives?: TenderConflictAlternative[]
  }>
  unreadable_fields?: string[]
  warnings?: string[]
  detailed_summary?: string
  summary_sources?: Array<{ filename: string; page_number?: number; sheet_name?: string }>
  file_coverage?: Array<{
    filename: string
    total_pages: number
    extracted_pages: number
    ocr_pages: number[]
    unreadable_pages: number[]
    sheets: string[]
    error?: string | null
  }>
}

const STATUS_BADGE: Record<string, { label: string; cls: string; icon: React.ReactNode }> = {
  VERIFIED: {
    label: 'Verified',
    cls: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: <CheckCircle2 className="h-3 w-3" />
  },
  NEEDS_REVIEW: {
    label: 'Needs Review',
    cls: 'bg-amber-50 text-amber-700 border-amber-200',
    icon: <AlertCircle className="h-3 w-3" />
  },
  AMBIGUOUS: {
    label: 'Conflicting',
    cls: 'bg-orange-50 text-orange-700 border-orange-200',
    icon: <AlertTriangle className="h-3 w-3" />
  },
  NOT_FOUND: {
    label: 'NOT_FOUND',
    cls: 'bg-slate-100 text-slate-500 border-slate-200',
    icon: <HelpCircle className="h-3 w-3" />
  },
  UNREADABLE: {
    label: 'Unreadable',
    cls: 'bg-rose-50 text-rose-700 border-rose-200',
    icon: <EyeOff className="h-3 w-3" />
  }
}

interface TenderExtractionCardProps {
  extraction: TenderExtractionPayload
}

export const TenderExtractionCard: React.FC<TenderExtractionCardProps> = ({ extraction }) => {
  const [expandedField, setExpandedField] = useState<string | null>(null)

  const toggleEvidence = (fieldKey: string) => {
    setExpandedField(prev => (prev === fieldKey ? null : fieldKey))
  }

  const formatSource = (ev: TenderFieldEvidence) => {
    const parts: string[] = []
    if (ev.source_file) parts.push(ev.source_file)
    if (ev.source_sheet) parts.push(`Sheet: ${ev.source_sheet}`)
    if (ev.source_page) parts.push(`Page ${ev.source_page}`)
    return parts.join(' • ')
  }

  const renderSection = (
    title: string,
    icon: React.ReactNode,
    fields?: Record<string, TenderFieldEvidence>
  ) => {
    const list = fields ? Object.values(fields) : []
    if (list.length === 0) return null

    return (
      <div className="rounded-xl border border-slate-200 bg-white shadow-2xs overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-50 border-b border-slate-200">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-700">
            {icon}
            <span>{title}</span>
          </div>
          <span className="text-[11px] text-slate-500">
            {list.filter(f => f.status !== 'NOT_FOUND' && f.status !== 'UNREADABLE').length}/{list.length} found
          </span>
        </div>

        <div className="divide-y divide-slate-100">
          {list.map(field => {
            const badge = STATUS_BADGE[field.status] || STATUS_BADGE.NOT_FOUND
            const hasEvidence = Boolean(field.source_text || (field.alternatives && field.alternatives.length > 0))
            const isExpanded = expandedField === field.field_name
            const srcLabel = formatSource(field)

            return (
              <div key={field.field_name} className="px-4 py-2.5 text-xs">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                  <div className="sm:w-1/3 shrink-0 font-medium text-slate-600">
                    {field.label}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div
                      className={
                        field.value === 'NOT_FOUND'
                          ? 'font-mono text-slate-400'
                          : 'font-semibold text-slate-900 break-words'
                      }
                    >
                      {field.value}
                    </div>
                    {srcLabel && (
                      <div className="mt-0.5 text-[11px] text-slate-500">
                        Source: {srcLabel}
                      </div>
                    )}
                    {field.notes && (
                      <div className="mt-0.5 text-[11px] text-amber-700">
                        {field.notes}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {field.status !== 'NOT_FOUND' && (
                      <span className="text-[11px] text-slate-400 tabular-nums">
                        {Math.round((field.confidence || 0) * 100)}%
                      </span>
                    )}
                    <span
                      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${badge.cls}`}
                    >
                      {badge.icon}
                      {badge.label}
                    </span>
                    {hasEvidence && (
                      <button
                        type="button"
                        onClick={() => toggleEvidence(field.field_name)}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100"
                        title="View source evidence"
                      >
                        <FileSearch className="h-3 w-3" />
                        {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                      </button>
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <div className="mt-2 rounded-lg bg-slate-50 border border-slate-200 p-2.5 text-[11px] text-slate-700 space-y-1.5">
                    {field.source_text && (
                      <div>
                        <span className="font-semibold text-slate-600">Supporting Source Text: </span>
                        <span className="italic">"{field.source_text}"</span>
                      </div>
                    )}
                    {field.alternatives && field.alternatives.length > 0 && (
                      <div>
                        <div className="font-semibold text-orange-700 mb-1">Conflicting / Alternative Values:</div>
                        <ul className="list-disc pl-4 space-y-0.5">
                          {field.alternatives.map((alt, i) => (
                            <li key={i}>
                              <span className="font-semibold">{alt.value}</span>
                              {alt.source_file ? ` (${alt.source_file}${alt.source_page ? `, Page ${alt.source_page}` : ''})` : ''}
                              {alt.source_text ? ` — "${alt.source_text.slice(0, 140)}"` : ''}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  const allFlat = [
    ...(extraction.basic_information ? Object.values(extraction.basic_information) : []),
    ...(extraction.financial_information ? Object.values(extraction.financial_information) : []),
    ...(extraction.important_dates ? Object.values(extraction.important_dates) : []),
    ...(extraction.additional_information ? Object.values(extraction.additional_information) : [])
  ]
  const missingItems = allFlat.filter(f => f.status === 'NOT_FOUND' || f.status === 'UNREADABLE')

  return (
    <div className="space-y-3 my-1">
      {/* Header Summary Strip */}
      <div className="rounded-xl border border-indigo-200 bg-indigo-50/70 px-4 py-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-bold text-slate-900">
            Extracted Tender Information (25-Field Schema)
          </div>
          <div className="text-xs text-slate-600 mt-0.5">
            Files: {(extraction.source_files || []).join(', ') || 'Uploaded tender'} •{' '}
            {extraction.total_pages || 0} page(s) analyzed
            {extraction.ocr_pages_count ? ` • ${extraction.ocr_pages_count} OCR page(s)` : ''}
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="rounded-full bg-emerald-100 text-emerald-800 px-2.5 py-0.5 font-semibold">
            {extraction.fields_found_count ?? 0}/25 Extracted
          </span>
          {(extraction.fields_ambiguous_count ?? 0) > 0 && (
            <span className="rounded-full bg-orange-100 text-orange-800 px-2.5 py-0.5 font-semibold">
              {extraction.fields_ambiguous_count} Conflicting
            </span>
          )}
        </div>
      </div>

      {/* Sections 1 - 4 */}
      {renderSection(
        '1. Basic Tender Information',
        <FileText className="h-3.5 w-3.5 text-indigo-600" />,
        extraction.basic_information
      )}
      {renderSection(
        '2. Financial Information',
        <DollarSign className="h-3.5 w-3.5 text-emerald-600" />,
        extraction.financial_information
      )}
      {renderSection(
        '3. Important Dates',
        <Calendar className="h-3.5 w-3.5 text-blue-600" />,
        extraction.important_dates
      )}
      {renderSection(
        '4. Additional Information',
        <Tag className="h-3.5 w-3.5 text-purple-600" />,
        extraction.additional_information
      )}

      {/* Section 5: Missing or Conflicting Information */}
      <div className="rounded-xl border border-amber-200 bg-amber-50/50 overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 bg-amber-100/60 border-b border-amber-200 text-xs font-semibold uppercase tracking-wide text-amber-900">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-700" />
          <span>5. Missing or Conflicting Information</span>
        </div>
        <div className="p-4 text-xs space-y-2 text-slate-700">
          <div>
            <span className="font-semibold">Not Found ({missingItems.length}): </span>
            {missingItems.length > 0
              ? missingItems.map(f => `${f.label} (${f.status})`).join(', ')
              : 'None'}
          </div>
          {extraction.conflicting_fields && extraction.conflicting_fields.length > 0 && (
            <div>
              <div className="font-semibold text-orange-800 mb-1">Conflicting / Corrigendum Revisions:</div>
              <ul className="list-disc pl-4 space-y-1">
                {extraction.conflicting_fields.map((cf, i) => (
                  <li key={i}>
                    <span className="font-semibold">{cf.label}:</span> Primary{' '}
                    <code className="bg-white px-1 rounded border">{cf.primary_value}</code>{' '}
                    vs{' '}
                    {(cf.alternatives || [])
                      .map(a => `${a.value} (${a.source_file || ''}${a.source_page ? ` p.${a.source_page}` : ''})`)
                      .join('; ')}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {extraction.warnings && extraction.warnings.length > 0 && (
            <div>
              <div className="font-semibold text-amber-800 mb-1">Warnings:</div>
              <ul className="list-disc pl-4 space-y-0.5">
                {extraction.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Detailed Tender Summary */}
      {extraction.detailed_summary && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-700 mb-1.5">
            Detailed Tender Summary
          </div>
          <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-line">
            {extraction.detailed_summary}
          </p>
          {extraction.summary_sources && extraction.summary_sources.length > 0 && (
            <div className="mt-2 text-[11px] text-slate-500">
              Summary Citations:{' '}
              {extraction.summary_sources
                .map(s => `${s.filename}${s.sheet_name ? ` (Sheet: ${s.sheet_name})` : ''}${s.page_number ? ` p.${s.page_number}` : ''}`)
                .join(' • ')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}


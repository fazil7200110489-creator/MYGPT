import React, { useState } from 'react'
import {
  FileText,
  Clock,
  Printer,
  ChevronDown,
  Search,
  Filter,
  Download,
  ShieldAlert,
  Sparkles,
  Maximize2,
  Minimize2,
  RefreshCw,
  AlertTriangle,
  Award,
  Layers,
  Cpu,
  Briefcase,
  DollarSign,
  Scale,
  AlertCircle,
  Globe
} from 'lucide-react'
import type {
  MasterTenderReport,
  VerificationStatusType
} from './types'
import { StatusBadge } from './StatusBadge'
import { PdfEvidenceViewer } from './PdfEvidenceViewer'
import {
  exportDossierPrint,
  exportDossierHtml,
  exportDossierMarkdown,
  exportTechnicalSpecificationsCsv,
  exportComplianceMatrixCsv,
  exportRiskRegisterCsv
} from './TenderExportUtils'

export interface TenderConsultantDashboardProps {
  report: MasterTenderReport
  onNewAnalysis?: () => void
}

// 11 Canonical Dimensions
export const CANONICAL_DIMENSIONS = [
  { id: 1, name: '1. Executive Consultant Briefing', shortName: 'Executive Briefing', icon: Sparkles },
  { id: 2, name: '2. Tender Overview & Key Facts', shortName: 'Tender Overview', icon: FileText },
  { id: 3, name: '3. Bidder Eligibility & PQ', shortName: 'Eligibility & PQ', icon: Award },
  { id: 4, name: '4. Technical Scope Analysis', shortName: 'Technical Scope', icon: Layers },
  { id: 5, name: '5. Technical Specifications', shortName: 'Technical Specs', icon: Cpu },
  { id: 6, name: '6. OEM & Product Requirements', shortName: 'OEM Requirements', icon: Briefcase },
  { id: 7, name: '7. Item-Wise Compliance Matrix', shortName: 'Compliance Matrix', icon: Scale },
  { id: 8, name: '8. Commercial & Financial Analysis', shortName: 'Commercial & Financial', icon: DollarSign },
  { id: 9, name: '9. Contractual & Legal Analysis', shortName: 'Contractual & Legal', icon: ShieldAlert },
  { id: 10, name: '10. Risk & Contradiction Analysis', shortName: 'Risk & Contradictions', icon: AlertTriangle },
  { id: 11, name: '11. Bid Strategy & Recommendations', shortName: 'Bid Strategy', icon: Sparkles }
]

export const formatTenderValue = (
  val: string | undefined | null,
  fallback: string = 'NOT FOUND IN SOURCE'
): string => {
  if (
    !val ||
    !val.trim() ||
    ['NOT FOUND', '[ NOT SPECIFIED IN TENDER ]', 'NOT_FOUND', 'NONE', 'N/A', 'NOT SPECIFIED'].includes(
      val.trim().toUpperCase()
    )
  ) {
    return fallback
  }
  return val.trim()
}

export const isDeadlinePassed = (deadlineStr?: string): boolean => {
  if (!deadlineStr || !deadlineStr.trim()) return false
  const clean = deadlineStr.trim()
  if (clean.toUpperCase().includes('PASSED') || clean.toUpperCase().includes('EXPIRED')) return true

  const dmyMatch = clean.match(/(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})/)
  if (dmyMatch) {
    const day = parseInt(dmyMatch[1], 10)
    const month = parseInt(dmyMatch[2], 10) - 1
    const year = parseInt(dmyMatch[3], 10)
    const deadlineDate = new Date(year, month, day, 23, 59, 59)
    if (!isNaN(deadlineDate.getTime())) {
      return deadlineDate.getTime() < Date.now()
    }
  }

  const ymdMatch = clean.match(/(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})/)
  if (ymdMatch) {
    const year = parseInt(ymdMatch[1], 10)
    const month = parseInt(ymdMatch[2], 10) - 1
    const day = parseInt(ymdMatch[3], 10)
    const deadlineDate = new Date(year, month, day, 23, 59, 59)
    if (!isNaN(deadlineDate.getTime())) {
      return deadlineDate.getTime() < Date.now()
    }
  }

  const parsed = Date.parse(clean)
  if (!isNaN(parsed)) {
    return parsed < Date.now()
  }

  return false
}

export const TenderConsultantDashboard: React.FC<TenderConsultantDashboardProps> = ({
  report,
  onNewAnalysis
}) => {
  // Navigation State: 'all' or dimension ID 1..11
  const [activeDimension, setActiveDimension] = useState<number | 'all'>('all')
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)

  // Search & Filter States
  const [specsSearch, setSpecsSearch] = useState('')
  const [specsSubsystem, setSpecsSubsystem] = useState<string>('all')
  const [complianceFilter, setComplianceFilter] = useState<string>('all')
  const [complianceCategoryFilter, setComplianceCategoryFilter] = useState<string>('all')
  const [complianceSearch, setComplianceSearch] = useState<string>('')
  const [showDocumentsChecklist, setShowDocumentsChecklist] = useState<boolean>(true)
  const [riskSeverityFilter, setRiskSeverityFilter] = useState<string>('all')

  // PDF Evidence Inspector Modal State
  const [evidenceViewerState, setEvidenceViewerState] = useState<{
    isOpen: boolean
    targetPage: number
    filename: string
    documentId?: string
    evidenceText?: string
    clauseHeading?: string
    category?: string
    verificationStatus?: VerificationStatusType | string
  }>({
    isOpen: false,
    targetPage: 1,
    filename: report.source_files?.[0] || 'Tender Document'
  })

  // Open PDF Evidence Inspector
  const openPdfEvidence = (
    page: number,
    evidenceText?: string,
    clauseHeading?: string,
    category?: string,
    filename?: string,
    documentId?: string,
    status?: VerificationStatusType | string
  ) => {
    setEvidenceViewerState({
      isOpen: true,
      targetPage: page || 1,
      filename: filename || report.source_files?.[0] || 'Tender Document',
      documentId: documentId || report.document_ids?.[0],
      evidenceText: evidenceText || '',
      clauseHeading: clauseHeading || '',
      category: category || 'Tender Evidence',
      verificationStatus: status || 'VERIFIED'
    })
  }

  // Shortcuts & Safe Getters
  const ov = report.overview || ({} as any)
  const el = report.eligibility || ({} as any)
  const sc = report.technical_scope || ({} as any)
  const sp = report.technical_specifications || ({} as any)
  const oem = report.oem_requirements || ({} as any)
  const cp = report.compliance_matrix || ({} as any)
  const cm = report.commercial_financial || ({} as any)
  const cl = report.contractual_legal || ({} as any)
  const rk = report.risks_and_contradictions || ({} as any)
  const bs = report.bid_strategy || ({} as any)

  // Deadline check
  const deadlinePassed = isDeadlinePassed(ov.bid_submission_deadline)

  // Verdict Parsing
  const recLower = (bs.recommendation || '').toLowerCase()
  let verdictTitle = 'Proceed with Caution'
  let verdictBorder = 'border-amber-500 bg-amber-50/70 text-amber-950'
  let verdictBadge = 'bg-amber-100 text-amber-900 border-amber-300'

  if (deadlinePassed || recLower.includes('deadline passed')) {
    verdictTitle = 'Submission Deadline Passed'
    verdictBorder = 'border-rose-600 bg-rose-50/80 text-rose-950'
    verdictBadge = 'bg-rose-100 text-rose-900 border-rose-300'
  } else if (recLower.includes('proceed') && !recLower.includes('caution') && !recLower.includes('reconsider')) {
    verdictTitle = 'Proceed'
    verdictBorder = 'border-emerald-500 bg-emerald-50/70 text-emerald-950'
    verdictBadge = 'bg-emerald-100 text-emerald-900 border-emerald-300'
  } else if (recLower.includes('high risk') || recLower.includes('reconsider') || recLower.includes('do not proceed') || recLower.includes('not recommended')) {
    verdictTitle = 'Do Not Proceed / High Risk'
    verdictBorder = 'border-rose-500 bg-rose-50/70 text-rose-950'
    verdictBadge = 'bg-rose-100 text-rose-900 border-rose-300'
  } else if (recLower.includes('clarification') || recLower.includes('manual review')) {
    verdictTitle = 'Needs Clarification'
    verdictBorder = 'border-blue-500 bg-blue-50/70 text-blue-950'
    verdictBadge = 'bg-blue-100 text-blue-900 border-blue-300'
  }

  // Real Technical Specs Count (excluding placeholder "NOT FOUND")
  const validSpecsList = (sp.items || []).filter((it: any) => it.item_name && it.item_name.toUpperCase() !== 'NOT FOUND')
  const realSpecsCount = validSpecsList.length

  // Specs Subsystems List
  const subsystemsList: string[] = Array.from(
    new Set(
      validSpecsList
        .map((it: any) => it.subsystem_or_category || it.category)
        .filter(Boolean)
    )
  )

  // Filtered Technical Specifications
  const filteredSpecs = validSpecsList.filter((it: any) => {
    const matchSearch =
      !specsSearch.trim() ||
      (it.item_name || '').toLowerCase().includes(specsSearch.toLowerCase()) ||
      (it.technical_specifications || '').toLowerCase().includes(specsSearch.toLowerCase()) ||
      (it.oem_brand_model_mentioned || '').toLowerCase().includes(specsSearch.toLowerCase())
    const matchSubsystem =
      specsSubsystem === 'all' ||
      (it.subsystem_or_category || it.category) === specsSubsystem
    return matchSearch && matchSubsystem
  })

  // Filtered Compliance Matrix
  const filteredCompliance = (cp.items || []).filter((it: any) => {
    // 1. Category Filter
    if (complianceCategoryFilter !== 'all') {
      const itCat = (it.category || 'Technical').toLowerCase()
      if (itCat !== complianceCategoryFilter.toLowerCase()) return false
    }

    // 2. Status Filter
    if (complianceFilter !== 'all') {
      const statusVal = (it.compliance_status || it.compliance_assessment || '').toLowerCase()
      if (!statusVal.includes(complianceFilter.toLowerCase())) return false
    }

    // 3. Search Filter
    if (complianceSearch.trim()) {
      const q = complianceSearch.trim().toLowerCase()
      const match =
        (it.item || '').toLowerCase().includes(q) ||
        (it.tender_requirement || '').toLowerCase().includes(q) ||
        (it.mandatory_specification || '').toLowerCase().includes(q) ||
        (it.requirement_id || '').toLowerCase().includes(q) ||
        (it.required_document_type || '').toLowerCase().includes(q) ||
        (it.remarks || '').toLowerCase().includes(q)
      if (!match) return false
    }

    return true
  })

  // Filtered Risks
  const filteredRisks = (rk.risks || []).filter((r: any) => {
    if (riskSeverityFilter === 'all') return true
    return (r.risk_level || '').toLowerCase() === riskSeverityFilter.toLowerCase()
  })

  return (
    <div
      className={`w-full bg-slate-50 text-slate-800 font-sans leading-relaxed text-sm transition-all duration-200 ${
        isFullscreen ? 'fixed inset-0 z-50 overflow-y-auto bg-white p-4 md:p-8' : 'rounded-xl border border-slate-200 bg-white shadow-xs'
      }`}
    >
      {/* ================================================================== */}
      {/* 1. ENTERPRISE HEADER                                               */}
      {/* ================================================================== */}
      <header className="px-5 py-3.5 bg-slate-900 text-white rounded-t-xl flex flex-wrap items-center justify-between gap-3 border-b border-slate-800">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white shadow-sm shrink-0">
            <Sparkles className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-white tracking-tight">
                MYGPT AI Tender Consultant
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-blue-500/20 text-blue-300 border border-blue-400/30">
                11-Dimension Dossier
              </span>
              {deadlinePassed && (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-rose-500/30 text-rose-200 border border-rose-400/50 flex items-center gap-1">
                  <Clock className="w-3 h-3 text-rose-300" />
                  Deadline Passed
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-300 pt-0.5 truncate">
              <FileText className="w-3.5 h-3.5 text-blue-400 shrink-0" />
              <span className="font-medium truncate max-w-sm" title={report.source_files?.[0] || 'Tender Document'}>
                {report.source_files?.[0] || 'Tender Document'}
              </span>
              <span>•</span>
              <span>{report.total_pages_analyzed} pages analyzed</span>
              <span>•</span>
              <span className="font-mono text-slate-400">{report.model_used}</span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 print:hidden">
          {onNewAnalysis && (
            <button
              onClick={onNewAnalysis}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white transition-colors border border-slate-700"
              title="Start a new tender analysis"
            >
              <RefreshCw className="w-3.5 h-3.5 text-blue-400" />
              <span>New Analysis</span>
            </button>
          )}

          {/* Export Dropdown Menu */}
          <div className="relative">
            <button
              onClick={() => setExportMenuOpen(prev => !prev)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-colors shadow-2xs"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export Dossier</span>
              <ChevronDown className="w-3 h-3 ml-0.5" />
            </button>

            {exportMenuOpen && (
              <div
                className="absolute right-0 mt-1 w-64 bg-white text-slate-800 rounded-lg shadow-xl border border-slate-200 py-1 z-30 text-xs"
                onMouseLeave={() => setExportMenuOpen(false)}
              >
                <button
                  onClick={() => {
                    exportDossierPrint(report)
                    setExportMenuOpen(false)
                  }}
                  className="w-full text-left px-3 py-2 hover:bg-slate-50 flex items-center gap-2"
                >
                  <Printer className="w-3.5 h-3.5 text-blue-600" />
                  <span>Print Dossier (PDF - All 11 Dimensions)</span>
                </button>
                <button
                  onClick={() => {
                    exportDossierHtml(report)
                    setExportMenuOpen(false)
                  }}
                  className="w-full text-left px-3 py-2 hover:bg-slate-50 flex items-center gap-2"
                >
                  <Globe className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Export Complete Dossier (HTML)</span>
                </button>
                <button
                  onClick={() => {
                    exportDossierMarkdown(report)
                    setExportMenuOpen(false)
                  }}
                  className="w-full text-left px-3 py-2 hover:bg-slate-50 flex items-center gap-2"
                >
                  <FileText className="w-3.5 h-3.5 text-slate-500" />
                  <span>Export Full Markdown (11 Dimensions)</span>
                </button>
                <button
                  onClick={() => {
                    exportTechnicalSpecificationsCsv(report)
                    setExportMenuOpen(false)
                  }}
                  className="w-full text-left px-3 py-2 hover:bg-slate-50 flex items-center gap-2"
                >
                  <Cpu className="w-3.5 h-3.5 text-blue-600" />
                  <span>Technical Specs (Excel / CSV)</span>
                </button>
                <button
                  onClick={() => {
                    exportComplianceMatrixCsv(report)
                    setExportMenuOpen(false)
                  }}
                  className="w-full text-left px-3 py-2 hover:bg-slate-50 flex items-center gap-2"
                >
                  <Scale className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Compliance Matrix (Excel / CSV)</span>
                </button>
                <button
                  onClick={() => {
                    exportRiskRegisterCsv(report)
                    setExportMenuOpen(false)
                  }}
                  className="w-full text-left px-3 py-2 hover:bg-slate-50 flex items-center gap-2"
                >
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                  <span>Risk Register (Excel / CSV)</span>
                </button>
              </div>
            )}
          </div>

          <button
            onClick={() => setIsFullscreen(prev => !prev)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title={isFullscreen ? 'Exit Fullscreen' : 'Expand Fullscreen'}
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </header>

      {/* ================================================================== */}
      {/* 2. TOP CONSULTANT VERDICT & KEY ANALYSIS INDICATORS                 */}
      {/* ================================================================== */}
      <div className="p-4 md:p-6 space-y-4 border-b border-slate-200 bg-slate-50/50">
        
        {/* Tender Title */}
        <div>
          <h2 className="text-lg md:text-xl font-bold text-slate-900 tracking-tight leading-snug">
            {ov.tender_title || 'Tender Evaluation & Bid Strategy Dossier'}
          </h2>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-600 mt-1">
            <span><strong>Issuing Authority:</strong> {formatTenderValue(ov.department_organization, 'NOT FOUND IN SOURCE')}</span>
            {ov.end_user_beneficiary && ov.end_user_beneficiary !== ov.department_organization && ov.end_user_beneficiary !== 'Not specified' && (
              <>
                <span>•</span>
                <span><strong>Beneficiary:</strong> {ov.end_user_beneficiary}</span>
              </>
            )}
            <span>•</span>
            <span><strong>Reference No:</strong> <code className="font-mono font-semibold text-slate-800">{formatTenderValue(ov.tender_reference_number, 'NOT FOUND IN SOURCE')}</code></span>
            <span>•</span>
            <span><strong>Location:</strong> {formatTenderValue(ov.project_location, 'NOT FOUND IN SOURCE')}</span>
          </div>
        </div>

        {/* Deadline Alert Banner if Passed */}
        {deadlinePassed && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-950 flex items-start gap-2.5 shadow-2xs">
            <Clock className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <strong className="font-bold text-rose-900">SUBMISSION DEADLINE PASSED:</strong> The official bid submission deadline ({ov.bid_submission_deadline}) has expired. Participation is only feasible if an official extension corrigendum has been published by the authority.
            </div>
          </div>
        )}

        {/* Consultant Verdict Banner */}
        <div className={`p-4 rounded-xl border-l-4 ${verdictBorder} shadow-2xs space-y-2`}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Consultant Strategic Verdict:
              </span>
              <span className={`px-2.5 py-0.5 rounded text-xs font-bold uppercase tracking-wide border ${verdictBadge}`}>
                {verdictTitle}
              </span>
            </div>
            <span className="text-[11px] font-mono text-slate-500">
              Model: {report.model_used}
            </span>
          </div>

          <p className="font-medium text-slate-900 leading-relaxed text-xs md:text-sm">
            {bs.recommendation_rationale || bs.overall_tender_assessment || 'Review all pre-qualification rules, financial commitments, and technical BOQ schedules carefully.'}
          </p>

          <div className="p-2.5 bg-white/70 rounded-lg border border-slate-200/60 text-[11px] text-slate-600 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
            <div>
              <strong>Single Source of Truth:</strong> Extracted tender parameters are strictly verified against source document pages. Strategic recommendations and risk ratings represent AI consultant reasoning and require company confirmation against audited turnover and OEM partnership credentials.
            </div>
          </div>
        </div>

        {/* Key Analysis Indicators Ribbon */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-2.5 pt-1">
          <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
            <span className="text-[10.5px] uppercase font-bold text-slate-500 block">Eligibility</span>
            <span className="text-xs font-bold text-slate-900 mt-0.5 block truncate">
              {el.conditions?.length ? `${el.conditions.length} Rules Grounded` : 'NOT FOUND IN SOURCE'}
            </span>
          </div>

          <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
            <span className="text-[10.5px] uppercase font-bold text-slate-500 block">Compliance Items</span>
            <span className="text-xs font-bold text-slate-900 mt-0.5 block">
              {cp.items?.length || 0} Clauses Extracted
            </span>
          </div>

          <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
            <span className="text-[10.5px] uppercase font-bold text-slate-500 block">BOQ Specs</span>
            <span className="text-xs font-bold text-slate-900 mt-0.5 block">
              {realSpecsCount} Items
            </span>
          </div>

          <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
            <span className="text-[10.5px] uppercase font-bold text-slate-500 block">Critical Risks</span>
            <span className="text-xs font-bold text-rose-700 mt-0.5 block">
              {rk.critical_risks_count || 0} Critical
            </span>
          </div>

          <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
            <span className="text-[10.5px] uppercase font-bold text-slate-500 block">High Risks</span>
            <span className="text-xs font-bold text-amber-700 mt-0.5 block">
              {rk.high_risks_count || 0} High
            </span>
          </div>

          <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
            <span className="text-[10.5px] uppercase font-bold text-slate-500 block">Contradictions</span>
            <span className="text-xs font-bold text-slate-800 mt-0.5 block">
              {rk.contradictions_found?.length || 0} Detected
            </span>
          </div>

          <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
            <span className="text-[10.5px] uppercase font-bold text-slate-500 block">Pre-Bid Queries</span>
            <span className="text-xs font-bold text-blue-700 mt-0.5 block">
              {bs.prebid_clarification_questions?.length || 0} Queries
            </span>
          </div>
        </div>
      </div>

      {/* ================================================================== */}
      {/* 3. MAIN WORKSPACE: 11-DIMENSION NAVIGATION + CONTENT PANELS         */}
      {/* ================================================================== */}
      <div className="flex flex-col lg:flex-row min-h-[600px]">
        
        {/* Left Navigation Sidebar */}
        <aside className="w-full lg:w-64 bg-slate-50/80 border-r border-slate-200 p-3 flex flex-col shrink-0 gap-1 print:hidden">
          <div className="flex items-center justify-between px-2 py-1.5 text-xs text-slate-500 font-bold uppercase tracking-wider">
            <span>11 Canonical Dimensions</span>
            <button
              onClick={() => setActiveDimension('all')}
              className={`text-[11px] px-2 py-0.5 rounded transition-colors ${
                activeDimension === 'all'
                  ? 'bg-blue-600 text-white font-bold'
                  : 'text-blue-700 hover:bg-slate-200'
              }`}
            >
              View All
            </button>
          </div>

          <div className="space-y-0.5">
            {CANONICAL_DIMENSIONS.map(dim => {
              const Icon = dim.icon
              const isActive = activeDimension === dim.id
              return (
                <button
                  key={dim.id}
                  onClick={() => setActiveDimension(dim.id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-2xs font-bold'
                      : 'text-slate-700 hover:bg-slate-200/70 hover:text-slate-900'
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-white' : 'text-slate-500'}`} />
                  <span className="truncate">{dim.name}</span>
                </button>
              )
            })}
          </div>
        </aside>

        {/* Content Canvas */}
        <main className="flex-1 p-4 md:p-6 space-y-8 overflow-y-auto">

          {/* -------------------------------------------------------------- */}
          {/* DIMENSION 1: EXECUTIVE CONSULTANT BRIEFING                     */}
          {/* -------------------------------------------------------------- */}
          {(activeDimension === 'all' || activeDimension === 1) && (
            <section id="dim-1" className="space-y-4">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-blue-600" />
                  Dimension 1 — Executive Consultant Briefing
                </h3>
                <span className="text-[11px] font-mono uppercase bg-blue-50 text-blue-700 px-2.5 py-0.5 rounded-full border border-blue-200 font-bold">
                  Gemma AI Reasoning & Evaluation
                </span>
              </div>

              {/* Section A: Tender at a Glance */}
              <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-blue-600" />
                    Section A — Tender at a Glance
                  </h4>
                  <span className="text-[11px] font-mono text-slate-500">Ref: {formatTenderValue(ov.tender_reference_number, 'NOT FOUND IN SOURCE')}</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="space-y-1">
                    <span className="text-slate-500 font-medium">Tender Title:</span>
                    <p className="font-semibold text-slate-900">{formatTenderValue(ov.tender_title, 'NOT FOUND IN SOURCE')}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-500 font-medium">Issuing Authority / Client:</span>
                    <p className="font-semibold text-slate-900">{formatTenderValue(ov.department_organization, 'NOT FOUND IN SOURCE')}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-500 font-medium">Scope Summary:</span>
                    <p className="text-slate-800">{formatTenderValue(ov.overall_understanding || ov.scope_of_work_summary, 'NOT FOUND IN SOURCE')}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-500 font-medium">Estimated Project Value:</span>
                    <p className="font-semibold text-emerald-800">{formatTenderValue(ov.estimated_project_value, 'NOT FOUND IN SOURCE')}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-500 font-medium">Earnest Money Deposit (EMD):</span>
                    <p className="font-semibold text-blue-900">{formatTenderValue(ov.emd_value, 'NOT FOUND IN SOURCE')} <span className="text-slate-500 font-normal">(Fee: {formatTenderValue(ov.tender_fee, 'Nil')})</span></p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-500 font-medium">Bid Submission Deadline:</span>
                    <p className="font-bold text-rose-800 flex items-center gap-2">
                      {formatTenderValue(ov.bid_submission_deadline, 'NOT FOUND IN SOURCE')}
                      {deadlinePassed && (
                        <span className="px-1.5 py-0.2 rounded text-[10px] bg-rose-100 text-rose-800 border border-rose-300 font-mono">
                          PASSED
                        </span>
                      )}
                    </p>
                  </div>
                </div>
              </div>

              {/* Section B: Most Important Requirements (Pre-Qualification & Eligibility) */}
              <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
                    <Award className="w-3.5 h-3.5 text-blue-600" />
                    Section B — Most Important Requirements (Eligibility & Qualification)
                  </h4>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex flex-col sm:flex-row sm:items-start gap-1">
                    <strong className="text-slate-700 min-w-44 shrink-0">Financial Turnover:</strong>
                    <span className="text-slate-900 font-medium">{formatTenderValue(el.annual_turnover_requirement || el.average_turnover_requirement, 'NOT FOUND IN SOURCE')}</span>
                  </div>
                  <div className="flex flex-col sm:flex-row sm:items-start gap-1">
                    <strong className="text-slate-700 min-w-44 shrink-0">Similar Work Experience:</strong>
                    <span className="text-slate-900 font-medium">{formatTenderValue(el.similar_work_experience, 'NOT FOUND IN SOURCE')}</span>
                  </div>
                  <div className="flex flex-col sm:flex-row sm:items-start gap-1">
                    <strong className="text-slate-700 min-w-44 shrink-0">OEM Authorization (MAF):</strong>
                    <span className="text-slate-900 font-medium">{el.oem_authorization_mandatory ? 'Mandatory Manufacturer Authorization Form (MAF) required' : 'Not mandated / Generic specifications'}</span>
                  </div>
                  <div className="flex flex-col sm:flex-row sm:items-start gap-1">
                    <strong className="text-slate-700 min-w-44 shrink-0">Consortium / Joint Venture:</strong>
                    <span className="text-slate-900 font-medium">{formatTenderValue(el.consortium_joint_venture_allowed, 'NOT FOUND IN SOURCE')}</span>
                  </div>
                  <div className="flex flex-col sm:flex-row sm:items-start gap-1">
                    <strong className="text-slate-700 min-w-44 shrink-0">Mandatory Certifications:</strong>
                    <span className="text-slate-900 font-medium">{el.required_certifications?.length ? el.required_certifications.join(', ') : 'NOT FOUND IN SOURCE'}</span>
                  </div>
                </div>
                <div className="p-2.5 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-900 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span><strong>Bidder eligibility:</strong> BIDDER INFORMATION REQUIRED — Company credentials have not been provided for verification.</span>
                </div>
              </div>

              {/* Section C: Important Technical Scope & Key Specifications */}
              <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
                    <Cpu className="w-3.5 h-3.5 text-blue-600" />
                    Section C — Important Technical Scope & Key Specifications
                  </h4>
                </div>
                <p className="text-xs text-slate-700 leading-relaxed">
                  {formatTenderValue(sc.overview, 'Detailed technical scope covering procurement, supply, installation, testing and commissioning.')}
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                  {subsystemsList.length > 0 ? (
                    subsystemsList.slice(0, 6).map((sub, idx) => {
                      const count = validSpecsList.filter((it: any) => (it.subsystem_or_category || it.category) === sub).length
                      return (
                        <div key={idx} className="p-2 bg-white rounded border border-slate-200 flex items-center justify-between">
                          <span className="font-semibold text-slate-800">{sub}</span>
                          <span className="text-[11px] text-blue-700 font-mono bg-blue-50 px-2 py-0.5 rounded">{count} specs</span>
                        </div>
                      )
                    })
                  ) : (
                    <div className="p-2 bg-white rounded border border-slate-200 text-slate-600">
                      {realSpecsCount} specifications categorized in technical schedule.
                    </div>
                  )}
                </div>
                <div className="p-2.5 bg-blue-50 rounded-lg border border-blue-200 text-xs text-blue-900 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-blue-600 shrink-0" />
                  <span><strong>Bidder compliance:</strong> REQUIREMENT EXTRACTED — Product proposal or OEM datasheets have not been provided for compliance evaluation.</span>
                </div>
              </div>

              {/* Section D: Financial and Contractual Obligations */}
              <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
                    <DollarSign className="w-3.5 h-3.5 text-blue-600" />
                    Section D — Financial & Contractual Obligations
                  </h4>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="space-y-1">
                    <span className="text-slate-500 font-medium">EMD & Exemption Rules:</span>
                    <p className="font-semibold text-slate-900">{formatTenderValue(ov.emd_value || cm.emd_amount, 'NOT FOUND IN SOURCE')} ({formatTenderValue(cm.emd_exemption_rules, 'Refer to tender terms')})</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-500 font-medium">Performance Bank Guarantee (PBG):</span>
                    <p className="font-semibold text-slate-900">{formatTenderValue(cm.performance_bank_guarantee_pbg, 'NOT FOUND IN SOURCE')}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-500 font-medium">Payment Terms:</span>
                    <p className="text-slate-800">{formatTenderValue(cm.payment_terms, 'NOT FOUND IN SOURCE')}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-500 font-medium">Warranty & Maintenance:</span>
                    <p className="font-semibold text-slate-900">{formatTenderValue(ov.warranty_maintenance_period || sc.maintenance_and_amc_obligations, 'NOT FOUND IN SOURCE')}</p>
                  </div>
                  <div className="space-y-1 md:col-span-2">
                    <span className="text-slate-500 font-medium">Liquidated Damages & Penalties:</span>
                    <p className="text-slate-800">{formatTenderValue(cm.penalties_and_liquidated_damages || cl.delay_penalties, 'NOT FOUND IN SOURCE')}</p>
                  </div>
                </div>
              </div>

              {/* Section E: Major Risks & Concerns */}
              <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    Section E — Major Risks & Critical Concerns
                  </h4>
                  <span className="text-[11px] font-mono text-rose-700 font-bold">{rk.critical_risks_count || 0} Critical, {rk.high_risks_count || 0} High</span>
                </div>
                <div className="space-y-2">
                  {(rk.risks || []).slice(0, 3).map((r: any, idx: number) => {
                    const isCrit = (r.risk_level || '').toLowerCase() === 'critical'
                    return (
                      <div key={idx} className="p-3 bg-white rounded-lg border border-slate-200 text-xs space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-900 flex items-center gap-1.5">
                            <span className={isCrit ? 'text-rose-600' : 'text-amber-600'}>●</span>
                            {r.risk_title}
                          </span>
                          <button
                            onClick={() => openPdfEvidence(r.source_page, r.tender_evidence, r.risk_title, 'Risk Evidence')}
                            className="text-[11px] text-blue-700 hover:underline font-mono"
                          >
                            Page {r.source_page}
                          </button>
                        </div>
                        <p className="text-slate-600 leading-relaxed">{r.why_it_matters || r.potential_impact}</p>
                        <p className="text-blue-900 font-medium text-[11.5px]"><em>Action:</em> {r.recommended_action}</p>
                      </div>
                    )
                  })}
                  {(rk.contradictions_found || []).length > 0 && (
                    <div className="p-2.5 bg-amber-50/80 rounded-lg border border-amber-200 text-xs space-y-1">
                      <strong className="text-amber-950 flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                        CONFLICT DETECTED — VERIFICATION REQUIRED:
                      </strong>
                      <ul className="list-disc pl-4 space-y-0.5 text-amber-900 text-[11.5px]">
                        {rk.contradictions_found.slice(0, 3).map((c: string, cidx: number) => (
                          <li key={cidx}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>

              {/* Section F: Consultant Recommendation */}
              <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                    Section F — Consultant Recommendation & Strategic Verdict
                  </h4>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${verdictBadge}`}>
                    {verdictTitle}
                  </span>
                </div>
                <div className="p-3 bg-white rounded-lg border border-slate-200 text-xs text-slate-800 leading-relaxed font-medium">
                  {bs.recommendation_rationale || bs.overall_tender_assessment}
                </div>
              </div>
            </section>
          )}

          {/* -------------------------------------------------------------- */}
          {/* DIMENSION 2: TENDER OVERVIEW                                   */}
          {/* -------------------------------------------------------------- */}
          {(activeDimension === 'all' || activeDimension === 2) && (
            <section id="dim-2" className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-blue-600" />
                  Dimension 2 — Tender Overview & Key Facts
                </h3>
                <StatusBadge status="VERIFIED" size="sm" />
              </div>

              {/* Comprehensive 11-Field Table with Verification Status and Page Citations */}
              <div className="border border-slate-200 rounded-lg overflow-hidden bg-white shadow-2xs">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-700 font-semibold">
                    <tr>
                      <th className="p-2.5 w-1/4">Parameter</th>
                      <th className="p-2.5">Extracted Value</th>
                      <th className="p-2.5 w-24 text-center">Source Page</th>
                      <th className="p-2.5 w-32 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    <tr className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-semibold text-slate-600">Tender Title</td>
                      <td className="p-2.5 font-bold text-slate-900">{formatTenderValue(ov.tender_title)}</td>
                      <td className="p-2.5 text-center">
                        <button
                          onClick={() => openPdfEvidence(1, ov.tender_title, 'Tender Title', 'Overview')}
                          className="font-mono text-blue-600 hover:underline"
                        >
                          Page 1
                        </button>
                      </td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status={ov.tender_title ? 'VERIFIED' : 'NOT FOUND IN SOURCE'} />
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-semibold text-slate-600">Issuing Authority</td>
                      <td className="p-2.5 font-bold text-slate-900">{formatTenderValue(ov.department_organization)}</td>
                      <td className="p-2.5 text-center">
                        <button
                          onClick={() => openPdfEvidence(1, ov.department_organization, 'Issuing Authority', 'Overview')}
                          className="font-mono text-blue-600 hover:underline"
                        >
                          Page 1
                        </button>
                      </td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status={ov.department_organization ? 'VERIFIED' : 'NOT FOUND IN SOURCE'} />
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-semibold text-slate-600">Intended Beneficiary / End-User</td>
                      <td className="p-2.5 font-bold text-slate-900">{formatTenderValue(ov.end_user_beneficiary || ov.department_organization)}</td>
                      <td className="p-2.5 text-center font-mono text-slate-400">Page 1-4</td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status="VERIFIED" />
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-semibold text-slate-600">Tender Reference Number</td>
                      <td className="p-2.5 font-mono font-semibold text-slate-800">{formatTenderValue(ov.tender_reference_number)}</td>
                      <td className="p-2.5 text-center">
                        <button
                          onClick={() => openPdfEvidence(1, ov.tender_reference_number, 'Reference Number', 'Overview')}
                          className="font-mono text-blue-600 hover:underline"
                        >
                          Page 1
                        </button>
                      </td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status={ov.tender_reference_number ? 'VERIFIED' : 'NOT FOUND IN SOURCE'} />
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-semibold text-slate-600">Tender Location</td>
                      <td className="p-2.5 text-slate-800">{formatTenderValue(ov.project_location)}</td>
                      <td className="p-2.5 text-center font-mono text-slate-400">Schedule</td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status={ov.project_location ? 'VERIFIED' : 'NOT FOUND IN SOURCE'} />
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-semibold text-slate-600">Estimated Tender Value</td>
                      <td className="p-2.5 font-bold text-slate-900">{formatTenderValue(ov.estimated_project_value)}</td>
                      <td className="p-2.5 text-center font-mono text-slate-400">NIT Notice</td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status={ov.estimated_project_value ? 'VERIFIED' : 'NOT FOUND IN SOURCE'} />
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-semibold text-slate-600">Earnest Money Deposit (EMD)</td>
                      <td className="p-2.5 font-bold text-slate-900">{formatTenderValue(ov.emd_value || cm.emd_amount)}</td>
                      <td className="p-2.5 text-center font-mono text-slate-400">Tender Notice</td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status={(ov.emd_value || cm.emd_amount) ? 'VERIFIED' : 'NOT FOUND IN SOURCE'} />
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-semibold text-slate-600">Tender Document Fee</td>
                      <td className="p-2.5 text-slate-800">{formatTenderValue(ov.tender_fee, 'Nil')}</td>
                      <td className="p-2.5 text-center font-mono text-slate-400">Tender Notice</td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status={ov.tender_fee ? 'VERIFIED' : 'NOT APPLICABLE'} />
                      </td>
                    </tr>

                    <tr className={deadlinePassed ? 'bg-rose-50/60 hover:bg-rose-50/80' : 'hover:bg-slate-50/60'}>
                      <td className="p-2.5 font-bold text-rose-800 flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-rose-600" />
                        Submission Deadline
                      </td>
                      <td className="p-2.5 font-bold text-rose-900 text-xs">
                        {formatTenderValue(ov.bid_submission_deadline)}
                        {deadlinePassed && (
                          <span className="ml-2 px-2 py-0.5 rounded text-[10px] bg-rose-200 text-rose-900 font-bold border border-rose-300">
                            DEADLINE EXPIRED
                          </span>
                        )}
                      </td>
                      <td className="p-2.5 text-center font-mono text-rose-800">Critical Cutoff</td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status={deadlinePassed ? 'SUBMISSION DEADLINE PASSED' : (ov.bid_submission_deadline ? 'VERIFIED' : 'NOT FOUND IN SOURCE')} />
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-semibold text-slate-600">Technical Bid Opening Date</td>
                      <td className="p-2.5 text-slate-800">{formatTenderValue(ov.bid_opening_date)}</td>
                      <td className="p-2.5 text-center font-mono text-slate-400">Key Dates</td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status={ov.bid_opening_date ? 'VERIFIED' : 'NOT FOUND IN SOURCE'} />
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-semibold text-slate-600">Contract Duration</td>
                      <td className="p-2.5 text-slate-800">{formatTenderValue(ov.contract_duration)}</td>
                      <td className="p-2.5 text-center font-mono text-slate-400">Scope / GCC</td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status={ov.contract_duration ? 'VERIFIED' : 'NOT FOUND IN SOURCE'} />
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-semibold text-slate-600">Warranty Period</td>
                      <td className="p-2.5 text-slate-800">{formatTenderValue(ov.warranty_maintenance_period)}</td>
                      <td className="p-2.5 text-center font-mono text-slate-400">Commercial</td>
                      <td className="p-2.5 text-center">
                        <StatusBadge status={ov.warranty_maintenance_period ? 'VERIFIED' : 'NOT FOUND IN SOURCE'} />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Project Understanding Synopsis */}
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700 space-y-1">
                <strong className="text-slate-900">Project Understanding & High-Level Scope:</strong>
                <p className="leading-relaxed">
                  {formatTenderValue(ov.overall_understanding || ov.scope_of_work_summary, 'Detailed project description specified in tender schedules.')}
                </p>
              </div>

              {/* Consultant Strategic Implications & Watchouts */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-1">
                <div className="p-3 bg-blue-50/50 rounded-lg border border-blue-200 space-y-1">
                  <strong className="text-blue-950 flex items-center gap-1.5 font-bold">
                    <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                    Bidder Implications & Working Capital:
                  </strong>
                  <p className="text-slate-700 leading-relaxed">
                    Implementation lead times must be aligned with equipment shipment cycles. Upfront capital is required for EMD, portal fees, and initial mobilization before milestone disbursements commence.
                  </p>
                </div>

                <div className="p-3 bg-amber-50/50 rounded-lg border border-amber-200 space-y-1">
                  <strong className="text-amber-950 flex items-center gap-1.5 font-bold">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    Consultant Submission Recommendation:
                  </strong>
                  <p className="text-slate-700 leading-relaxed">
                    Verify portal Digital Signature Certificate (DSC) mapping and execute all mandatory non-blacklisting affidavits on stamp paper at least 48 hours prior to deadline.
                  </p>
                </div>
              </div>
            </section>
          )}

          {/* -------------------------------------------------------------- */}
          {/* DIMENSION 3: BIDDER ELIGIBILITY & PRE-QUALIFICATION            */}
          {/* -------------------------------------------------------------- */}
          {(activeDimension === 'all' || activeDimension === 3) && (
            <section id="dim-3" className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                  <Award className="w-4 h-4 text-blue-600" />
                  Dimension 3 — Bidder Eligibility & Pre-Qualification (PQ)
                </h3>
                <span className="text-[11px] font-semibold text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                  Bidder Information Required
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <strong className="text-slate-500 uppercase text-[10px] block">Annual Turnover</strong>
                  <span className="text-sm font-bold text-slate-900 mt-0.5 block">
                    {formatTenderValue(el.annual_turnover_requirement || el.average_turnover_requirement)}
                  </span>
                </div>

                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <strong className="text-slate-500 uppercase text-[10px] block">Similar Work Experience</strong>
                  <span className="text-xs font-semibold text-slate-900 mt-0.5 block leading-normal">
                    {formatTenderValue(el.similar_work_experience)}
                  </span>
                </div>

                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <strong className="text-slate-500 uppercase text-[10px] block">OEM Authorization (MAF)</strong>
                  <span className="text-xs font-bold text-slate-900 mt-0.5 block">
                    {el.oem_authorization_mandatory ? '⚠️ Mandatory MAF Required' : 'Open / Generic Policy'}
                  </span>
                </div>
              </div>

              {/* Eligibility Conditions Table */}
              <div className="border border-slate-200 rounded-lg overflow-hidden bg-white shadow-2xs">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-700 font-semibold">
                    <tr>
                      <th className="p-2.5 w-1/4">Category</th>
                      <th className="p-2.5">Department Requirement</th>
                      <th className="p-2.5 w-1/4">Document Required</th>
                      <th className="p-2.5 w-20 text-center">Page</th>
                      <th className="p-2.5 w-28 text-center">Tender Evidence</th>
                      <th className="p-2.5 w-32 text-center">Bidder Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {el.conditions && el.conditions.length > 0 ? (
                      el.conditions.map((c: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50/60">
                          <td className="p-2.5 align-top font-bold text-slate-900">
                            {c.category}
                            {c.is_mandatory && (
                              <span className="block mt-0.5 text-[10px] font-bold text-rose-700">MANDATORY</span>
                            )}
                          </td>
                          <td className="p-2.5 align-top text-slate-800 leading-normal">
                            {c.department_requirement}
                            {c.disqualification_effect && (
                              <div className="text-[11px] text-rose-600 mt-0.5">
                                ⚠️ Disqualification: {c.disqualification_effect}
                              </div>
                            )}
                          </td>
                          <td className="p-2.5 align-top text-slate-600">{c.supporting_document_required}</td>
                          <td className="p-2.5 align-top text-center">
                            <button
                              onClick={() =>
                                openPdfEvidence(
                                  c.source_page,
                                  c.verbatim_evidence || c.department_requirement,
                                  c.category,
                                  'Eligibility',
                                  c.source_file,
                                  c.document_id,
                                  'VERIFIED'
                                )
                              }
                              className="font-mono text-blue-600 hover:underline"
                            >
                              Page {c.source_page}
                            </button>
                          </td>
                          <td className="p-2.5 align-top text-center">
                            <StatusBadge status="VERIFIED" />
                          </td>
                          <td className="p-2.5 align-top text-center">
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-300 block">
                              VERIFICATION REQUIRED
                            </span>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="p-4 text-center text-slate-500 italic">
                          No specific eligibility conditions extracted.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Consultant Eligibility Guidance */}
              <div className="p-3.5 bg-indigo-50/50 rounded-lg border border-indigo-200 text-xs space-y-2">
                <strong className="text-indigo-950 flex items-center gap-1.5 font-bold">
                  <Award className="w-3.5 h-3.5 text-indigo-600" />
                  Pre-Qualification Evaluation & Verification Protocol:
                </strong>
                <p className="text-slate-800 leading-relaxed font-medium">
                  {el.summary_assessment || 'Pre-qualification criteria are evaluated on a strict zero-deviation basis. Non-compliance in any single mandatory item causes immediate technical rejection.'}
                </p>
                <p className="text-slate-700 leading-relaxed">
                  <strong>Action Required:</strong> Ensure CA turnover certificate includes a valid UDIN. Work completion certificates must state project title, contract value, and completion dates explicitly to survive scrutiny.
                </p>
              </div>
            </section>
          )}

          {/* -------------------------------------------------------------- */}
          {/* DIMENSION 4: TECHNICAL SCOPE ANALYSIS                          */}
          {/* -------------------------------------------------------------- */}
          {(activeDimension === 'all' || activeDimension === 4) && (
            <section id="dim-4" className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-blue-600" />
                  Dimension 4 — Technical Scope Analysis & Deliverables
                </h3>
                <StatusBadge status="VERIFIED" size="sm" />
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700 leading-relaxed">
                {formatTenderValue(sc.overview || ov.scope_of_work_summary, 'Detailed scope of work specified in technical schedule.')}
              </div>

              {sc.scope_items && sc.scope_items.length > 0 && (
                <div className="border border-slate-200 rounded-lg overflow-hidden bg-white shadow-2xs">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-700 font-semibold">
                      <tr>
                        <th className="p-2.5 w-1/4">Scope Area</th>
                        <th className="p-2.5">Specific Requirement</th>
                        <th className="p-2.5 w-1/3">Core Purpose</th>
                        <th className="p-2.5 w-20 text-center">Page</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {sc.scope_items.map((it: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50/60">
                          <td className="p-2.5 font-bold text-slate-900">{it.area}</td>
                          <td className="p-2.5 text-slate-800">{it.description}</td>
                          <td className="p-2.5 text-slate-600">{it.purpose}</td>
                          <td className="p-2.5 text-center">
                            <button
                              onClick={() =>
                                openPdfEvidence(
                                  it.source_page,
                                  it.description,
                                  it.area,
                                  'Technical Scope',
                                  it.source_file,
                                  it.document_id,
                                  'VERIFIED'
                                )
                              }
                              className="font-mono text-blue-600 hover:underline"
                            >
                              Page {it.source_page}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Operational Commitments */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 text-xs pt-1">
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <strong className="text-slate-700 block">Testing & Commissioning</strong>
                  <span className="text-slate-600 text-[11.5px] mt-0.5 block">{formatTenderValue(sc.testing_and_commissioning_obligations, 'As per tender terms')}</span>
                </div>
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <strong className="text-slate-700 block">Training Obligations</strong>
                  <span className="text-slate-600 text-[11.5px] mt-0.5 block">{formatTenderValue(sc.training_obligations, 'As per tender terms')}</span>
                </div>
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <strong className="text-slate-700 block">Maintenance & AMC</strong>
                  <span className="text-slate-600 text-[11.5px] mt-0.5 block">{formatTenderValue(sc.maintenance_and_amc_obligations || ov.warranty_maintenance_period, 'As per tender terms')}</span>
                </div>
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <strong className="text-slate-700 block">SLA & Uptime</strong>
                  <span className="text-slate-600 text-[11.5px] mt-0.5 block">{formatTenderValue(sc.sla_requirements, 'Standard uptime SLA')}</span>
                </div>
              </div>
            </section>
          )}

          {/* -------------------------------------------------------------- */}
          {/* DIMENSION 5: TECHNICAL SPECIFICATION ANALYSIS (SEARCHABLE)     */}
          {/* -------------------------------------------------------------- */}
          {(activeDimension === 'all' || activeDimension === 5) && (
            <section id="dim-5" className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-blue-600" />
                  Dimension 5 — Technical Specification Analysis ({realSpecsCount} items)
                </h3>
                <StatusBadge status="VERIFIED" size="sm" />
              </div>

              {/* Search & Subsystem Filter Controls */}
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <div className="relative flex-1 min-w-[200px]">
                  <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
                  <input
                    type="text"
                    value={specsSearch}
                    onChange={e => setSpecsSearch(e.target.value)}
                    placeholder="Search specifications by equipment, parameter, or brand..."
                    className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-800 placeholder:text-slate-400 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                  />
                </div>

                {subsystemsList.length > 0 && (
                  <div className="flex items-center gap-1.5">
                    <Filter className="w-3.5 h-3.5 text-slate-500" />
                    <select
                      value={specsSubsystem}
                      onChange={e => setSpecsSubsystem(e.target.value)}
                      className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 text-xs focus:outline-hidden"
                    >
                      <option value="all">All Subsystems ({realSpecsCount})</option>
                      {subsystemsList.map((sub, idx) => (
                        <option key={idx} value={sub}>{sub}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {/* Specifications Table */}
              <div className="border border-slate-200 rounded-lg overflow-hidden bg-white shadow-2xs">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-700 font-semibold">
                    <tr>
                      <th className="p-2.5 w-12 text-center">#</th>
                      <th className="p-2.5 w-1/4">Equipment / Component</th>
                      <th className="p-2.5 w-16 text-center">Qty</th>
                      <th className="p-2.5">Key Technical Specifications</th>
                      <th className="p-2.5 w-28">Standards / Brand</th>
                      <th className="p-2.5 w-20 text-center">Page</th>
                      <th className="p-2.5 w-24 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredSpecs.length > 0 ? (
                      filteredSpecs.map((item: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50/60">
                          <td className="p-2.5 text-center font-mono text-slate-400">{idx + 1}</td>
                          <td className="p-2.5 align-top font-bold text-slate-900">{item.item_name}</td>
                          <td className="p-2.5 align-top text-center font-mono font-semibold text-slate-800">
                            {item.required_quantity || '1'}
                          </td>
                          <td className="p-2.5 align-top text-slate-700 leading-relaxed">
                            {item.technical_specifications}
                          </td>
                          <td className="p-2.5 align-top text-slate-600 text-[11px]">
                            {item.mandatory_standards || item.oem_brand_model_mentioned || 'Standard industry'}
                          </td>
                          <td className="p-2.5 align-top text-center">
                            <button
                              onClick={() =>
                                openPdfEvidence(
                                  item.source_page,
                                  item.verbatim_evidence || item.technical_specifications,
                                  item.item_name,
                                  'Technical Specification',
                                  item.source_file,
                                  item.document_id,
                                  'VERIFIED'
                                )
                              }
                              className="font-mono text-blue-600 hover:underline"
                            >
                              Page {item.source_page}
                            </button>
                          </td>
                          <td className="p-2.5 align-top text-center">
                            <StatusBadge status="VERIFIED" />
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={7} className="p-4 text-center text-slate-500 italic">
                          No matching technical specifications found.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Consultant Technical Specs Guidance */}
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-2">
                <strong className="text-slate-900 flex items-center gap-1.5 font-bold">
                  <Cpu className="w-3.5 h-3.5 text-blue-600" />
                  Technical Specification Evaluation & Compliance Strategy:
                </strong>
                <p className="text-slate-800 leading-relaxed font-medium">
                  {sp.overall_spec_evaluation || 'Item-by-item breakdown of hardware, software, and engineering specifications.'}
                </p>
                <p className="text-slate-700 leading-relaxed">
                  <strong>Consultant Action:</strong> Verify each parameter against official OEM datasheets and ensure signed Manufacturer Authorization Forms (MAF) are procured before bidding.
                </p>
              </div>
            </section>
          )}

          {/* -------------------------------------------------------------- */}
          {/* DIMENSION 6: OEM AND PRODUCT REQUIREMENTS                      */}
          {/* -------------------------------------------------------------- */}
          {(activeDimension === 'all' || activeDimension === 6) && (
            <section id="dim-6" className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                  <Briefcase className="w-4 h-4 text-blue-600" />
                  Dimension 6 — OEM and Product Requirement Analysis
                </h3>
                <StatusBadge status="VERIFIED" size="sm" />
              </div>

              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold border ${
                    oem.oem_authorization_required
                      ? 'bg-amber-100 text-amber-900 border-amber-300'
                      : 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  }`}>
                    {oem.oem_authorization_required ? '⚠️ OEM Authorization (MAF) Mandatory' : 'Generic Specifications / Open Policy'}
                  </span>
                  {oem.specific_brands_in_tender && oem.specific_brands_in_tender.length > 0 && (
                    <span className="text-slate-600">
                      Approved / Mentioned Brands: <strong>{oem.specific_brands_in_tender.join(', ')}</strong>
                    </span>
                  )}
                </div>
                <p className="text-slate-700 leading-relaxed">{oem.consultant_notes}</p>
              </div>

              {oem.oem_requirements && oem.oem_requirements.length > 0 && (
                <div className="border border-slate-200 rounded-lg overflow-hidden bg-white shadow-2xs">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-700 font-semibold">
                      <tr>
                        <th className="p-2.5 w-1/4">Requirement</th>
                        <th className="p-2.5">Details</th>
                        <th className="p-2.5 w-28">Mandatory?</th>
                        <th className="p-2.5 w-20 text-center">Page</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {oem.oem_requirements.map((it: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50/60">
                          <td className="p-2.5 font-bold text-slate-900">{it.requirement_name}</td>
                          <td className="p-2.5 text-slate-800">{it.details}</td>
                          <td className="p-2.5 font-semibold text-slate-700">{it.is_mandatory ? 'Yes' : 'No'}</td>
                          <td className="p-2.5 text-center">
                            <button
                              onClick={() =>
                                openPdfEvidence(
                                  it.source_page,
                                  it.details,
                                  it.requirement_name,
                                  'OEM Requirements',
                                  it.source_file,
                                  it.document_id,
                                  'VERIFIED'
                                )
                              }
                              className="font-mono text-blue-600 hover:underline"
                            >
                              Page {it.source_page}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {/* -------------------------------------------------------------- */}
          {/* DIMENSION 7: ADVANCED INTELLIGENT COMPLIANCE & READINESS       */}
          {/* -------------------------------------------------------------- */}
          {(activeDimension === 'all' || activeDimension === 7) && (
            <section id="dim-7" className="space-y-4">
              {/* Header */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                    <Scale className="w-4 h-4 text-blue-600" />
                    Dimension 7 — Intelligent Compliance Matrix & Bidder Readiness
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Evidence-based requirement tracking across 6 canonical procurement categories.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {/* Search Input */}
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="Search requirements..."
                      value={complianceSearch}
                      onChange={e => setComplianceSearch(e.target.value)}
                      className="pl-8 pr-2.5 py-1 text-xs rounded-lg border border-slate-200 bg-white text-slate-700 w-44 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                    />
                  </div>

                  {/* Status Filter */}
                  <select
                    value={complianceFilter}
                    onChange={e => setComplianceFilter(e.target.value)}
                    className="px-2.5 py-1 rounded-lg border border-slate-200 bg-white text-slate-700 text-xs font-medium"
                  >
                    <option value="all">All Statuses ({cp.items?.length || 0})</option>
                    <option value="pending">Pending Evidence</option>
                    <option value="compliant">Compliant</option>
                    <option value="non_compliant">Non-Compliant</option>
                    <option value="needs_review">Needs Review</option>
                    <option value="not_applicable">Not Applicable</option>
                  </select>
                </div>
              </div>

              {/* Category Filter Pills */}
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-xs font-semibold text-slate-500 mr-1">Category:</span>
                {['all', 'Technical', 'Eligibility', 'OEM', 'Statutory', 'Commercial', 'Administrative'].map(cat => {
                  const count = cat === 'all'
                    ? (cp.items?.length || 0)
                    : (cp.items || []).filter((it: any) => (it.category || 'Technical').toLowerCase() === cat.toLowerCase()).length
                  const isSelected = complianceCategoryFilter.toLowerCase() === cat.toLowerCase()
                  return (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setComplianceCategoryFilter(cat)}
                      className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                        isSelected
                          ? 'bg-blue-600 text-white shadow-2xs'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200/80'
                      }`}
                    >
                      {cat === 'all' ? 'All Categories' : cat} ({count})
                    </button>
                  )
                })}
              </div>

              {/* Bidder Readiness KPI Summary Strip */}
              {cp.readiness_summary && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                    {/* KPI 1: Readiness Score */}
                    <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold uppercase text-slate-500">Readiness Score</span>
                        <span className="text-xs font-bold text-blue-600 font-mono">
                          {cp.readiness_summary.overall_readiness_percentage}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-100 h-1.5 rounded-full mt-2 overflow-hidden">
                        <div
                          className="bg-blue-600 h-full rounded-full transition-all duration-300"
                          style={{ width: `${Math.max(cp.readiness_summary.overall_readiness_percentage, 4)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-slate-500 mt-1 block">
                        {cp.readiness_summary.compliant_count} of {cp.readiness_summary.mandatory_requirements} mandatory certified
                      </span>
                    </div>

                    {/* KPI 2: Total Tracked */}
                    <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                      <span className="text-[11px] font-semibold uppercase text-slate-500 block">Requirements Tracked</span>
                      <span className="text-base font-bold text-slate-900 mt-0.5 block font-mono">
                        {cp.readiness_summary.total_requirements}
                      </span>
                      <span className="text-[10px] text-slate-500 block">
                        {cp.readiness_summary.mandatory_requirements} marked mandatory
                      </span>
                    </div>

                    {/* KPI 3: Pending Evidence */}
                    <div className="p-3 bg-amber-50/60 rounded-lg border border-amber-200 shadow-2xs">
                      <span className="text-[11px] font-semibold uppercase text-amber-800 block">Pending Evidence</span>
                      <span className="text-base font-bold text-amber-900 mt-0.5 block font-mono">
                        {cp.readiness_summary.pending_count}
                      </span>
                      <span className="text-[10px] text-amber-700 block">
                        Awaiting bidder proposal / datasheets
                      </span>
                    </div>

                    {/* KPI 4: Missing Documents */}
                    <div className="p-3 bg-indigo-50/60 rounded-lg border border-indigo-200 shadow-2xs">
                      <span className="text-[11px] font-semibold uppercase text-indigo-800 block">Required Documents</span>
                      <span className="text-base font-bold text-indigo-900 mt-0.5 block font-mono">
                        {cp.required_documents?.length || 0}
                      </span>
                      <span className="text-[10px] text-indigo-700 block">
                        Mandatory submission proofs
                      </span>
                    </div>
                  </div>

                  {/* Category Readiness Progress Meters */}
                  {cp.readiness_summary.categories && (
                    <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                      <span className="text-xs font-bold text-slate-800 block mb-2">Category Readiness Breakdown</span>
                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                        {Object.entries(cp.readiness_summary.categories).map(([cName, cData]: [string, any]) => (
                          <div key={cName} className="p-2 bg-white rounded border border-slate-200 text-center">
                            <span className="text-[11px] font-semibold text-slate-700 block truncate">{cName}</span>
                            <span className="text-xs font-bold font-mono text-blue-700 block mt-0.5">
                              {cData.readiness_percentage}%
                            </span>
                            <span className="text-[9.5px] text-slate-500 block">
                              {cData.compliant_count}/{cData.mandatory_count} certified
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Critical Blockers Alert */}
                  {cp.readiness_summary.critical_blockers && cp.readiness_summary.critical_blockers.length > 0 && (
                    <div className="p-3 bg-rose-50/80 rounded-lg border border-rose-200 text-xs text-rose-950 space-y-1.5">
                      <div className="flex items-center gap-1.5 font-bold text-rose-900">
                        <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                        Critical Unresolved Readiness Blockers ({cp.readiness_summary.critical_blockers.length}):
                      </div>
                      <ul className="list-disc list-inside space-y-0.5 text-rose-900/90 pl-1 text-[11.5px]">
                        {cp.readiness_summary.critical_blockers.map((b: string, bIdx: number) => (
                          <li key={bIdx}>{b}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Notice: Separation of Extraction from Bidder Evaluation */}
              <div className="p-2.5 bg-blue-50/70 rounded-lg border border-blue-200 text-xs text-blue-950 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                <div className="leading-relaxed">
                  <strong>Intelligent Compliance Guard:</strong> All tender clauses default strictly to <code>PENDING</code>. Bidder compliance cannot be certified until proposed product datasheets, CA certificates, and MAF authorizations are submitted.
                </div>
              </div>

              {/* Mandatory Documents Checklist Accordion */}
              {cp.required_documents && cp.required_documents.length > 0 && (
                <div className="border border-slate-200 rounded-lg overflow-hidden bg-white shadow-2xs">
                  <div
                    onClick={() => setShowDocumentsChecklist(!showDocumentsChecklist)}
                    className="p-2.5 bg-slate-100/80 hover:bg-slate-200/60 cursor-pointer flex items-center justify-between text-xs font-bold text-slate-800 transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <Briefcase className="w-3.5 h-3.5 text-blue-600" />
                      Mandatory Bidder Document Submission Checklist ({cp.required_documents.length} Required)
                    </span>
                    <span className="text-[11px] text-blue-600 font-normal underline">
                      {showDocumentsChecklist ? 'Hide Checklist' : 'Show Checklist'}
                    </span>
                  </div>

                  {showDocumentsChecklist && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead className="bg-slate-50 border-b border-slate-200 text-slate-700 font-semibold text-[11px]">
                          <tr>
                            <th className="p-2 w-1/4">Document Required</th>
                            <th className="p-2 w-24 text-center">Category</th>
                            <th className="p-2 w-20 text-center">Mandatory?</th>
                            <th className="p-2">Submission Format / Certification</th>
                            <th className="p-2 w-28 text-center">Reference</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {cp.required_documents.map((doc: any, dIdx: number) => (
                            <tr key={dIdx} className="hover:bg-slate-50/60">
                              <td className="p-2 font-semibold text-slate-900">{doc.document_name}</td>
                              <td className="p-2 text-center">
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                                  {doc.category || 'Administrative'}
                                </span>
                              </td>
                              <td className="p-2 text-center">
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                                  {doc.is_mandatory ? 'YES' : 'OPTIONAL'}
                                </span>
                              </td>
                              <td className="p-2 text-slate-700 text-[11.5px]">{doc.submission_format || doc.notes || 'As per tender format'}</td>
                              <td className="p-2 text-center font-mono text-slate-600 text-[11px]">
                                {doc.tender_reference || (doc.source_page ? `Page ${doc.source_page}` : 'Tender Notice')}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Clause-by-Clause Compliance Matrix Table */}
              <div className="border border-slate-200 rounded-lg overflow-hidden bg-white shadow-2xs">
                <div className="p-2.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-800">
                    Detailed Compliance Matrix ({filteredCompliance.length} Clauses Showing)
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead className="bg-slate-50/80 border-b border-slate-200 text-slate-700 font-semibold text-[11px]">
                      <tr>
                        <th className="p-2.5 w-24">Req ID</th>
                        <th className="p-2.5 w-24 text-center">Category</th>
                        <th className="p-2.5 w-1/4">Requirement / Clause</th>
                        <th className="p-2.5">Mandatory Specification</th>
                        <th className="p-2.5 w-32 text-center">Compliance Status</th>
                        <th className="p-2.5 w-1/5">Required Proof / Action</th>
                        <th className="p-2.5 w-24 text-center">Reference</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredCompliance.length > 0 ? (
                        filteredCompliance.map((it: any, idx: number) => {
                          const statusLower = (it.compliance_status || it.compliance_assessment || '').toLowerCase()
                          let statusBadgeClass = 'bg-amber-50 text-amber-800 border-amber-300'
                          let statusLabel = 'PENDING'
                          if (statusLower.includes('compliant') && !statusLower.includes('non') && !statusLower.includes('partially')) {
                            statusBadgeClass = 'bg-emerald-50 text-emerald-800 border-emerald-300'
                            statusLabel = 'COMPLIANT'
                          } else if (statusLower.includes('non')) {
                            statusBadgeClass = 'bg-rose-50 text-rose-800 border-rose-300'
                            statusLabel = 'NON-COMPLIANT'
                          } else if (statusLower.includes('review') || statusLower.includes('unclear')) {
                            statusBadgeClass = 'bg-purple-50 text-purple-800 border-purple-300'
                            statusLabel = 'NEEDS REVIEW'
                          } else if (statusLower.includes('not applicable')) {
                            statusBadgeClass = 'bg-slate-100 text-slate-600 border-slate-300'
                            statusLabel = 'NOT APPLICABLE'
                          }

                          const catLower = (it.category || 'technical').toLowerCase()
                          let catBadgeClass = 'bg-blue-50 text-blue-700 border-blue-200'
                          if (catLower === 'eligibility') catBadgeClass = 'bg-purple-50 text-purple-700 border-purple-200'
                          else if (catLower === 'oem') catBadgeClass = 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          else if (catLower === 'statutory') catBadgeClass = 'bg-amber-50 text-amber-700 border-amber-200'
                          else if (catLower === 'commercial') catBadgeClass = 'bg-cyan-50 text-cyan-700 border-cyan-200'
                          else if (catLower === 'administrative') catBadgeClass = 'bg-slate-100 text-slate-700 border-slate-300'

                          return (
                            <tr key={idx} className="hover:bg-slate-50/60 transition-colors">
                              <td className="p-2.5 font-mono text-[11px] font-bold text-slate-600">
                                {it.requirement_id || `REQ-${idx + 1}`}
                              </td>
                              <td className="p-2.5 text-center">
                                <span className={`px-2 py-0.5 rounded text-[10.5px] font-semibold border ${catBadgeClass}`}>
                                  {it.category || 'Technical'}
                                </span>
                              </td>
                              <td className="p-2.5">
                                <div className="font-bold text-slate-900">{it.item}</div>
                                {it.tender_requirement && it.tender_requirement !== it.item && (
                                  <div className="text-[11px] text-slate-500 mt-0.5">{it.tender_requirement}</div>
                                )}
                              </td>
                              <td className="p-2.5 text-slate-800 leading-snug">
                                {it.mandatory_specification || it.tender_requirement}
                              </td>
                              <td className="p-2.5 text-center">
                                <span className={`px-2 py-0.5 rounded text-[10.5px] font-mono font-bold border ${statusBadgeClass}`}>
                                  {statusLabel}
                                </span>
                              </td>
                              <td className="p-2.5 text-slate-600 text-[11.5px]">
                                {it.required_document_type || it.remarks || 'Datasheet evidence required'}
                              </td>
                              <td className="p-2.5 text-center">
                                {it.source_page ? (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setEvidenceViewerState({
                                        isOpen: true,
                                        targetPage: it.source_page,
                                        filename: it.source_file || report.source_files?.[0] || 'tender.pdf',
                                        documentId: it.document_id,
                                        evidenceText: it.mandatory_specification || it.tender_requirement,
                                        clauseHeading: it.item,
                                        category: it.category || 'Technical',
                                        verificationStatus: 'VERIFIED',
                                      })
                                    }
                                    className="px-2 py-0.5 rounded text-[11px] font-mono text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 transition-colors cursor-pointer"
                                    title="Inspect original tender PDF evidence"
                                  >
                                    Page {it.source_page}
                                  </button>
                                ) : (
                                  <span className="font-mono text-slate-500 text-[11px]">
                                    {it.tender_reference || 'Tender'}
                                  </span>
                                )}
                              </td>
                            </tr>
                          )
                        })
                      ) : (
                        <tr>
                          <td colSpan={7} className="p-6 text-center text-slate-500 italic">
                            No compliance items match the filter criteria.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Consultant Compliance Guidance */}
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-2">
                <strong className="text-slate-900 flex items-center gap-1.5 font-bold">
                  <Scale className="w-3.5 h-3.5 text-blue-600" />
                  Compliance Matrix Strategy & Audit Notes:
                </strong>
                <p className="text-slate-700 leading-relaxed">
                  Mark 'COMPLIED' only with direct page and clause references to OEM published datasheets. Avoid ambiguous responses such as 'Will Comply Post-Award' which are treated as non-compliant deviations. Ensure all mandatory documents (GST, PAN, MAF, Balance Sheets with UDIN) are compiled in Envelope 1 before final bid submission.
                </p>
              </div>
            </section>
          )}

          {/* -------------------------------------------------------------- */}
          {/* DIMENSION 8: COMMERCIAL AND FINANCIAL ANALYSIS                 */}
          {/* -------------------------------------------------------------- */}
          {(activeDimension === 'all' || activeDimension === 8) && (
            <section id="dim-8" className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-blue-600" />
                  Dimension 8 — Commercial and Financial Analysis
                </h3>
                <StatusBadge status="VERIFIED" size="sm" />
              </div>

              <div className="border border-slate-200 rounded-lg overflow-hidden bg-white shadow-2xs">
                <table className="w-full text-left text-xs border-collapse">
                  <tbody className="divide-y divide-slate-100">
                    <tr className="hover:bg-slate-50/60">
                      <td className="p-3 w-1/3 font-semibold text-slate-600 bg-slate-50/70">Estimated Tender Value</td>
                      <td className="p-3 font-bold text-slate-900">{formatTenderValue(ov.estimated_project_value)}</td>
                    </tr>
                    <tr className="hover:bg-slate-50/60">
                      <td className="p-3 font-semibold text-slate-600 bg-slate-50/70">Earnest Money Deposit (EMD)</td>
                      <td className="p-3 text-slate-800">{formatTenderValue(ov.emd_value || cm.emd_amount)} ({formatTenderValue(cm.emd_exemption_rules, 'Refer to tender terms')})</td>
                    </tr>
                    <tr className="hover:bg-slate-50/60">
                      <td className="p-3 font-semibold text-slate-600 bg-slate-50/70">Payment Milestones</td>
                      <td className="p-3 text-slate-800 leading-relaxed">{formatTenderValue(cm.payment_terms)}</td>
                    </tr>
                    <tr className="bg-rose-50/40 hover:bg-rose-50/70">
                      <td className="p-3 font-semibold text-rose-800 bg-rose-50/70">Liquidated Damages (Delay Penalty)</td>
                      <td className="p-3 font-medium text-rose-900 leading-relaxed">{formatTenderValue(cm.penalties_and_liquidated_damages)}</td>
                    </tr>
                    <tr className="hover:bg-slate-50/60">
                      <td className="p-3 font-semibold text-slate-600 bg-slate-50/70">Performance Bank Guarantee (PBG)</td>
                      <td className="p-3 text-slate-800">{formatTenderValue(cm.performance_bank_guarantee_pbg)}</td>
                    </tr>
                    <tr className="hover:bg-slate-50/60">
                      <td className="p-3 font-semibold text-slate-600 bg-slate-50/70">Security Deposit / Retention</td>
                      <td className="p-3 text-slate-800">{formatTenderValue(cm.retention_amount || cm.security_deposit)}</td>
                    </tr>
                    <tr className="hover:bg-slate-50/60">
                      <td className="p-3 font-semibold text-slate-600 bg-slate-50/70">Advance Payment Allowed</td>
                      <td className="p-3 text-slate-800">{formatTenderValue(cm.advance_payment_allowed, 'No advance payment permitted')}</td>
                    </tr>
                    <tr className="hover:bg-slate-50/60">
                      <td className="p-3 font-semibold text-slate-600 bg-slate-50/70">Price Validity Period</td>
                      <td className="p-3 text-slate-800">{formatTenderValue(cm.price_validity_period)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Financial Exposure & Cash Flow Analysis */}
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-2">
                <strong className="text-slate-900 flex items-center gap-1.5 font-bold">
                  <DollarSign className="w-3.5 h-3.5 text-blue-600" />
                  Bidder Financial Exposure & Cash Flow Strategy:
                </strong>
                <p className="text-slate-800 leading-relaxed font-medium">
                  {cm.bidder_impact_analysis || 'Review working capital requirements between milestone delivery and acceptance sign-offs. Factor bank guarantee commissions into pricing.'}
                </p>
                <p className="text-slate-700 leading-relaxed">
                  <strong>Consultant Financial Recommendation:</strong> Engage relationship bank to verify non-fund based limit readiness for PBG and factor 60 to 90-day disbursement cycles into working capital provisions.
                </p>
              </div>
            </section>
          )}

          {/* -------------------------------------------------------------- */}
          {/* DIMENSION 9: CONTRACTUAL AND LEGAL CONDITIONS                  */}
          {/* -------------------------------------------------------------- */}
          {(activeDimension === 'all' || activeDimension === 9) && (
            <section id="dim-9" className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-blue-600" />
                  Dimension 9 — Contractual and Legal Analysis
                </h3>
                <StatusBadge status="VERIFIED" size="sm" />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs space-y-1">
                  <div className="flex items-center justify-between">
                    <strong className="text-slate-800">Contract & Warranty Tenure</strong>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-100 text-slate-700">ACTUAL TENDER CLAUSE</span>
                  </div>
                  <p className="text-slate-600">{formatTenderValue(ov.contract_duration)} (Warranty: {formatTenderValue(ov.warranty_maintenance_period)})</p>
                </div>

                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs space-y-1">
                  <div className="flex items-center justify-between">
                    <strong className="text-slate-800">Delivery & Implementation Timeline</strong>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-100 text-slate-700">ACTUAL TENDER CLAUSE</span>
                  </div>
                  <p className="text-slate-600">{formatTenderValue(ov.delivery_implementation_period)}</p>
                </div>

                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs space-y-1">
                  <div className="flex items-center justify-between">
                    <strong className="text-slate-800">Termination Conditions</strong>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-100 text-slate-700">ACTUAL TENDER CLAUSE</span>
                  </div>
                  <p className="text-slate-600">{formatTenderValue(cl.termination_conditions, 'Termination for default, insolvency, or prolonged SLA failure')}</p>
                </div>

                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs space-y-1">
                  <div className="flex items-center justify-between">
                    <strong className="text-slate-800">Dispute Resolution & Jurisdiction</strong>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-100 text-slate-700">ACTUAL TENDER CLAUSE</span>
                  </div>
                  <p className="text-slate-600">{formatTenderValue(cl.dispute_resolution_and_jurisdiction)}</p>
                </div>
              </div>

              {/* Legal Risk & Protection Guidance */}
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-2">
                <strong className="text-slate-900 flex items-center gap-1.5 font-bold">
                  <ShieldAlert className="w-3.5 h-3.5 text-blue-600" />
                  Legal Liability & Contractual Dispute Safeguards:
                </strong>
                <p className="text-slate-700 leading-relaxed">
                  Review draft contract to ensure overall contractor indemnity and liability are capped at 100% of contract value. Confirm dispute resolution jurisdiction (e.g. city civil courts vs arbitration tribunal) to anticipate legal exposure.
                </p>
              </div>
            </section>
          )}

          {/* -------------------------------------------------------------- */}
          {/* DIMENSION 10: RISK AND CONTRADICTION ANALYSIS                  */}
          {/* -------------------------------------------------------------- */}
          {(activeDimension === 'all' || activeDimension === 10) && (
            <section id="dim-10" className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-rose-900 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600" />
                  Dimension 10 — Risk & Contradiction Analysis
                </h3>

                {/* Severity Filter Buttons */}
                <div className="flex items-center gap-1 text-xs">
                  {['all', 'critical', 'high', 'medium', 'low'].map(sev => (
                    <button
                      key={sev}
                      onClick={() => setRiskSeverityFilter(sev)}
                      className={`px-2 py-0.5 rounded capitalize text-[11px] font-semibold transition-colors ${
                        riskSeverityFilter === sev
                          ? 'bg-rose-600 text-white shadow-2xs'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      {sev}
                    </button>
                  ))}
                </div>
              </div>

              {/* Contradictions Box (Separated from Ordinary Risks) */}
              {rk.contradictions_found && rk.contradictions_found.length > 0 && (
                <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-900 space-y-1.5">
                  <div className="font-bold text-amber-950 flex items-center gap-1.5">
                    <AlertCircle className="w-4 h-4 text-amber-600" />
                    CONFLICT DETECTED — VERIFICATION REQUIRED ({rk.contradictions_found.length})
                  </div>
                  <ul className="list-disc list-inside space-y-1 pl-1">
                    {rk.contradictions_found.map((c: string, idx: number) => (
                      <li key={idx} className="leading-relaxed">{c}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Risk Register Cards */}
              <div className="space-y-2">
                {filteredRisks.length > 0 ? (
                  filteredRisks.map((risk: any, idx: number) => (
                    <div key={idx} className="p-3 bg-white rounded-lg border border-slate-200 text-xs space-y-1.5 shadow-2xs">
                      <div className="flex flex-wrap items-center justify-between gap-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900">{risk.risk_title}</span>
                          <span className="px-1.5 py-0.2 rounded text-[10px] font-bold uppercase bg-amber-100 text-amber-900">
                            {risk.risk_level}
                          </span>
                        </div>
                        <button
                          onClick={() =>
                            openPdfEvidence(
                              risk.source_page,
                              risk.tender_evidence,
                              risk.risk_title,
                              'Risk Evidence',
                              risk.source_file,
                              risk.document_id,
                              'VERIFIED'
                            )
                          }
                          className="font-mono text-blue-600 hover:underline"
                        >
                          Page {risk.source_page}
                        </button>
                      </div>

                      <div className="text-slate-700 bg-slate-50 p-2 rounded border border-slate-100 italic text-[11.5px]">
                        <strong>Tender Evidence:</strong> "{risk.tender_evidence}"
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-slate-600">
                        <div><strong>Why It Matters:</strong> {risk.why_it_matters}</div>
                        <div><strong className="text-emerald-700">Recommended Action:</strong> {risk.recommended_action}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-500 italic p-3 text-center bg-slate-50 rounded-lg">
                    No risk items match the selected severity.
                  </p>
                )}
              </div>
            </section>
          )}

          {/* -------------------------------------------------------------- */}
          {/* DIMENSION 11: BID STRATEGY & ACTION ROADMAP                    */}
          {/* -------------------------------------------------------------- */}
          {(activeDimension === 'all' || activeDimension === 11) && (
            <section id="dim-11" className="space-y-4">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-blue-600" />
                  Dimension 11 — Bid Strategy & Recommendations
                </h3>
                <span className="text-[11px] font-mono uppercase bg-blue-50 text-blue-700 px-2 py-0.5 rounded border border-blue-200">
                  Strategic Plan & Bid Recommendation
                </span>
              </div>

              {deadlinePassed && (
                <div className="p-3 bg-rose-50 border border-rose-300 rounded-lg text-xs text-rose-950 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-rose-600 shrink-0" />
                  <span><strong>SUBMISSION DEADLINE PASSED:</strong> Bid submission deadline was {ov.bid_submission_deadline}. Do not disburse EMD or purchase bid security without an active extension corrigendum.</span>
                </div>
              )}

              {/* Part 1: Strategic Assessment */}
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-2">
                <strong className="text-slate-900">Bid Suitability & Strategic Assessment:</strong>
                <p className="text-slate-800 leading-relaxed font-medium">{bs.overall_tender_assessment}</p>
                <p className="text-slate-600 leading-relaxed">{bs.technical_preparation_strategy}</p>
              </div>

              {/* Part 2: Pre-Bid Clarification Queries */}
              {bs.prebid_clarification_questions && bs.prebid_clarification_questions.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  <strong className="text-xs text-slate-800">
                    Suggested Pre-Bid Queries (Ready for Submission):
                  </strong>
                  <ol className="list-decimal list-inside space-y-1 text-xs text-slate-700 bg-white p-3 rounded-lg border border-slate-200">
                    {bs.prebid_clarification_questions.map((q: string, idx: number) => (
                      <li key={idx} className="leading-relaxed font-mono text-[11.5px]">{q}</li>
                    ))}
                  </ol>
                </div>
              )}
            </section>
          )}

        </main>
      </div>

      {/* ================================================================== */}
      {/* 4. FOOTER STATUS BAR                                               */}
      {/* ================================================================== */}
      <footer className="px-5 py-2.5 bg-slate-100/80 border-t border-slate-200 rounded-b-xl flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 print:hidden">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span>System Status: <strong className="text-slate-700">{report.validation_status || 'VERIFIED'}</strong></span>
          <span>•</span>
          <span>{report.total_pages_analyzed} Pages Scanned</span>
          {report.elapsed_seconds && <span>({report.elapsed_seconds}s)</span>}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => exportDossierPrint(report)}
            className="hover:text-blue-700 flex items-center gap-1 font-semibold"
          >
            <Printer className="w-3.5 h-3.5 text-blue-600" />
            <span>Print Report (All 11 Dimensions)</span>
          </button>
        </div>
      </footer>

      {/* ================================================================== */}
      {/* 5. PDF EVIDENCE INSPECTOR MODAL                                    */}
      {/* ================================================================== */}
      <PdfEvidenceViewer
        isOpen={evidenceViewerState.isOpen}
        onClose={() => setEvidenceViewerState(prev => ({ ...prev, isOpen: false }))}
        targetPage={evidenceViewerState.targetPage}
        filename={evidenceViewerState.filename}
        documentId={evidenceViewerState.documentId}
        evidenceText={evidenceViewerState.evidenceText}
        clauseHeading={evidenceViewerState.clauseHeading}
        category={evidenceViewerState.category}
        verificationStatus={evidenceViewerState.verificationStatus}
      />
    </div>
  )
}

import React, { useState } from 'react'
import { LayoutDashboard, FileText } from 'lucide-react'
import { TenderConsultantDashboard } from '../tender/TenderConsultantDashboard'
import type { MasterTenderReport } from '../tender/types'

export interface TenderIntelligenceCardProps {
  report: MasterTenderReport
}

export const TenderIntelligenceCard: React.FC<TenderIntelligenceCardProps> = ({ report }) => {
  const [viewMode, setViewMode] = useState<'dashboard' | 'reading'>('dashboard')

  return (
    <div className="w-full space-y-3">
      {/* Top View Mode Switcher */}
      <div className="flex items-center justify-between text-xs text-slate-500 pb-1 print:hidden">
        <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200">
          <button
            onClick={() => setViewMode('dashboard')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold transition-all ${
              viewMode === 'dashboard'
                ? 'bg-white text-blue-900 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <LayoutDashboard className="w-3.5 h-3.5 text-blue-600" />
            <span>Enterprise Dashboard</span>
          </button>
          <button
            onClick={() => setViewMode('reading')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold transition-all ${
              viewMode === 'reading'
                ? 'bg-white text-blue-900 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <FileText className="w-3.5 h-3.5 text-slate-600" />
            <span>Executive Reading View</span>
          </button>
        </div>

        <span className="text-[11px] font-mono text-slate-400">
          Tender Dossier Ref: {report.overview?.tender_reference_number || 'N/A'}
        </span>
      </div>

      {/* Main View Display */}
      {viewMode === 'dashboard' ? (
        <TenderConsultantDashboard report={report} />
      ) : (
        <div className="p-6 bg-white rounded-xl border border-slate-200 shadow-xs space-y-4">
          <div className="prose prose-sm prose-slate max-w-none whitespace-pre-wrap font-sans text-xs md:text-sm leading-relaxed text-slate-800">
            {report.consultant_briefing_markdown || report.executive_summary_markdown || report.full_report_markdown}
          </div>
        </div>
      )}
    </div>
  )
}

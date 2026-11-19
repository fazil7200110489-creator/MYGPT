import React from 'react'
import {
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  HelpCircle,
  Slash,
  Eye,
  FileCheck,
  Clock
} from 'lucide-react'
import type { VerificationStatusType } from './types'

interface StatusBadgeProps {
  status?: VerificationStatusType | string
  className?: string
  size?: 'sm' | 'md'
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status = 'NOT FOUND IN SOURCE',
  className = '',
  size = 'sm'
}) => {
  const norm = (status || '').toUpperCase().trim()

  let label = 'NOT FOUND IN SOURCE'
  let colorCls = 'bg-slate-100 text-slate-600 border-slate-200'
  let icon = <HelpCircle className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />

  if (norm.includes('DEADLINE PASSED')) {
    label = 'SUBMISSION DEADLINE PASSED'
    colorCls = 'bg-rose-100 text-rose-800 border-rose-300'
    icon = <Clock className={size === 'sm' ? 'w-3 h-3 text-rose-600' : 'w-3.5 h-3.5 text-rose-600'} />
  } else if (norm.includes('REQUIREMENT EXTRACTED')) {
    label = 'REQUIREMENT EXTRACTED'
    colorCls = 'bg-blue-50 text-blue-800 border-blue-200'
    icon = <FileCheck className={size === 'sm' ? 'w-3 h-3 text-blue-600' : 'w-3.5 h-3.5 text-blue-600'} />
  } else if (norm.includes('PARTIALLY')) {
    label = 'PARTIALLY VERIFIED'
    colorCls = 'bg-teal-50 text-teal-800 border-teal-200'
    icon = <AlertCircle className={size === 'sm' ? 'w-3 h-3 text-teal-600' : 'w-3.5 h-3.5 text-teal-600'} />
  } else if (norm.includes('VERIFIED')) {
    label = 'VERIFIED'
    colorCls = 'bg-emerald-50 text-emerald-800 border-emerald-200'
    icon = <CheckCircle2 className={size === 'sm' ? 'w-3 h-3 text-emerald-600' : 'w-3.5 h-3.5 text-emerald-600'} />
  } else if (norm.includes('CONFLICT') || norm.includes('AMBIGUOUS')) {
    label = 'CONFLICT DETECTED — VERIFICATION REQUIRED'
    colorCls = 'bg-amber-50 text-amber-900 border-amber-300'
    icon = <AlertTriangle className={size === 'sm' ? 'w-3 h-3 text-amber-600' : 'w-3.5 h-3.5 text-amber-600'} />
  } else if (norm.includes('BIDDER INFORMATION') || norm.includes('VERIFICATION REQUIRED')) {
    label = 'VERIFICATION REQUIRED'
    colorCls = 'bg-amber-50 text-amber-900 border-amber-300'
    icon = <AlertCircle className={size === 'sm' ? 'w-3 h-3 text-amber-600' : 'w-3.5 h-3.5 text-amber-600'} />
  } else if (norm.includes('NOT EVALUATED')) {
    label = 'NOT EVALUATED'
    colorCls = 'bg-slate-100 text-slate-700 border-slate-300'
    icon = <HelpCircle className={size === 'sm' ? 'w-3 h-3 text-slate-500' : 'w-3.5 h-3.5 text-slate-500'} />
  } else if (norm.includes('NEEDS REVIEW') || norm.includes('REVIEW')) {
    label = 'NEEDS REVIEW'
    colorCls = 'bg-rose-50 text-rose-800 border-rose-200'
    icon = <Eye className={size === 'sm' ? 'w-3 h-3 text-rose-600' : 'w-3.5 h-3.5 text-rose-600'} />
  } else if (norm.includes('NOT APPLICABLE') || norm === 'N/A') {
    label = 'NOT APPLICABLE'
    colorCls = 'bg-zinc-100 text-zinc-600 border-zinc-200'
    icon = <Slash className={size === 'sm' ? 'w-3 h-3 text-zinc-500' : 'w-3.5 h-3.5 text-zinc-500'} />
  } else if (norm.includes('NOT_FOUND') || norm.includes('NOT FOUND')) {
    label = 'NOT FOUND IN SOURCE'
    colorCls = 'bg-slate-100 text-slate-500 border-slate-200'
    icon = <HelpCircle className={size === 'sm' ? 'w-3 h-3 text-slate-400' : 'w-3.5 h-3.5 text-slate-400'} />
  }

  const paddingCls = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs'

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded font-mono font-medium border ${colorCls} ${paddingCls} ${className}`}
      title={`Status: ${label}`}
    >
      {icon}
      <span>{label}</span>
    </span>
  )
}


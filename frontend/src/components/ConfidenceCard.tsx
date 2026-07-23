import { CheckCircle2 } from 'lucide-react'

export interface ConfidenceBreakdown {
  intent_confidence: number
  entity_confidence: number
  evidence_confidence: number
  final_confidence: number
}

export interface ConfidenceCardProps {
  confidence: number
  breakdown?: ConfidenceBreakdown
}

export function ConfidenceCard({ confidence, breakdown }: ConfidenceCardProps) {
  return (
    <div className="flex flex-col gap-2.5 w-full max-w-xs mt-2.5 bg-slate-100 p-3.5 rounded-xl border border-slate-300 shadow-2xs">
      <div className="flex justify-between items-center text-xs font-bold text-slate-800">
        <span className="flex items-center gap-1.5">
          <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
          Reasoning Confidence
        </span>
        <span className="text-slate-900 font-black text-xs">{confidence}%</span>
      </div>

      {breakdown && (
        <div className="grid grid-cols-2 gap-2 text-[10px] pt-2 border-t border-slate-300">
          <div className="flex items-center justify-between bg-white p-1.5 rounded-md border border-slate-200">
            <span className="text-slate-700 font-bold">Intent:</span>
            <span className="font-extrabold text-slate-900">{breakdown.intent_confidence}%</span>
          </div>
          <div className="flex items-center justify-between bg-white p-1.5 rounded-md border border-slate-200">
            <span className="text-slate-700 font-bold">Entity:</span>
            <span className="font-extrabold text-slate-900">{breakdown.entity_confidence}%</span>
          </div>
          <div className="flex items-center justify-between bg-white p-1.5 rounded-md border border-slate-200">
            <span className="text-slate-700 font-bold">Evidence:</span>
            <span className="font-extrabold text-slate-900">{breakdown.evidence_confidence}%</span>
          </div>
          <div className="flex items-center justify-between bg-indigo-100 p-1.5 rounded-md border border-indigo-300">
            <span className="text-indigo-900 font-black">Final:</span>
            <span className="font-black text-indigo-900">{breakdown.final_confidence}%</span>
          </div>
        </div>
      )}
    </div>
  )
}

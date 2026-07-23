import { CheckCircle2, AlertTriangle, Sparkles, ShieldCheck } from 'lucide-react'

export interface RoleMatchCardProps {
  matchPercentage: number
  suitabilityTier: 'Highly Suitable' | 'Suitable' | 'Partially Suitable' | 'Not Suitable' | string
  isQualified: boolean
  matchingSkills: string[]
  missingSkills: string[]
  reason: string
  recommendation?: string
  evidence?: string
  confidence?: number
}

export function CircularProgressRing({ value, tier }: { value: number; tier: string }) {
  const radius = 36
  const stroke = 6
  const normalizedRadius = radius - stroke * 2
  const circumference = normalizedRadius * 2 * Math.PI
  const strokeDashoffset = circumference - (Math.max(0, Math.min(100, value)) / 100) * circumference

  let strokeColor = '#10b981'
  if (value < 35 || tier === 'Not Suitable') strokeColor = '#ef4444'
  else if (value < 60 || tier === 'Partially Suitable') strokeColor = '#f59e0b'
  else if (value < 85 || tier === 'Suitable') strokeColor = '#0284c7'

  return (
    <div className="relative flex items-center justify-center shrink-0">
      <svg height={radius * 2} width={radius * 2} className="transform -rotate-90">
        <circle
          stroke="rgba(226, 232, 240, 0.8)"
          fill="transparent"
          strokeWidth={stroke}
          r={normalizedRadius}
          cx={radius}
          cy={radius}
        />
        <circle
          stroke={strokeColor}
          fill="transparent"
          strokeWidth={stroke}
          strokeDasharray={circumference + ' ' + circumference}
          style={{ strokeDashoffset }}
          strokeLinecap="round"
          r={normalizedRadius}
          cx={radius}
          cy={radius}
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <div className="absolute text-center flex flex-col items-center justify-center">
        <span className="text-xs font-black text-slate-900">{value}%</span>
      </div>
    </div>
  )
}

export function RoleMatchCard({
  matchPercentage,
  suitabilityTier,
  isQualified,
  matchingSkills = [],
  missingSkills = [],
  reason,
  recommendation,
  evidence = 'Designation, Domain, Skills',
  confidence = 95
}: RoleMatchCardProps) {
  return (
    <div className="flex flex-col gap-3.5 p-4 bg-white border border-slate-200 rounded-2xl shadow-sm my-1">
      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
        <div className="flex items-center gap-3.5">
          <CircularProgressRing value={matchPercentage} tier={suitabilityTier} />
          <div>
            <div className="text-[10px] uppercase font-black text-slate-600 tracking-wider">Role Suitability Analysis</div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`text-sm font-black ${
                suitabilityTier === 'Highly Suitable' ? 'text-emerald-700' :
                suitabilityTier === 'Suitable' ? 'text-sky-700' :
                suitabilityTier === 'Partially Suitable' ? 'text-amber-700' : 'text-rose-700'
              }`}>
                {suitabilityTier}
              </span>
              <span className="text-xs text-slate-700 font-bold">({matchPercentage}% Match)</span>
            </div>
          </div>
        </div>

        <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-wider ${
          isQualified ? 'bg-emerald-100 text-emerald-900 border border-emerald-300' : 'bg-rose-100 text-rose-900 border border-rose-300'
        }`}>
          {isQualified ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700" /> : <AlertTriangle className="h-3.5 w-3.5 text-rose-700" />}
          {isQualified ? '✓ Qualified' : '✕ Unsuitable'}
        </span>
      </div>

      {reason && (
        <div className="text-xs text-slate-900 font-medium leading-relaxed bg-slate-50 p-3.5 rounded-xl border border-slate-200">
          <span className="font-black text-slate-900">Reason: </span>
          {reason}
        </div>
      )}

      {recommendation && (
        <div className="flex items-start gap-2 text-xs font-semibold text-indigo-900 bg-indigo-50 p-3.5 rounded-xl border border-indigo-200">
          <Sparkles className="h-4 w-4 text-indigo-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-black">Recommendation: </span>
            {recommendation}
          </div>
        </div>
      )}

      {(matchingSkills.length > 0 || missingSkills.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 text-xs pt-0.5">
          {matchingSkills.length > 0 && (
            <div className="flex flex-col gap-1.5 p-3 bg-emerald-50 border border-emerald-200 rounded-xl">
              <span className="text-[10px] font-black text-emerald-900 uppercase tracking-wider">✓ Matching Skills ({matchingSkills.length})</span>
              <div className="flex flex-wrap gap-1">
                {matchingSkills.map((s, idx) => (
                  <span key={idx} className="bg-emerald-100 text-emerald-900 border border-emerald-300 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full">
                    ✓ {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {missingSkills.length > 0 && (
            <div className="flex flex-col gap-1.5 p-3 bg-rose-50 border border-rose-200 rounded-xl">
              <span className="text-[10px] font-black text-rose-900 uppercase tracking-wider">✕ Missing Skills ({missingSkills.length})</span>
              <div className="flex flex-wrap gap-1">
                {missingSkills.map((s, idx) => (
                  <span key={idx} className="bg-rose-100 text-rose-900 border border-rose-300 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex justify-between items-center text-[11px] text-slate-700 font-bold border-t border-slate-200 pt-2.5">
        <span className="flex items-center gap-1">
          <ShieldCheck className="h-3.5 w-3.5 text-indigo-600" />
          Evidence: <strong className="text-slate-900">{evidence}</strong>
        </span>
        <span className="font-extrabold text-slate-800">Confidence: {confidence}%</span>
      </div>
    </div>
  )
}

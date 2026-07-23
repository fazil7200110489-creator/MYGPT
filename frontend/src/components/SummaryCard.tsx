import { User, Briefcase, GraduationCap, Award, Building2, CheckCircle2 } from 'lucide-react'

export interface SummaryCardProps {
  name: string
  designation?: string
  domain?: string
  experience?: string
  education?: string
  recommendedRoles?: string[]
  matchPercentage?: number
  confidence?: number
  summaryText?: string
}

export function SummaryCard({
  name,
  designation = 'Professional Candidate',
  domain = 'General Industry',
  experience = 'Not specified',
  education = 'Not specified',
  recommendedRoles = [],
  matchPercentage = 88,
  confidence = 92,
  summaryText
}: SummaryCardProps) {
  return (
    <div className="flex flex-col gap-4 p-5 bg-gradient-to-br from-white via-slate-50 to-indigo-50/20 border border-slate-200 rounded-2xl shadow-sm my-1">
      <div className="flex items-start justify-between border-b border-slate-200 pb-4">
        <div className="flex items-center gap-4">
          <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-indigo-600 to-purple-600 text-white flex items-center justify-center font-black text-xl shadow-md shrink-0">
            {name.charAt(0).toUpperCase() || <User className="h-7 w-7" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-black text-slate-900 tracking-tight">{name}</h3>
              <span className="bg-indigo-100 text-indigo-800 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full border border-indigo-200">
                Verified Candidate
              </span>
            </div>
            <p className="text-xs font-bold text-indigo-700 mt-0.5">{designation}</p>
            <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-700 font-semibold">
              <span className="flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5 text-indigo-600" />
                {domain}
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Briefcase className="h-3.5 w-3.5 text-indigo-600" />
                {experience}
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-end">
          <div className="flex items-center gap-1 bg-emerald-100 text-emerald-800 border border-emerald-300 px-3 py-1 rounded-full text-xs font-black shadow-2xs">
            <CheckCircle2 className="h-3.5 w-3.5" />
            {matchPercentage}% Match
          </div>
          <span className="text-[11px] text-slate-600 font-bold mt-1">Confidence: {confidence}%</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        <div className="p-3 bg-white border border-slate-200 rounded-xl shadow-2xs">
          <span className="text-[10px] uppercase font-black text-indigo-800 tracking-wider flex items-center gap-1.5 mb-1">
            <GraduationCap className="h-3.5 w-3.5 text-indigo-600" />
            Education Background
          </span>
          <p className="text-slate-900 font-bold">{education}</p>
        </div>

        {recommendedRoles.length > 0 && (
          <div className="p-3 bg-white border border-slate-200 rounded-xl shadow-2xs">
            <span className="text-[10px] uppercase font-black text-purple-800 tracking-wider flex items-center gap-1.5 mb-1.5">
              <Award className="h-3.5 w-3.5 text-purple-600" />
              Recommended Roles ({recommendedRoles.length})
            </span>
            <div className="flex flex-wrap gap-1">
              {recommendedRoles.map((role, idx) => (
                <span key={idx} className="bg-purple-100 text-purple-800 border border-purple-300 text-[10px] font-bold px-2 py-0.5 rounded-md">
                  {role}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {summaryText && (
        <div className="text-xs text-slate-800 leading-relaxed bg-slate-50 p-4 rounded-xl border border-slate-200 whitespace-pre-line font-medium">
          <span className="font-black text-slate-900">Executive Briefing: </span>
          {summaryText}
        </div>
      )}
    </div>
  )
}

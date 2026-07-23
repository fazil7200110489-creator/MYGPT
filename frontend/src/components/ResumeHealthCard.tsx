import { ShieldCheck, CheckCircle2, AlertCircle } from 'lucide-react'

export interface ResumeHealthCardProps {
  score: number
  checklist?: {
    skills: boolean
    experience: boolean
    education: boolean
    projects: boolean
    certifications: boolean
    linkedin: boolean
    achievements: boolean
  }
}

export function ResumeHealthCard({
  score = 85,
  checklist = {
    skills: true,
    experience: true,
    education: true,
    projects: true,
    certifications: false,
    linkedin: true,
    achievements: false
  }
}: ResumeHealthCardProps) {
  const getBadgeColor = (val: number) => {
    if (val >= 85) return 'text-emerald-700 bg-emerald-50 border-emerald-200'
    if (val >= 60) return 'text-amber-700 bg-amber-50 border-amber-200'
    return 'text-rose-700 bg-rose-50 border-rose-200'
  }

  const items = [
    { label: 'Technical & Soft Skills', status: checklist.skills },
    { label: 'Work Experience History', status: checklist.experience },
    { label: 'Academic Education', status: checklist.education },
    { label: 'Key Portfolio Projects', status: checklist.projects },
    { label: 'Certifications & Licensing', status: checklist.certifications },
    { label: 'LinkedIn Profile URL', status: checklist.linkedin },
    { label: 'Awards & Key Achievements', status: checklist.achievements }
  ]

  return (
    <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-xs flex flex-col gap-4 my-2">
      <div className="flex items-center justify-between border-b border-slate-150 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-600 flex items-center justify-center font-bold">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-extrabold text-slate-900 text-sm tracking-tight">Resume Health Score</h3>
            <p className="text-[11px] text-slate-500 font-medium">Backend calculated candidate profile completeness</p>
          </div>
        </div>

        <div className={`px-3 py-1 rounded-full border text-xs font-black flex items-center gap-1.5 ${getBadgeColor(score)}`}>
          <span className="text-sm">{score}%</span>
          <span className="text-[10px] uppercase tracking-wider">{score >= 80 ? 'Excellent' : score >= 60 ? 'Good' : 'Needs Improvement'}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
        {items.map((item, idx) => (
          <div key={idx} className="flex items-center justify-between p-2.5 bg-slate-50 border border-slate-200/80 rounded-xl">
            <span className="font-semibold text-slate-700">{item.label}</span>
            {item.status ? (
              <span className="flex items-center gap-1 text-emerald-600 font-bold text-[11px] bg-emerald-100/80 px-2 py-0.5 rounded-md">
                <CheckCircle2 className="h-3.5 w-3.5" /> Present
              </span>
            ) : (
              <span className="flex items-center gap-1 text-amber-600 font-bold text-[11px] bg-amber-100/80 px-2 py-0.5 rounded-md">
                <AlertCircle className="h-3.5 w-3.5" /> Missing
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

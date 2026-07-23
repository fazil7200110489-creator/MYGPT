import { Briefcase, Calendar, Building, CheckCircle } from 'lucide-react'

export interface ExperienceItem {
  title: string
  company?: string
  duration?: string
  responsibilities?: string[]
}

export interface ExperienceTimelineProps {
  totalExperience?: string
  experiences: ExperienceItem[]
}

export function ExperienceTimeline({ totalExperience, experiences = [] }: ExperienceTimelineProps) {
  return (
    <div className="flex flex-col gap-4 p-4.5 bg-white border border-slate-200 rounded-2xl shadow-sm my-1">
      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2 font-black text-slate-900 text-xs uppercase tracking-wider">
          <Briefcase className="h-4 w-4 text-indigo-600" />
          <span>Professional Experience & Career History</span>
        </div>
        {totalExperience && (
          <span className="bg-indigo-100 text-indigo-900 border border-indigo-300 px-3 py-1 rounded-full text-xs font-black shadow-2xs">
            Total: {totalExperience}
          </span>
        )}
      </div>

      <div className="flex flex-col gap-4 timeline-border pl-4 relative my-1">
        {experiences.map((exp, idx) => (
          <div key={idx} className="relative group">
            <div className="absolute -left-[23px] top-1.5 h-3.5 w-3.5 rounded-full bg-white border-2 border-indigo-600 group-hover:scale-125 group-hover:bg-indigo-600 transition-all duration-200 shadow-2xs" />

            <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl hover:bg-white hover:border-indigo-400 hover:shadow-md transition-all duration-300">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-1 mb-2">
                <div className="font-extrabold text-slate-900 text-xs flex items-center gap-2">
                  <Building className="h-3.5 w-3.5 text-indigo-600 shrink-0" />
                  {exp.title}
                </div>
                {exp.duration && (
                  <span className="text-[10px] font-bold text-slate-700 bg-slate-200 px-2.5 py-0.5 rounded-md flex items-center gap-1 w-fit">
                    <Calendar className="h-3 w-3 text-slate-500" />
                    {exp.duration}
                  </span>
                )}
              </div>

              {exp.responsibilities && exp.responsibilities.length > 0 && (
                <ul className="space-y-1.5 text-slate-800 text-[11px] pl-1 pt-1 font-semibold">
                  {exp.responsibilities.map((resp, rIdx) => (
                    <li key={rIdx} className="leading-relaxed flex items-start gap-2 text-slate-800">
                      <CheckCircle className="h-3.5 w-3.5 text-indigo-600 shrink-0 mt-0.5" />
                      <span>{resp}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

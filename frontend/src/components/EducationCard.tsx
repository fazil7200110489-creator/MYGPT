import { GraduationCap, Building2, Calendar, Award } from 'lucide-react'

export interface EducationItem {
  degree: string
  institution?: string
  year?: string
  score?: string
  details?: string[]
}

export interface EducationCardProps {
  educations: EducationItem[]
}

export function EducationCard({ educations = [] }: EducationCardProps) {
  return (
    <div className="flex flex-col gap-3.5 p-4.5 bg-white border border-slate-200 rounded-2xl shadow-sm my-1">
      <div className="flex items-center gap-2 font-black text-slate-900 text-xs uppercase tracking-wider border-b border-slate-200 pb-2.5">
        <GraduationCap className="h-4 w-4 text-indigo-600" />
        <span>Academic Qualifications & Education</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-0.5">
        {educations.map((edu, idx) => (
          <div key={idx} className="flex flex-col justify-between p-4 bg-slate-50 border border-slate-200 rounded-xl hover:bg-white hover:border-purple-400 hover:shadow-md transition-all duration-300">
            <div>
              <div className="flex items-center gap-2 font-extrabold text-slate-900 text-xs mb-1">
                <span className="h-2 w-2 rounded-full bg-purple-600 shrink-0" />
                {edu.degree}
              </div>

              {edu.institution && (
                <div className="text-[11px] font-bold text-slate-700 flex items-center gap-1.5 mt-1 pl-4">
                  <Building2 className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                  {edu.institution}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-slate-200 pt-2.5 mt-3 text-[10px] font-bold text-slate-700 pl-4">
              {edu.year ? (
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3 text-slate-500" />
                  {edu.year}
                </span>
              ) : <span>Year: N/A</span>}

              {edu.score && (
                <span className="flex items-center gap-1 text-purple-900 bg-purple-100 px-2 py-0.5 rounded-md border border-purple-300 font-extrabold">
                  <Award className="h-3 w-3 text-purple-600" />
                  {edu.score}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

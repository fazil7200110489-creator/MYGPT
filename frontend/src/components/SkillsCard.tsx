import { Code, Wrench, Users, Cpu } from 'lucide-react'

export interface SkillsCardProps {
  technicalSkills?: string[]
  softSkills?: string[]
  toolsAndFrameworks?: string[]
  allSkills?: string[]
}

export function SkillsCard({
  technicalSkills = [],
  softSkills = [],
  toolsAndFrameworks = [],
  allSkills = []
}: SkillsCardProps) {
  const hasCategories = technicalSkills.length > 0 || softSkills.length > 0 || toolsAndFrameworks.length > 0
  const displaySkills = hasCategories ? [] : allSkills

  return (
    <div className="flex flex-col gap-3.5 p-4.5 bg-white border border-slate-200 rounded-2xl shadow-sm my-1">
      <div className="flex items-center gap-2 font-black text-slate-900 text-xs uppercase tracking-wider border-b border-slate-200 pb-2.5">
        <Cpu className="h-4 w-4 text-indigo-600" />
        <span>Skills & Technical Expertise</span>
      </div>

      {hasCategories ? (
        <div className="flex flex-col gap-3 text-xs">
          {technicalSkills.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase font-black text-indigo-800 tracking-wider flex items-center gap-1.5">
                <Code className="h-3.5 w-3.5 text-indigo-600" />
                Technical Skills ({technicalSkills.length})
              </span>
              <div className="flex flex-wrap gap-1.5">
                {technicalSkills.map((s, idx) => (
                  <span key={idx} className="bg-indigo-100 text-indigo-900 border border-indigo-300 text-xs font-bold px-3 py-1 rounded-full shadow-2xs">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {toolsAndFrameworks.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase font-black text-purple-800 tracking-wider flex items-center gap-1.5">
                <Wrench className="h-3.5 w-3.5 text-purple-600" />
                Tools & Frameworks ({toolsAndFrameworks.length})
              </span>
              <div className="flex flex-wrap gap-1.5">
                {toolsAndFrameworks.map((s, idx) => (
                  <span key={idx} className="bg-purple-100 text-purple-900 border border-purple-300 text-xs font-bold px-3 py-1 rounded-full shadow-2xs">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {softSkills.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase font-black text-emerald-800 tracking-wider flex items-center gap-1.5">
                <Users className="h-3.5 w-3.5 text-emerald-600" />
                Soft Skills & Leadership ({softSkills.length})
              </span>
              <div className="flex flex-wrap gap-1.5">
                {softSkills.map((s, idx) => (
                  <span key={idx} className="bg-emerald-100 text-emerald-900 border border-emerald-300 text-xs font-bold px-3 py-1 rounded-full shadow-2xs">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2 pt-1">
          {displaySkills.map((s, idx) => (
            <span key={idx} className="bg-indigo-100 text-indigo-900 border border-indigo-300 text-xs font-bold px-3 py-1 rounded-full shadow-2xs">
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

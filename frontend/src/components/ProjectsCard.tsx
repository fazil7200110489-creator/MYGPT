import { Rocket, Code2, CheckCircle2, AlertCircle } from 'lucide-react'

export interface ProjectItem {
  title: string
  role?: string
  responsibilities?: string[]
  techStack?: string[]
}

export interface ProjectsCardProps {
  projects: ProjectItem[]
  noProjectsAvailable?: boolean
}

export function ProjectsCard({ projects = [], noProjectsAvailable = false }: ProjectsCardProps) {
  if (noProjectsAvailable || projects.length === 0) {
    return (
      <div className="flex items-center gap-3 p-4 bg-slate-50 border border-slate-200 rounded-2xl text-slate-700 text-xs font-semibold italic my-1">
        <AlertCircle className="h-4 w-4 text-slate-500 shrink-0" />
        <span>No project information is available in the resume.</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3.5 p-4.5 bg-white border border-slate-200 rounded-2xl shadow-sm my-1">
      <div className="flex items-center gap-2 font-black text-slate-900 text-xs uppercase tracking-wider border-b border-slate-200 pb-2.5">
        <Rocket className="h-4 w-4 text-indigo-600" />
        <span>Key Projects & Portfolio Highlights ({projects.length})</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-0.5">
        {projects.map((proj, idx) => (
          <div key={idx} className="relative bg-slate-50 border border-slate-200 p-4 rounded-xl hover:bg-white hover:border-indigo-400 hover:shadow-md transition-all duration-300 flex flex-col justify-between overflow-hidden">
            <div className="absolute top-2 right-3 font-black text-2xl text-slate-300/80 select-none">
              0{idx + 1}
            </div>

            <div>
              <div className="font-extrabold text-slate-900 text-xs mb-1 pr-6 leading-snug">
                {proj.title}
              </div>
              {proj.role && (
                <div className="text-[10px] font-extrabold text-indigo-700 mb-2">
                  Role: {proj.role}
                </div>
              )}

              {proj.responsibilities && proj.responsibilities.length > 0 && (
                <ul className="space-y-1 text-slate-800 text-[11px] pl-1 font-medium">
                  {proj.responsibilities.map((resp, rIdx) => (
                    <li key={rIdx} className="leading-relaxed flex items-start gap-1.5 text-slate-800">
                      <CheckCircle2 className="h-3.5 w-3.5 text-indigo-600 shrink-0 mt-0.5" />
                      <span>{resp}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {proj.techStack && proj.techStack.length > 0 && (
              <div className="border-t border-slate-200 pt-2.5 mt-3 flex items-center gap-1.5 flex-wrap">
                <Code2 className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                {proj.techStack.map((tech, tIdx) => (
                  <span key={tIdx} className="bg-indigo-100 text-indigo-900 border border-indigo-300 text-[9px] font-extrabold px-2 py-0.5 rounded-md">
                    {tech}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

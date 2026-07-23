import { User, Briefcase, GraduationCap, Building2, Sparkles, Code, Rocket, Mail, Award } from 'lucide-react'

export interface WelcomeScreenProps {
  documentDetails?: any
  onActionClick: (question: string) => void
}

export function WelcomeScreen({ documentDetails, onActionClick }: WelcomeScreenProps) {
  const candidateName = documentDetails?.metadata?.candidate_name || documentDetails?.filename?.replace(/\.[^/.]+$/, '') || 'Candidate'
  const designation = documentDetails?.metadata?.designation || 'Professional Specialist'
  const domain = documentDetails?.metadata?.domain || 'Enterprise Industry'
  const totalExperience = documentDetails?.metadata?.experience || 'Work Experience Available'
  const education = documentDetails?.metadata?.education || 'Higher Credentials'

  const quickActions = [
    { label: 'Summarize Resume', query: 'Summarize candidate resume', icon: <Sparkles className="h-4 w-4 text-indigo-600" /> },
    { label: 'Show Skills', query: 'Show technical skills', icon: <Code className="h-4 w-4 text-sky-600" /> },
    { label: 'Show Experience', query: 'Show work experience timeline', icon: <Briefcase className="h-4 w-4 text-emerald-600" /> },
    { label: 'Recommended Roles', query: 'What roles are suitable for this candidate?', icon: <Award className="h-4 w-4 text-purple-600" /> },
    { label: 'Education Details', query: 'Show education background', icon: <GraduationCap className="h-4 w-4 text-amber-600" /> },
    { label: 'Key Projects', query: 'Show key projects', icon: <Rocket className="h-4 w-4 text-rose-600" /> },
    { label: 'Contact Details', query: 'Contact details', icon: <Mail className="h-4 w-4 text-teal-600" /> },
    { label: 'Domain & Fit', query: 'What is the domain and overall fit?', icon: <Building2 className="h-4 w-4 text-blue-600" /> },
  ]

  return (
    <div className="flex flex-col gap-6 max-w-3xl mx-auto py-8 animate-fade-in">
      <div className="p-6 bg-gradient-to-br from-white via-slate-50 to-indigo-50/40 border border-slate-200 rounded-3xl shadow-sm flex flex-col md:flex-row items-center gap-6 text-center md:text-left">
        <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-indigo-600 to-purple-600 text-white flex items-center justify-center font-black text-3xl shadow-md shrink-0">
          {candidateName.charAt(0).toUpperCase() || <User className="h-10 w-10" />}
        </div>

        <div className="flex-1">
          <div className="flex flex-wrap items-center justify-center md:justify-start gap-2 mb-1">
            <h2 className="text-xl font-black text-slate-900 tracking-tight">{candidateName}</h2>
            <span className="bg-indigo-100 text-indigo-900 text-xs font-black px-2.5 py-0.5 rounded-full border border-indigo-300">
              Active Candidate
            </span>
          </div>

          <p className="text-sm font-extrabold text-indigo-700">{designation}</p>

          <div className="flex flex-wrap justify-center md:justify-start gap-4 mt-3 text-xs font-bold text-slate-800">
            <span className="flex items-center gap-1.5">
              <Building2 className="h-4 w-4 text-indigo-600" />
              {domain}
            </span>
            <span>•</span>
            <span className="flex items-center gap-1.5">
              <Briefcase className="h-4 w-4 text-indigo-600" />
              {totalExperience}
            </span>
            <span>•</span>
            <span className="flex items-center gap-1.5">
              <GraduationCap className="h-4 w-4 text-indigo-600" />
              {education}
            </span>
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-xs font-black uppercase tracking-wider text-slate-700 pl-1 flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
          Quick Executive Insights
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          {quickActions.map((action, idx) => (
            <button
              key={idx}
              onClick={() => onActionClick(action.query)}
              className="flex items-center gap-3 p-3.5 bg-white border border-slate-200 rounded-2xl hover:border-indigo-500 hover:shadow-md hover:scale-[1.02] transition-all duration-200 text-left group cursor-pointer"
            >
              <div className="h-9 w-9 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0 group-hover:bg-indigo-50 group-hover:border-indigo-300 transition-colors">
                {action.icon}
              </div>
              <span className="text-xs font-extrabold text-slate-900 group-hover:text-indigo-700 transition-colors">
                {action.label}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

import {
  Briefcase, GraduationCap, Sparkles,
  ShieldCheck, CheckCircle2, Award, Mail, Phone, MapPin, Globe
} from 'lucide-react'
import { ResumeHealthCard } from './ResumeHealthCard'

export interface CandidateDashboardProps {
  profile: {
    name?: string
    designation?: string
    domain?: string
    total_experience?: string
    education?: string[] | string
    skills?: string[]
    projects?: string[]
    email?: string
    phone?: string
    address?: string
    linkedin?: string
    github?: string
    portfolio?: string
  }
  healthScore?: number
  healthChecklist?: any
  insights?: {
    career_level?: string
    interview_readiness?: string
    strengths?: string[]
    recommended_roles?: string[]
    improvement_suggestions?: string[]
  }
  roleMatch?: {
    match_percentage?: number
    suitability_tier?: string
    matching_skills?: string[]
    missing_skills?: string[]
    reason?: string
    recommendation?: string
  }
  onQuickAction: (query: string) => void
}

export function CandidateDashboard({
  profile,
  healthScore = 85,
  healthChecklist,
  insights,
  onQuickAction
}: CandidateDashboardProps) {
  const name = profile?.name || 'Candidate Profile'
  const designation = profile?.designation || 'Professional Candidate'
  const domain = profile?.domain || 'General Industry'
  const experience = profile?.total_experience || 'Not specified'
  const educationList = Array.isArray(profile?.education) ? profile.education : [profile?.education || 'Degree Graduate']
  const skillsList = profile?.skills || []
  const recommendedRoles = insights?.recommended_roles || []

  return (
    <div className="flex flex-col gap-6 p-6 bg-slate-50/50 min-h-full">
      {/* Header Profile Hero */}
      <div className="p-6 bg-gradient-to-r from-indigo-900 via-indigo-800 to-purple-900 rounded-3xl text-white shadow-lg relative overflow-hidden">
        <div className="absolute right-0 top-0 opacity-10 pointer-events-none transform translate-x-8 -translate-y-8">
          <Sparkles className="w-64 h-64 text-white" />
        </div>

        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 relative z-10">
          <div className="flex items-center gap-5">
            <div className="h-20 w-20 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 text-white flex items-center justify-center font-black text-3xl shadow-xl shrink-0">
              {name.charAt(0).toUpperCase()}
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-black tracking-tight">{name}</h1>
                <span className="bg-indigo-500/30 text-indigo-200 border border-indigo-400/40 text-[10px] font-black px-3 py-1 rounded-full uppercase tracking-wider">
                  {domain}
                </span>
              </div>
              <p className="text-indigo-200 font-bold text-sm">{designation}</p>

              <div className="flex flex-wrap items-center gap-4 text-xs text-indigo-100/90 pt-1 font-medium">
                <span className="flex items-center gap-1.5">
                  <Briefcase className="h-3.5 w-3.5 text-indigo-300" />
                  {experience}
                </span>
                <span>•</span>
                <span className="flex items-center gap-1.5">
                  <GraduationCap className="h-3.5 w-3.5 text-indigo-300" />
                  {educationList[0] || 'Graduated'}
                </span>
                {profile?.address && (
                  <>
                    <span>•</span>
                    <span className="flex items-center gap-1.5">
                      <MapPin className="h-3.5 w-3.5 text-indigo-300" />
                      {profile.address}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex flex-col items-start md:items-end gap-2 shrink-0">
            <div className="flex items-center gap-2 bg-white/10 backdrop-blur-md border border-white/20 px-4 py-2 rounded-2xl">
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
              <div>
                <div className="text-[10px] text-indigo-200 uppercase font-black tracking-wider">Resume Score</div>
                <div className="text-lg font-black text-white">{healthScore}%</div>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Contact Bar */}
        <div className="mt-6 pt-4 border-t border-white/10 flex flex-wrap items-center gap-4 text-xs text-indigo-100">
          {profile?.email && (
            <a href={`mailto:${profile.email}`} className="flex items-center gap-1.5 hover:text-white transition-colors bg-white/5 px-3 py-1.5 rounded-lg border border-white/10">
              <Mail className="h-3.5 w-3.5 text-indigo-300" />
              {profile.email}
            </a>
          )}
          {profile?.phone && (
            <span className="flex items-center gap-1.5 bg-white/5 px-3 py-1.5 rounded-lg border border-white/10">
              <Phone className="h-3.5 w-3.5 text-indigo-300" />
              {profile.phone}
            </span>
          )}
          {profile?.linkedin && profile.linkedin !== 'Not Mentioned' && (
            <span className="flex items-center gap-1.5 bg-white/5 px-3 py-1.5 rounded-lg border border-white/10">
              <Globe className="h-3.5 w-3.5 text-indigo-300" />
              {profile.linkedin}
            </span>
          )}
          {profile?.github && profile.github !== 'Not Mentioned' && (
            <span className="flex items-center gap-1.5 bg-white/5 px-3 py-1.5 rounded-lg border border-white/10">
              <Globe className="h-3.5 w-3.5 text-indigo-300" />
              {profile.github}
            </span>
          )}
        </div>
      </div>

      {/* Quick Action Intelligence Chips */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs">
        <span className="text-[11px] font-black uppercase text-slate-400 tracking-wider mb-3 block">
          Quick Candidate Intelligence Actions
        </span>
        <div className="flex flex-wrap gap-2.5">
          {[
            { label: 'Summarize Profile', query: 'Summarize candidate profile' },
            { label: 'View Skills', query: 'Skills' },
            { label: 'View Experience', query: 'Give me the experience' },
            { label: 'View Education', query: 'Education' },
            { label: 'View Projects', query: 'Projects' },
            { label: 'Contact Details', query: 'Contact details' },
            { label: 'Role Match Analysis', query: 'Role Match' }
          ].map((action, idx) => (
            <button
              key={idx}
              onClick={() => onQuickAction(action.query)}
              className="px-4 py-2 bg-slate-50 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 border border-slate-200 hover:border-indigo-200 rounded-xl text-xs font-bold transition-all shadow-2xs flex items-center gap-2 cursor-pointer"
            >
              <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
              {action.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid: Insights & Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Health Score & Recommended Roles */}
        <div className="flex flex-col gap-6">
          <ResumeHealthCard score={healthScore} checklist={healthChecklist} />

          {/* Recommended Roles */}
          {recommendedRoles.length > 0 && (
            <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-xs flex flex-col gap-3">
              <div className="flex items-center gap-2 border-b border-slate-150 pb-3">
                <Award className="h-4 w-4 text-purple-600" />
                <h3 className="font-extrabold text-slate-900 text-sm">Recommended Roles</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                {recommendedRoles.map((role, idx) => (
                  <button
                    key={idx}
                    onClick={() => onQuickAction(`Evaluate suitability for ${role}`)}
                    className="bg-purple-50 text-purple-800 border border-purple-200 text-xs font-bold px-3 py-1.5 rounded-xl hover:bg-purple-100 transition-colors cursor-pointer"
                  >
                    {role}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: AI Insights & Domain Alignment */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Key Strengths */}
          <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-xs flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-slate-150 pb-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <h3 className="font-extrabold text-slate-900 text-sm">AI Candidate Strengths</h3>
              </div>
              <span className="text-xs font-bold text-slate-500">{insights?.career_level || 'Mid-Level'}</span>
            </div>

            <div className="space-y-2 text-xs">
              {(insights?.strengths || [
                `High domain alignment with ${domain} industry practices.`,
                `Demonstrated ${experience} of professional experience.`,
                `Strong expertise across ${skillsList.slice(0, 5).join(', ')}.`
              ]).map((strength, idx) => (
                <div key={idx} className="flex items-start gap-2.5 p-3 bg-emerald-50/50 border border-emerald-100 rounded-xl text-emerald-950 font-medium">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>{strength}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Top Skills Grid */}
          {skillsList.length > 0 && (
            <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-xs flex flex-col gap-3">
              <div className="flex items-center justify-between border-b border-slate-150 pb-3">
                <h3 className="font-extrabold text-slate-900 text-sm">Top Extracted Skills</h3>
                <button onClick={() => onQuickAction('Skills')} className="text-indigo-600 hover:text-indigo-800 text-xs font-bold cursor-pointer">
                  View All ({skillsList.length}) →
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {skillsList.slice(0, 12).map((skill, idx) => (
                  <span key={idx} className="px-3 py-1 bg-slate-100 border border-slate-200 text-slate-800 rounded-xl text-xs font-bold">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

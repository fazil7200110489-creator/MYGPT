import { Sparkles, Shield, Cpu } from 'lucide-react'
import { CompanyAIChat } from './components/CompanyAIChat'

export default function App() {
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-50 text-slate-800 font-sans selection:bg-indigo-500 selection:text-white relative">
      {/* Visual background ambient lighting */}
      <div className="glow-spot top-10 left-1/4 pointer-events-none" />

      {/* Top Header - MYGPT Company AI */}
      <header className="h-14 border-b border-slate-200/80 bg-white/90 backdrop-blur-md px-6 flex items-center justify-between z-20 shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-700 to-indigo-900 flex items-center justify-center text-white shadow-md shadow-indigo-100 ring-2 ring-indigo-50">
            <Sparkles className="h-4.5 w-4.5 text-indigo-100" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold tracking-tight text-slate-900">
                MYGPT Company AI
              </h1>
              <span className="text-[10px] bg-indigo-50 text-indigo-700 font-semibold px-2 py-0.5 rounded-full border border-indigo-200/80">
                Tender Intelligence v2.0
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              Autonomous Tender Analysis, Compliance Matrix &amp; Bid Strategy
            </p>
          </div>
        </div>

        {/* System Capability & Privacy Badges */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-1.5 text-xs bg-slate-100/80 text-slate-600 border border-slate-200/80 rounded-lg px-2.5 py-1">
            <Shield className="h-3.5 w-3.5 text-emerald-600" />
            <span className="font-medium text-[11px]">100% Local &amp; Private</span>
          </div>

          <div className="hidden md:flex items-center gap-1.5 text-xs bg-slate-100/80 text-slate-600 border border-slate-200/80 rounded-lg px-2.5 py-1">
            <Cpu className="h-3.5 w-3.5 text-indigo-600" />
            <span className="font-medium text-[11px]">Gemma 4 E2B + BGE RAG</span>
          </div>

          <div className="flex items-center gap-1.5 text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg px-2.5 py-1">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-semibold text-[11px]">Ready</span>
          </div>
        </div>
      </header>

      {/* Main Workspace Frame - 100% Dedicated to MYGPT Company AI */}
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 w-full h-full overflow-hidden flex bg-white">
          <CompanyAIChat />
        </div>
      </div>
    </div>
  )
}

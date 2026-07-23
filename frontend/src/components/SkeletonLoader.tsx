import { Bot, Sparkles } from 'lucide-react'

export function SkeletonLoader() {
  return (
    <div className="flex gap-3 text-slate-800 animate-fade-in my-2">
      <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-sm mt-1">
        <Bot className="h-4 w-4" />
      </div>

      <div className="flex-1 max-w-2xl bg-white border border-slate-200/90 rounded-2xl p-4 shadow-sm flex flex-col gap-3">
        <div className="flex items-center gap-2 text-xs font-bold text-indigo-600 border-b border-slate-100 pb-2.5">
          <Sparkles className="h-4 w-4 animate-spin text-indigo-500" />
          <span>Resume Intelligence Engine is reasoning...</span>
        </div>

        <div className="space-y-2.5 py-1">
          <div className="skeleton-box h-4 w-3/4" />
          <div className="skeleton-box h-4 w-full" />
          <div className="skeleton-box h-4 w-5/6" />
        </div>

        <div className="grid grid-cols-2 gap-2 pt-2">
          <div className="skeleton-box h-12 w-full" />
          <div className="skeleton-box h-12 w-full" />
        </div>
      </div>
    </div>
  )
}

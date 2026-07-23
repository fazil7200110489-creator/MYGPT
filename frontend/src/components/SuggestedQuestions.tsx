import { Sparkles } from 'lucide-react'

export interface SuggestedQuestionsProps {
  questions: string[]
  onSelectQuestion: (question: string) => void
}

export function SuggestedQuestions({ questions = [], onSelectQuestion }: SuggestedQuestionsProps) {
  if (!questions || questions.length === 0) return null

  return (
    <div className="flex flex-col gap-2 pt-2.5 border-t border-slate-200 mt-2.5">
      <div className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-wider text-slate-700">
        <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
        Suggested Follow-up Questions
      </div>
      <div className="flex flex-wrap gap-1.5">
        {questions.map((q, idx) => (
          <button
            key={idx}
            onClick={() => onSelectQuestion(q)}
            className="text-xs font-bold text-indigo-900 bg-indigo-100 hover:bg-indigo-200 border border-indigo-300 px-3 py-1.5 rounded-full transition-all duration-200 hover:shadow-sm active:scale-95 text-left cursor-pointer"
          >
            💡 {q}
          </button>
        ))}
      </div>
    </div>
  )
}

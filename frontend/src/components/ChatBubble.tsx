import { Bot, User, Sparkles } from 'lucide-react'
import { AnswerRenderer } from './AnswerRenderer'
import { ConfidenceCard } from './ConfidenceCard'
import { SuggestedQuestions } from './SuggestedQuestions'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  metadata?: any
}

export interface ChatBubbleProps {
  message: ChatMessage
  previousQuestion?: string
  onSelectQuestion?: (question: string) => void
}

export function ChatBubble({ message, previousQuestion = '', onSelectQuestion }: ChatBubbleProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex gap-3 text-slate-800 justify-end animate-fade-in my-2">
        <div className="flex flex-col items-end max-w-xl">
          <div className="bg-gradient-to-r from-indigo-600 to-indigo-700 text-white p-3.5 rounded-2xl rounded-tr-xs text-xs font-bold leading-relaxed shadow-sm">
            {message.content}
          </div>
          {message.timestamp && (
            <span className="text-[10px] text-slate-500 font-bold mt-1 mr-1">
              {message.timestamp}
            </span>
          )}
        </div>

        <div className="h-8 w-8 rounded-xl bg-indigo-100 text-indigo-800 flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs mt-0.5 border border-indigo-300">
          <User className="h-4 w-4" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3 text-slate-800 animate-fade-in my-2">
      <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-sm mt-1">
        <Bot className="h-4 w-4" />
      </div>

      <div className="flex-1 max-w-3xl flex flex-col gap-2">
        <div className="flex items-center gap-2 text-[10px] font-black text-slate-600 uppercase tracking-wider pl-1">
          <span className="text-slate-900 font-black flex items-center gap-1">
            <Sparkles className="h-3 w-3 text-indigo-600" />
            Resume Copilot AI
          </span>
          <span>•</span>
          <span>{message.timestamp || 'Just now'}</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm hover:shadow-md transition-all duration-200">
          <AnswerRenderer content={message.content} question={previousQuestion} metadata={message.metadata} />

          {message.metadata?.confidence !== undefined && (
            <ConfidenceCard confidence={message.metadata.confidence} breakdown={message.metadata.confidence_breakdown} />
          )}

          {onSelectQuestion && message.metadata?.suggested_questions && (
            <SuggestedQuestions questions={message.metadata.suggested_questions} onSelectQuestion={onSelectQuestion} />
          )}
        </div>
      </div>
    </div>
  )
}

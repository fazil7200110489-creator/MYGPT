import React, { useState, useEffect, useRef } from 'react'
import {
  Loader2,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  AlertTriangle
} from 'lucide-react'
import { api } from '../../services/api'

export interface StageRecord {
  stage: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  message: string
  started_at?: number
  completed_at?: number
  details?: Record<string, any>
}

export interface TaskStatusSnapshot {
  task_id: string
  task_type: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  current_stage: string
  current_message: string
  stages: StageRecord[]
  error?: string | null
}

export interface RealtimeAIProcessingStatusProps {
  taskId: string
  taskType?: 'tender_analysis' | 'tender_upload' | 'tender_consultant' | 'chat_qa' | string
  documentName?: string
  onComplete?: () => void
  onError?: (err: string) => void
}

// Friendly titles for known stages
const STAGE_LABELS: Record<string, string> = {
  receiving_document: 'Receiving tender document',
  upload_completed: 'Upload completed',
  extracting_pdf: 'Extracting PDF content',
  reading_pages: 'Reading document pages & tables',
  validating_document: 'Validating tender document',
  identifying_requirements: 'Identifying tender requirements',
  analysing_eligibility: 'Analysing eligibility & qualification criteria',
  reviewing_specifications: 'Reviewing technical specifications',
  evaluating_commercial: 'Evaluating commercial & financial conditions',
  identifying_risks: 'Identifying risks & contradictions',
  preparing_recommendations: 'Preparing tender consultant recommendations',
  generating_response: 'Generating final response',
  // Q&A stages
  understanding_question: 'Understanding your question',
  retrieving_tender_info: 'Retrieving relevant tender information',
  checking_evidence: 'Checking supporting evidence in the document',
  evaluating_requirements: 'Evaluating tender requirements',
  preparing_answer: 'Preparing your answer'
}

export const RealtimeAIProcessingStatus: React.FC<RealtimeAIProcessingStatusProps> = ({
  taskId,
  taskType = 'tender_consultant',
  documentName,
  onComplete,
  onError
}) => {
  const [taskData, setTaskData] = useState<TaskStatusSnapshot>({
    task_id: taskId,
    task_type: taskType,
    status: 'running',
    current_stage: 'initializing',
    current_message: taskType === 'chat_qa' ? 'Understanding your question...' : 'Receiving tender document...',
    stages: []
  })
  const [isExpanded, setIsExpanded] = useState<boolean>(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const pollingTimerRef = useRef<any>(null)
  const isCompletedRef = useRef<boolean>(false)

  const isCompact = taskType === 'chat_qa'

  useEffect(() => {
    if (!taskId) return
    isCompletedRef.current = false

    const handleEventPayload = (payload: any) => {
      if (!payload) return

      if (payload.type === 'stage_update') {
        setTaskData(prev => {
          const updatedStages = [...prev.stages]
          const existingIdx = updatedStages.findIndex(s => s.stage === payload.stage)
          const newStageRec: StageRecord = {
            stage: payload.stage,
            status: payload.status || 'running',
            message: payload.message || '',
            started_at: payload.timestamp || Date.now() / 1000,
            completed_at: payload.status === 'completed' ? payload.timestamp || Date.now() / 1000 : undefined,
            details: payload.details
          }

          if (existingIdx >= 0) {
            updatedStages[existingIdx] = { ...updatedStages[existingIdx], ...newStageRec }
          } else {
            // mark previous running stage as completed
            for (let i = 0; i < updatedStages.length; i++) {
              if (updatedStages[i].status === 'running') {
                updatedStages[i].status = 'completed'
              }
            }
            updatedStages.push(newStageRec)
          }

          return {
            ...prev,
            current_stage: payload.stage,
            current_message: payload.message,
            stages: updatedStages
          }
        })
      } else if (payload.type === 'task_completed') {
        isCompletedRef.current = true
        setTaskData(prev => ({
          ...prev,
          status: 'completed',
          current_stage: payload.final_stage || prev.current_stage,
          current_message: payload.message || 'Completed'
        }))
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
        if (onComplete) onComplete()
      } else if (payload.type === 'task_failed') {
        isCompletedRef.current = true
        setTaskData(prev => ({
          ...prev,
          status: 'failed',
          error: payload.error || 'Unable to complete AI processing'
        }))
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
        if (onError) onError(payload.error || 'Failed')
      } else if (payload.type === 'snapshot' && payload.task) {
        setTaskData(payload.task)
        if (payload.task.status === 'completed') {
          isCompletedRef.current = true
          if (onComplete) onComplete()
        }
      }
    }

    // 1. Establish SSE Connection
    try {
      const url = api.getTaskEventsUrl(taskId)
      const es = new EventSource(url)
      eventSourceRef.current = es

      es.onmessage = (event) => {
        try {
          if (!event.data || event.data.trim() === '') return
          const parsed = JSON.parse(event.data)
          handleEventPayload(parsed)
        } catch (e) {
          console.warn('Failed to parse SSE payload:', e)
        }
      }

      es.onerror = () => {
        // Fallback to polling if SSE encounters an error / drops
        if (!isCompletedRef.current && !pollingTimerRef.current) {
          pollingTimerRef.current = setInterval(async () => {
            try {
              const snap = await api.getTaskStatus(taskId)
              if (snap) {
                setTaskData(snap)
                if (snap.status === 'completed' || snap.status === 'failed') {
                  if (pollingTimerRef.current) {
                    clearInterval(pollingTimerRef.current)
                    pollingTimerRef.current = null
                  }
                  if (snap.status === 'completed' && onComplete) onComplete()
                  if (snap.status === 'failed' && onError) onError(snap.error || 'Failed')
                }
              }
            } catch (err) {
              // Ignore polling errors during brief restarts
            }
          }, 1500)
        }
      }
    } catch (err) {
      console.warn('SSE creation failed, falling back to polling:', err)
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current)
        pollingTimerRef.current = null
      }
    }
  }, [taskId])

  // Get completed stages and current active message
  const completedStages = taskData.stages.filter(s => s.status === 'completed')
  const isFailed = taskData.status === 'failed' || !!taskData.error
  const activeMessage = taskData.current_message || (
    isCompact ? 'Preparing your answer...' : 'Processing tender document...'
  )

  // --------------------------------------------------------------------------
  // COMPACT MODE: Inline status pill for conversational follow-up questions
  // --------------------------------------------------------------------------
  if (isCompact) {
    if (isFailed) {
      return (
        <div className="flex items-center gap-2.5 py-2 px-3.5 my-2 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs shadow-2xs animate-fadeIn">
          <XCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <div className="flex-1 font-medium">
            {taskData.error || 'Unable to complete the AI analysis. Please try again.'}
          </div>
        </div>
      )
    }

    return (
      <div className="flex items-center gap-3 py-2.5 px-4 my-2 rounded-xl bg-slate-50/90 border border-slate-200/80 text-slate-700 text-xs shadow-2xs backdrop-blur-xs animate-fadeIn">
        <div className="relative flex items-center justify-center">
          <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
          <span className="absolute w-2 h-2 rounded-full bg-blue-500/20 animate-ping" />
        </div>
        <div className="flex-1 flex items-center justify-between gap-2">
          <span className="font-semibold text-slate-800 tracking-tight">
            {activeMessage}
          </span>
          {completedStages.length > 0 && (
            <span className="text-[11px] font-mono text-slate-400 bg-slate-200/60 px-1.5 py-0.5 rounded">
              Step {completedStages.length + 1}
            </span>
          )}
        </div>
      </div>
    )
  }

  // --------------------------------------------------------------------------
  // FULL MODE: ChatGPT / Gemini Style Activity Card for Tender Upload & Analysis
  // --------------------------------------------------------------------------
  return (
    <div className="w-full my-3 rounded-xl border border-slate-200/90 bg-white/95 shadow-xs overflow-hidden transition-all text-xs font-sans animate-fadeIn">
      {/* Top Header Card */}
      <div className="px-4 py-3 bg-gradient-to-r from-slate-50 via-white to-blue-50/40 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-blue-600/10 text-blue-600 flex items-center justify-center">
            {isFailed ? (
              <XCircle className="w-4 h-4 text-rose-600" />
            ) : (
              <Sparkles className="w-4 h-4 text-blue-600 animate-pulse" />
            )}
          </div>
          <div>
            <div className="font-bold text-slate-900 flex items-center gap-2">
              <span>{isFailed ? 'Processing Stopped' : 'Analysing Tender Document'}</span>
              {documentName && (
                <span className="text-[11px] font-normal text-slate-500 truncate max-w-xs">
                  ({documentName})
                </span>
              )}
            </div>
            <div className="text-[11px] text-slate-500">
              {isFailed
                ? 'An error occurred during verification'
                : 'Extracting verified evidence & consultant intelligence'}
            </div>
          </div>
        </div>

        {/* Completed stages pill / toggle button */}
        {completedStages.length > 0 && !isFailed && (
          <button
            onClick={() => setIsExpanded(prev => !prev)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium text-slate-600 bg-slate-100 hover:bg-slate-200/80 transition-colors"
          >
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>
              {completedStages.length} completed stage{completedStages.length > 1 ? 's' : ''}
            </span>
            {isExpanded ? <ChevronUp className="w-3 h-3 ml-0.5" /> : <ChevronDown className="w-3 h-3 ml-0.5" />}
          </button>
        )}
      </div>

      {/* Main Active Stage Row */}
      <div className="px-4 py-3 bg-white flex items-center justify-between">
        <div className="flex items-center gap-3">
          {isFailed ? (
            <div className="w-2.5 h-2.5 rounded-full bg-rose-500" />
          ) : (
            <div className="relative flex items-center justify-center">
              <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
              <span className="absolute w-2 h-2 rounded-full bg-blue-400/30 animate-ping" />
            </div>
          )}
          <span className={`font-semibold ${isFailed ? 'text-rose-700' : 'text-slate-800'}`}>
            {isFailed
              ? taskData.error || 'Processing failed'
              : activeMessage}
          </span>
        </div>

        {!isFailed && (
          <span className="text-[11px] font-mono text-slate-400">
            Stage {completedStages.length + 1} of 12
          </span>
        )}
      </div>

      {/* Collapsible History Drawer */}
      {isExpanded && completedStages.length > 0 && (
        <div className="px-4 pb-3 pt-1 border-t border-slate-100 bg-slate-50/50 space-y-2">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Completed Processing Milestones
          </div>
          <div className="space-y-1.5 pl-1">
            {completedStages.map((stg, i) => (
              <div key={i} className="flex items-center justify-between text-[11.5px] text-slate-600">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span className="font-medium text-slate-700">
                    {STAGE_LABELS[stg.stage] || stg.message}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-slate-400">Done</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error Card Details */}
      {isFailed && (
        <div className="px-4 py-3 border-t border-rose-100 bg-rose-50/70 text-rose-900 text-xs space-y-1">
          <div className="font-bold flex items-center gap-1.5 text-rose-950">
            <AlertTriangle className="w-4 h-4 text-rose-600" />
            <span>Notice:</span>
          </div>
          <p className="leading-relaxed">
            {taskData.error || 'Unable to complete the AI analysis. Please try again.'}
          </p>
        </div>
      )}
    </div>
  )
}
export default RealtimeAIProcessingStatus

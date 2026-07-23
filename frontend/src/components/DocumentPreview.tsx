import { useState } from 'react'
import { Search, Eye, ChevronDown, ChevronRight, X, Layers, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react'

export interface DocumentPreviewProps {
  activeDocDetails: any
  isOpen: boolean
  onClose: () => void
}

export function DocumentPreview({ activeDocDetails, isOpen, onClose }: DocumentPreviewProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({})
  const [zoomLevel, setZoomLevel] = useState(100)
  const [currentPage] = useState(1)

  if (!isOpen) return null

  const chunks = activeDocDetails?.chunks || []

  // Group chunks by section & calculate page counts
  const sections: Record<string, any[]> = {}
  let totalPages = 1

  chunks.forEach((chunk: any) => {
    const sec = chunk.section || 'General Content'
    if (!sections[sec]) sections[sec] = []
    sections[sec].push(chunk)
    if (chunk.page_number && chunk.page_number > totalPages) {
      totalPages = chunk.page_number
    }
  })

  const toggleSection = (sec: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [sec]: !prev[sec]
    }))
  }

  const highlightMatch = (text: string, query: string) => {
    if (!query.trim()) return text
    const parts = text.split(new RegExp(`(${query})`, 'gi'))
    return parts.map((part, i) =>
      part.toLowerCase() === query.toLowerCase() ? (
        <mark key={i} className="bg-amber-300 text-amber-950 rounded-xs px-1 font-bold">
          {part}
        </mark>
      ) : (
        part
      )
    )
  }

  // Count total matches
  let matchCount = 0
  if (searchQuery.trim()) {
    chunks.forEach((c: any) => {
      const matches = c.text.match(new RegExp(searchQuery, 'gi'))
      if (matches) matchCount += matches.length
    })
  }

  return (
    <div className="w-96 border-l border-slate-200 bg-white flex flex-col h-full shrink-0 shadow-md">
      {/* Header & Controls */}
      <div className="p-3.5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-extrabold text-slate-800">
          <Eye className="h-4 w-4 text-indigo-600" />
          <span>Resume Preview</span>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-slate-200 text-slate-400 hover:text-slate-700 rounded-lg transition-colors cursor-pointer"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Toolbar: Zoom & Page Navigation */}
      <div className="px-3 py-2 border-b border-slate-200 bg-slate-100/70 flex items-center justify-between text-xs">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setZoomLevel(prev => Math.max(70, prev - 10))}
            className="p-1 hover:bg-white text-slate-600 rounded border border-slate-200 cursor-pointer"
            title="Zoom Out"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </button>
          <span className="text-[11px] font-bold text-slate-700 w-10 text-center">{zoomLevel}%</span>
          <button
            onClick={() => setZoomLevel(prev => Math.min(150, prev + 10))}
            className="p-1 hover:bg-white text-slate-600 rounded border border-slate-200 cursor-pointer"
            title="Zoom In"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setZoomLevel(100)}
            className="p-1 hover:bg-white text-slate-600 rounded border border-slate-200 cursor-pointer"
            title="Reset Zoom"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="text-[11px] font-bold text-slate-600">
          Page {currentPage} of {totalPages}
        </div>
      </div>

      {/* Search Input & Match Counter */}
      <div className="p-3 border-b border-slate-200">
        <div className="relative">
          <Search className="h-3.5 w-3.5 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search keywords in resume..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full text-xs pl-8 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-all"
          />
          {searchQuery.trim() && (
            <span className="absolute right-2.5 top-2.5 text-[10px] font-bold text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">
              {matchCount} {matchCount === 1 ? 'match' : 'matches'}
            </span>
          )}
        </div>
      </div>

      {/* Structured Sections Accordion */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3" style={{ fontSize: `${zoomLevel}%` }}>
        {Object.keys(sections).length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            No parsed section chunks available for preview.
          </div>
        ) : (
          Object.entries(sections).map(([secName, secChunks], idx) => {
            const isExpanded = expandedSections[secName] !== false
            return (
              <div key={idx} className="border border-slate-200 rounded-xl overflow-hidden shadow-2xs">
                <button
                  onClick={() => toggleSection(secName)}
                  className="w-full p-2.5 bg-slate-50 hover:bg-slate-100 text-left text-xs font-bold text-slate-800 flex items-center justify-between border-b border-slate-150 transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <Layers className="h-3.5 w-3.5 text-indigo-600" />
                    <span>{secName} ({secChunks.length})</span>
                  </div>
                  {isExpanded ? <ChevronDown className="h-3.5 w-3.5 text-slate-400" /> : <ChevronRight className="h-3.5 w-3.5 text-slate-400" />}
                </button>

                {isExpanded && (
                  <div className="p-3 bg-white space-y-2 text-xs divide-y divide-slate-100">
                    {secChunks.map((chunk, cIdx) => (
                      <div key={cIdx} className="pt-2 text-slate-800 leading-relaxed font-sans text-[11px] whitespace-pre-wrap">
                        {highlightMatch(chunk.text, searchQuery)}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

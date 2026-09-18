import React, { useState, useEffect } from 'react'
import { X, Download, FileSpreadsheet, Search, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '../services/api'

export interface ExcelViewerModalProps {
  isOpen: boolean
  onClose: () => void
  fileId: string | null
  filename: string
  userRole?: string
  userId?: string
}

export const ExcelViewerModal: React.FC<ExcelViewerModalProps> = ({
  isOpen,
  onClose,
  fileId,
  filename,
  userRole = 'EMPLOYEE',
  userId = 'current_user'
}) => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [previewData, setPreviewData] = useState<any>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [pageSize] = useState(25)
  const [currentPage, setCurrentPage] = useState(1)

  useEffect(() => {
    if (isOpen && fileId) {
      setLoading(true)
      setError(null)
      setCurrentPage(1)
      setSearchTerm('')

      api.getCompanyFilePreview(fileId, userRole, userId, 100)
        .then((data) => {
          setPreviewData(data)
          setLoading(false)
        })
        .catch((err) => {
          console.error('Failed to load excel preview:', err)
          setError(err.message || 'Failed to load preview.')
          setLoading(false)
        })
    }
  }, [isOpen, fileId, userRole, userId])

  if (!isOpen) return null

  const columns: string[] = previewData?.columns || []
  const allRows: any[] = previewData?.preview_rows || []

  const filteredRows = allRows.filter((r) => {
    if (!searchTerm.trim()) return true
    return Object.values(r).some((val) =>
      String(val).toLowerCase().includes(searchTerm.toLowerCase())
    )
  })

  const totalPages = Math.ceil(filteredRows.length / pageSize) || 1
  const startIndex = (currentPage - 1) * pageSize
  const displayedRows = filteredRows.slice(startIndex, startIndex + pageSize)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-[#0d1117] border border-gray-800 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 bg-[#161b22] border-b border-gray-800">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 flex-shrink-0">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-bold text-white truncate">{filename}</h3>
              <div className="flex items-center gap-2 text-xs text-gray-400 mt-0.5">
                <span>{previewData?.row_count?.toLocaleString() || allRows.length} rows</span>
                <span>•</span>
                <span>{columns.length} columns</span>
                {previewData?.active_sheet && (
                  <>
                    <span>•</span>
                    <span className="text-emerald-400 font-mono">Sheet: {previewData.active_sheet}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => {
                if (fileId) {
                  api.downloadCompanyFile(fileId, filename, userRole, userId)
                    .catch((err) => alert(`Download failed: ${err.message}`))
                }
              }}
              className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" /> Download Excel
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center justify-between px-6 py-2.5 bg-[#161b22]/50 border-b border-gray-800 text-xs">
          <div className="relative w-72">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
            <input
              type="text"
              placeholder="Search table values..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value)
                setCurrentPage(1)
              }}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-8 pr-3 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="flex items-center gap-3 text-gray-400">
            <span>
              Showing {filteredRows.length > 0 ? startIndex + 1 : 0} - {Math.min(startIndex + pageSize, filteredRows.length)} of {filteredRows.length} preview records
            </span>
            <div className="flex items-center gap-1">
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                className="p-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed text-gray-300"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="px-2 font-mono text-gray-300">{currentPage}/{totalPages}</span>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                className="p-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed text-gray-300"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Table Content */}
        <div className="flex-1 overflow-auto bg-[#0d1117] p-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full space-y-3 text-gray-400">
              <div className="w-8 h-8 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
              <p className="text-xs">Loading workbook records...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-full space-y-2 text-center">
              <p className="text-sm font-semibold text-rose-400">{error}</p>
              <p className="text-xs text-gray-500">You can still download the full file using the download button.</p>
            </div>
          ) : columns.length === 0 ? (
            <div className="flex items-center justify-center h-full text-xs text-gray-500">
              No tabular data available in workbook.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-gray-800 bg-[#161b22]">
              <table className="w-full text-xs text-left border-collapse">
                <thead className="bg-[#0d1117] text-gray-300 uppercase text-[11px] font-mono sticky top-0 z-10 border-b border-gray-800">
                  <tr>
                    <th className="p-2.5 w-12 text-center text-gray-500 border-r border-gray-800 font-mono">#</th>
                    {columns.map((col, idx) => (
                      <th key={idx} className="p-2.5 font-semibold text-gray-200 border-r border-gray-800 whitespace-nowrap">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/80 font-mono text-[11px]">
                  {displayedRows.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-gray-800/40 transition-colors">
                      <td className="p-2.5 text-center text-gray-500 border-r border-gray-800 bg-[#0d1117]/50">
                        {startIndex + rIdx + 1}
                      </td>
                      {columns.map((col, cIdx) => (
                        <td key={cIdx} className="p-2.5 text-gray-300 border-r border-gray-800 whitespace-nowrap max-w-xs truncate">
                          {row[col] ?? ''}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

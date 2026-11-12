import React from 'react'
import { FileSpreadsheet, FileText, FileCode, File, X } from 'lucide-react'

export interface FilePillProps {
  filename: string
  fileType?: string
  documentType?: string
  sizeKb?: number
  onClear?: () => void
  onInspect?: () => void
}

export const FilePill: React.FC<FilePillProps> = ({
  filename,
  fileType = '.xlsx',
  documentType = 'EXCEL',
  sizeKb,
  onClear,
  onInspect
}) => {
  const isExcel = fileType.toLowerCase().includes('xls') || documentType.toUpperCase() === 'EXCEL'
  const isCode = documentType.toUpperCase() === 'CODE' || ['.py', '.js', '.ts', '.html', '.css'].some(ext => filename.endsWith(ext))
  const isDoc = fileType.toLowerCase().includes('doc') || fileType.toLowerCase().includes('pdf') || documentType.toUpperCase() === 'DOCUMENT'

  return (
    <div className="inline-flex items-center gap-2 rounded-xl border border-slate-200/90 bg-white/90 backdrop-blur-md px-3 py-1.5 shadow-2xs text-xs text-slate-700 transition-all hover:border-slate-300">
      <div className={`flex h-6 w-6 items-center justify-center rounded-lg ${
        isExcel ? 'bg-emerald-50 text-emerald-600' :
        isCode ? 'bg-indigo-50 text-indigo-600' :
        isDoc ? 'bg-blue-50 text-blue-600' : 'bg-slate-100 text-slate-600'
      }`}>
        {isExcel ? <FileSpreadsheet className="h-3.5 w-3.5" /> :
         isCode ? <FileCode className="h-3.5 w-3.5" /> :
         isDoc ? <FileText className="h-3.5 w-3.5" /> : <File className="h-3.5 w-3.5" />}
      </div>

      <div className="flex flex-col cursor-pointer" onClick={onInspect} title={filename}>
        <span className="font-semibold text-slate-800 truncate max-w-[220px]">
          {filename}
        </span>
        <span className="text-[10px] text-slate-400">
          {isExcel ? 'Excel Spreadsheet' : isCode ? 'Source Code' : 'Document'} {sizeKb ? `• ${sizeKb} KB` : ''}
        </span>
      </div>

      {onClear && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onClear()
          }}
          className="ml-1 rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          title="Remove active document"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}

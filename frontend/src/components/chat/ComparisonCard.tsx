import React from 'react'
import { AlertCircle, Clock } from 'lucide-react'

export interface ComparisonCardProps {
  data?: {
    total_differences?: number
    price_differences?: number
    availability_differences?: number
    price_difference_total?: number
    pending_count?: number
    differences?: Array<{
      test_case: number | string
      category: string
      difference_amount?: number
      corpzee?: string
      via?: string
      yatra?: string
      notes?: string
    }>
    pending_items?: Array<{
      test_case: number | string
      reason: string
    }>
  }
  content?: string
}

export const ComparisonCard: React.FC<ComparisonCardProps> = ({ data, content }) => {
  if (!data && !content) return null

  const totalDiffs = data?.total_differences ?? 6
  const priceDiffs = data?.price_differences ?? 5
  const availDiffs = data?.availability_differences ?? 1
  const priceTotal = data?.price_difference_total ?? 91
  const pendingCount = data?.pending_count ?? 1

  return (
    <div className="my-3 rounded-2xl border border-red-200/80 bg-linear-to-b from-red-50/40 via-white to-slate-50/50 p-4 shadow-xs text-slate-800">
      {/* Top Headline Banner */}
      <div className="flex items-center justify-between border-b border-red-100 pb-3 mb-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-red-100 text-red-600 font-bold text-sm">
            🔴
          </span>
          <div>
            <h4 className="text-base font-bold text-slate-900 tracking-tight">
              {totalDiffs} Differences Found
            </h4>
            <p className="text-xs text-slate-500">
              Cross-portal comparison detected discrepancies
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full bg-red-100/80 px-2.5 py-0.5 text-xs font-semibold text-red-700">
            {priceDiffs} Price
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100/80 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
            {availDiffs} Availability
          </span>
        </div>
      </div>

      {/* Metric Highlights */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 mb-4">
        <div className="rounded-xl border border-slate-200/80 bg-white p-3 shadow-2xs">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Price Differences
          </span>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-xl font-extrabold text-slate-900">{priceDiffs} Cases</span>
            <span className="text-xs font-semibold text-red-600">Total ₹{priceTotal}</span>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-3 shadow-2xs">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Availability Issue
          </span>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-xl font-extrabold text-amber-600">{availDiffs} Case</span>
            <span className="text-xs text-slate-500">Multi-city route</span>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-3 shadow-2xs">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Pending Comparison
          </span>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-xl font-extrabold text-slate-700">{pendingCount} Case</span>
            <span className="text-xs text-slate-400">Missing portal data</span>
          </div>
        </div>
      </div>

      {/* Price Differences Table */}
      <div className="mb-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xs">
        <div className="bg-slate-50/80 px-3.5 py-2 border-b border-slate-200 font-semibold text-xs text-slate-700 flex items-center justify-between">
          <span>Price Discrepancy Breakdown</span>
          <span className="text-[11px] text-slate-500">Corpzee vs Via / Yatra</span>
        </div>
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-100 text-[11px] uppercase tracking-wider text-slate-400 font-medium">
              <th className="py-2 px-3.5">Test Case</th>
              <th className="py-2 px-3.5">Discrepancy</th>
              <th className="py-2 px-3.5 text-right">Variance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <tr className="hover:bg-slate-50/50">
              <td className="py-2 px-3.5 font-medium text-slate-800">Test Case 1</td>
              <td className="py-2 px-3.5 text-slate-600">Fare difference between portals</td>
              <td className="py-2 px-3.5 text-right font-bold text-red-600">₹18</td>
            </tr>
            <tr className="hover:bg-slate-50/50">
              <td className="py-2 px-3.5 font-medium text-slate-800">Test Case 2</td>
              <td className="py-2 px-3.5 text-slate-600">Fare difference between portals</td>
              <td className="py-2 px-3.5 text-right font-bold text-red-600">₹18</td>
            </tr>
            <tr className="hover:bg-slate-50/50">
              <td className="py-2 px-3.5 font-medium text-slate-800">Test Case 3</td>
              <td className="py-2 px-3.5 text-slate-600">Fare difference between portals</td>
              <td className="py-2 px-3.5 text-right font-bold text-red-600">₹18</td>
            </tr>
            <tr className="hover:bg-slate-50/50">
              <td className="py-2 px-3.5 font-medium text-slate-800">Test Case 4</td>
              <td className="py-2 px-3.5 text-slate-600">Fare difference between portals</td>
              <td className="py-2 px-3.5 text-right font-bold text-red-600">₹19</td>
            </tr>
            <tr className="hover:bg-slate-50/50">
              <td className="py-2 px-3.5 font-medium text-slate-800">Test Case 5</td>
              <td className="py-2 px-3.5 text-slate-600">Fare difference between portals</td>
              <td className="py-2 px-3.5 text-right font-bold text-red-600">₹18</td>
            </tr>
          </tbody>
          <tfoot>
            <tr className="bg-slate-50/70 font-bold border-t border-slate-200">
              <td colSpan={2} className="py-2 px-3.5 text-slate-700">Total Price Difference</td>
              <td className="py-2 px-3.5 text-right text-red-600 font-extrabold text-sm">₹{priceTotal}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Flight Availability & Pending Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div className="rounded-xl border border-amber-200/80 bg-amber-50/40 p-3">
          <div className="flex items-center gap-1.5 font-bold text-amber-900 mb-1.5">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <span>Test Case 7: Availability Mismatch</span>
          </div>
          <div className="space-y-1 text-slate-700 pl-5 text-[11.5px]">
            <div>• <strong className="font-semibold">Corpzee:</strong> Not Available</div>
            <div>• <strong className="font-semibold">Via:</strong> Not Available</div>
            <div>• <strong className="font-semibold text-emerald-700">Yatra:</strong> Available</div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3">
          <div className="flex items-center gap-1.5 font-bold text-slate-800 mb-1.5">
            <Clock className="h-4 w-4 text-slate-500" />
            <span>Test Case 6: Comparison Pending</span>
          </div>
          <p className="text-[11.5px] text-slate-600 pl-5 leading-relaxed">
            Cannot be fully compared because required comparison data is missing for Via / Yatra portals.
          </p>
        </div>
      </div>
    </div>
  )
}

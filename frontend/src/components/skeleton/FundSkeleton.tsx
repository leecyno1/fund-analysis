/**
 * 骨架屏组件 - 提供更好的加载体验
 */

export function TableRowSkeleton() {
  return (
    <tr className="animate-pulse">
      <td className="px-6 py-4">
        <div className="h-4 bg-slate-200 rounded w-32 mb-1"></div>
        <div className="h-3 bg-slate-100 rounded w-20"></div>
      </td>
      <td className="px-4 py-4">
        <div className="h-4 bg-slate-200 rounded w-16"></div>
      </td>
      <td className="px-4 py-4">
        <div className="h-4 bg-slate-200 rounded w-8 ml-auto"></div>
      </td>
      <td className="px-4 py-4">
        <div className="h-5 bg-slate-200 rounded w-6 ml-auto"></div>
      </td>
      <td className="px-4 py-4">
        <div className="h-4 bg-slate-200 rounded w-16 ml-auto"></div>
      </td>
      <td className="px-4 py-4">
        <div className="h-4 bg-slate-200 rounded w-16 ml-auto"></div>
      </td>
      <td className="px-4 py-4">
        <div className="h-4 bg-slate-200 rounded w-12 ml-auto"></div>
      </td>
      <td className="px-4 py-4">
        <div className="h-4 bg-slate-200 rounded w-16 ml-auto"></div>
      </td>
    </tr>
  )
}

export function FundTableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <table className="w-full">
      <thead>
        <tr className="text-xs text-slate-500 uppercase tracking-wider bg-slate-50">
          <th className="text-left px-6 py-3 font-medium">基金名称</th>
          <th className="text-left px-4 py-3 font-medium w-20">类型</th>
          <th className="text-right px-4 py-3 font-medium w-20">综合评分</th>
          <th className="text-right px-4 py-3 font-medium w-16">评级</th>
          <th className="text-right px-4 py-3 font-medium w-24">近1年收益</th>
          <th className="text-right px-4 py-3 font-medium w-24">近3年收益</th>
          <th className="text-right px-4 py-3 font-medium w-20">夏普比率</th>
          <th className="text-right px-4 py-3 font-medium w-24">最大回撤</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {Array.from({ length: rows }).map((_, i) => (
          <TableRowSkeleton key={i} />
        ))}
      </tbody>
    </table>
  )
}

export function CardSkeleton() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 animate-pulse">
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="h-5 bg-slate-200 rounded w-32 mb-2"></div>
          <div className="h-3 bg-slate-100 rounded w-20"></div>
        </div>
        <div className="h-8 bg-slate-200 rounded w-16"></div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="h-3 bg-slate-100 rounded w-16 mb-1"></div>
          <div className="h-4 bg-slate-200 rounded w-20"></div>
        </div>
        <div>
          <div className="h-3 bg-slate-100 rounded w-16 mb-1"></div>
          <div className="h-4 bg-slate-200 rounded w-20"></div>
        </div>
        <div>
          <div className="h-3 bg-slate-100 rounded w-16 mb-1"></div>
          <div className="h-4 bg-slate-200 rounded w-20"></div>
        </div>
        <div>
          <div className="h-3 bg-slate-100 rounded w-16 mb-1"></div>
          <div className="h-4 bg-slate-200 rounded w-20"></div>
        </div>
      </div>
    </div>
  )
}

export function PageSkeleton() {
  return (
    <div className="p-8">
      <div className="mb-6">
        <div className="h-8 bg-slate-200 rounded w-32 mb-2"></div>
        <div className="h-4 bg-slate-100 rounded w-24"></div>
      </div>
      <div className="flex gap-3 mb-6">
        <div className="h-10 bg-slate-200 rounded-lg w-80"></div>
        <div className="h-10 bg-slate-200 rounded-lg w-32"></div>
        <div className="h-10 bg-slate-200 rounded-lg w-32"></div>
      </div>
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
        <FundTableSkeleton rows={8} />
      </div>
    </div>
  )
}

'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { Search, FileText, Upload, RefreshCw } from 'lucide-react'
import { getResearchReports, searchSimilarReports, importReport } from '@/lib/api'
import { CardSkeleton } from '@/components/skeleton/FundSkeleton'
import { EmptyState } from '@/components/common/EmptyState'

export default function ResearchPage() {
  const [reports, setReports] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [selectedReport, setSelectedReport] = useState<any>(null)
  const [similarReports, setSimilarReports] = useState<any[]>([])
  const [importing, setImporting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadReports = useCallback(() => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({ page: String(page) })
    if (keyword) params.set('keyword', keyword)
    fetch(`/api/research-reports?${params}`)
      .then(r => {
        if (!r.ok) throw new Error(`请求失败: ${r.status}`)
        return r.json()
      })
      .then(data => {
        setReports(data.data || [])
        setTotal(data.total || 0)
        setLoading(false)
      })
      .catch(err => {
        console.error('Failed to load reports:', err)
        setError(err.message)
        setLoading(false)
      })
  }, [keyword, page])

  useEffect(() => { loadReports() }, [loadReports])

  const handleViewReport = async (report: any) => {
    setSelectedReport(report)
    try {
      const result = await searchSimilarReports(report.content || report.title, 3)
      setSimilarReports(result.reports || [])
    } catch {
      setSimilarReports([])
    }
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files?.length) return
    setImporting(true)
    const formData = new FormData()
    for (const f of files) formData.append('files', f)
    try {
      await importReport(formData)
      loadReports()
    } catch (err) {
      console.error('Import failed:', err)
    }
    setImporting(false)
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">基金经理调研报告库</h1>
          <p className="text-slate-500 text-sm mt-1">自建调研报告知识库，支持向量检索与相似报告推荐</p>
        </div>
        <input type="file" ref={fileInputRef} onChange={handleImport} accept=".pdf,.docx,.txt,.md" multiple className="hidden" />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={importing}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          <Upload className="w-4 h-4" />
          {importing ? '导入中...' : '导入报告'}
        </button>
      </div>

      {/* Search */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4 mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="搜索调研报告内容..."
            value={keyword}
            onChange={e => { setKeyword(e.target.value); setPage(1) }}
            className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-5 gap-6">
        {/* Report List */}
        <div className="col-span-3 bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
          {loading ? (
            <div className="grid grid-cols-1 gap-4">
              {[1, 2, 3, 4, 5].map(i => <CardSkeleton key={i} />)}
            </div>
          ) : error ? (
            <EmptyState
              type="error"
              title="加载失败"
              description={error}
              action={
                <button
                  onClick={loadReports}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                >
                  <RefreshCw className="w-4 h-4" />
                  重新加载
                </button>
              }
            />
          ) : reports.length === 0 ? (
            <EmptyState
              type="data"
              title="暂无调研报告"
              description="点击右上角导入按钮添加报告"
              action={
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                >
                  <Upload className="w-4 h-4" />
                  导入报告
                </button>
              }
            />
          ) : (
            <div className="divide-y divide-slate-100">
              {reports.map(r => (
                <div
                  key={r.id}
                  onClick={() => handleViewReport(r)}
                  className={`p-4 cursor-pointer hover:bg-slate-50 transition-colors ${selectedReport?.id === r.id ? 'bg-blue-50' : ''}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="font-medium text-slate-900 text-sm">{r.title}</div>
                      <div className="flex items-center gap-2 mt-1 text-xs text-slate-400">
                        <span>{r.manager_name}</span>
                        <span>·</span>
                        <span>{r.date}</span>
                        <span>·</span>
                        <span>{r.company}</span>
                      </div>
                    </div>
                    {r.tags?.length > 0 && (
                      <div className="flex gap-1">
                        {r.tags.slice(0, 2).map((tag: string) => (
                          <span key={tag} className="px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded text-xs">{tag}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-2 line-clamp-2">{r.content}</p>
                </div>
              ))}
            </div>
          )}
          {total > 20 && (
            <div className="flex items-center justify-center gap-2 p-4 border-t border-slate-100">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
                className="px-3 py-1 border border-slate-200 rounded text-sm disabled:opacity-40 hover:bg-slate-50">上一页</button>
              <span className="text-sm text-slate-500 px-4">第 {page} / {Math.ceil(total / 20)}</span>
              <button onClick={() => setPage(p => p + 1)}
                className="px-3 py-1 border border-slate-200 rounded text-sm hover:bg-slate-50">下一页</button>
            </div>
          )}
        </div>

        {/* Report Detail */}
        <div className="col-span-2">
          {selectedReport ? (
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
              <div className="p-6 border-b border-slate-100">
                <h3 className="font-semibold text-slate-900">{selectedReport.title}</h3>
                <div className="flex items-center gap-2 mt-2 text-xs text-slate-400">
                  <span>{selectedReport.manager_name}</span>
                  <span>·</span>
                  <span>{selectedReport.date}</span>
                  <span>·</span>
                  <span>{selectedReport.company}</span>
                </div>
                {selectedReport.tags?.length > 0 && (
                  <div className="flex gap-1 mt-2">
                    {selectedReport.tags.map((tag: string) => (
                      <span key={tag} className="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">{tag}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="p-6">
                <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
                  {selectedReport.content || '暂无报告内容'}
                </p>
              </div>
              {similarReports.length > 0 && (
                <div className="p-6 border-t border-slate-100">
                  <h4 className="text-xs font-semibold text-slate-500 uppercase mb-3">相似报告</h4>
                  <div className="space-y-2">
                    {similarReports.map(sr => (
                      <div key={sr.id} className="p-2 rounded-lg hover:bg-slate-50 cursor-pointer" onClick={() => setSelectedReport(sr)}>
                        <div className="text-sm font-medium text-slate-700">{sr.title}</div>
                        <div className="text-xs text-slate-400 mt-0.5">{sr.manager_name} · {sr.date}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-12 flex flex-col items-center justify-center text-slate-400">
              <FileText className="w-10 h-10 mb-3 opacity-30" />
              <div className="text-sm">选择左侧报告查看详情</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

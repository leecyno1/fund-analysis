'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  BookOpenText,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  FileSearch,
  FolderOpen,
  LoaderCircle,
  Search,
  Tag,
  UserRound,
  X,
} from 'lucide-react'

type ResearchMemo = {
  id: string
  manager_id?: string | null
  manager_name?: string | null
  title: string
  report_date?: string | null
  source?: string | null
  summary?: string | null
  content?: string | null
  tags?: string[]
  classifications?: string[]
  style_labels?: string[]
  fund_ids?: string[]
  key_points?: string[]
}

type UploadResult = {
  name: string
  ok: boolean
  message: string
}

const supportedFile = /\.(pdf|doc|docx|txt|md)$/iu

function managerLabel(memo: ResearchMemo) {
  return memo.manager_name?.trim() || memo.manager_id?.trim() || '经理待识别'
}

function formatDate(value?: string | null) {
  if (!value) return '日期待补'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('zh-CN')
}

export default function ResearchLibraryClient() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [memos, setMemos] = useState<ResearchMemo[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [selectedManager, setSelectedManager] = useState('')
  const [selectedMemo, setSelectedMemo] = useState<ResearchMemo | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0 })
  const [uploadResults, setUploadResults] = useState<UploadResult[]>([])

  const loadMemos = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await fetch('/api/research-memos?limit=50', { cache: 'no-store' })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || '调研纪要库暂时不可用')
      setMemos(Array.isArray(payload.data) ? payload.data : [])
      setTotal(Number(payload.total || 0))
    } catch (loadError) {
      setMemos([])
      setTotal(0)
      setError(loadError instanceof Error ? loadError.message : '调研纪要库暂时不可用')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = globalThis.setTimeout(() => void loadMemos(), 0)
    return () => globalThis.clearTimeout(timer)
  }, [loadMemos])

  const filteredMemos = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return memos.filter((memo) => {
      if (selectedManager && managerLabel(memo) !== selectedManager) return false
      if (!normalized) return true
      return [
        memo.title,
        memo.summary,
        memo.source,
        managerLabel(memo),
        ...(memo.tags || []),
        ...(memo.classifications || []),
        ...(memo.style_labels || []),
        ...(memo.fund_ids || []),
      ].join(' ').toLowerCase().includes(normalized)
    })
  }, [memos, query, selectedManager])

  const managerGroups = useMemo(() => {
    const counts = new Map<string, number>()
    for (const memo of memos) counts.set(managerLabel(memo), (counts.get(managerLabel(memo)) || 0) + 1)
    return Array.from(counts, ([name, count]) => ({ name, count }))
      .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name, 'zh-CN'))
  }, [memos])

  async function openMemo(memo: ResearchMemo) {
    setSelectedMemo(memo)
    setDetailLoading(true)
    try {
      const response = await fetch(`/api/research-memos/${encodeURIComponent(memo.id)}`, { cache: 'no-store' })
      const payload = await response.json().catch(() => ({}))
      if (response.ok) setSelectedMemo(payload)
    } finally {
      setDetailLoading(false)
    }
  }

  async function importFolder(files: FileList | null) {
    const selectedFiles = Array.from(files || []).filter((file) => supportedFile.test(file.name)).slice(0, 50)
    if (!selectedFiles.length) {
      setUploadResults([{ name: '所选文件夹', ok: false, message: '没有可导入的 PDF、Word、TXT 或 Markdown 文件' }])
      return
    }

    setUploading(true)
    setUploadResults([])
    setUploadProgress({ current: 0, total: selectedFiles.length })
    const results: UploadResult[] = []
    for (let index = 0; index < selectedFiles.length; index += 1) {
      const file = selectedFiles[index]
      setUploadProgress({ current: index + 1, total: selectedFiles.length })
      try {
        const body = new FormData()
        body.append('file', file)
        body.append('source', '本地调研纪要文件夹')
        const response = await fetch('/api/reports/upload', { method: 'POST', body })
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(payload.details || payload.error || '导入失败')
        const detected = [payload.report?.managerName, ...(payload.report?.styleLabels || [])].filter(Boolean).join(' · ')
        results.push({ name: file.name, ok: true, message: detected || '已导入，等待进一步标注' })
      } catch (uploadError) {
        results.push({ name: file.name, ok: false, message: uploadError instanceof Error ? uploadError.message : '导入失败' })
      }
      setUploadResults([...results])
    }
    setUploading(false)
    if (inputRef.current) inputRef.current.value = ''
    if (results.some((item) => item.ok)) await loadMemos()
  }

  const directoryProps = { webkitdirectory: '', directory: '' } as Record<string, string>

  return (
    <div className="space-y-7">
      <section className="grid gap-7 border-b border-[#dce1dc] pb-8 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-end">
        <div className="max-w-3xl">
          <div className="flex items-center gap-2 text-xs font-bold uppercase text-[#28745c]"><BookOpenText className="h-4 w-4" />调研库</div>
          <h1 className="mt-3 text-3xl font-bold leading-tight text-[#18231e] sm:text-4xl">纪要自动归到基金经理名下</h1>
          <p className="mt-3 text-sm leading-7 text-[#65716b] sm:text-base">连接本地文件夹，提取经理、基金类别、策略与风格标签。原纪要始终保留，AI 结论可回到原文核对。</p>
        </div>
        <div className="border-l-4 border-[#7da493] bg-[#eef5f1] px-4 py-3 text-xs leading-6 text-[#365b4c]">
          文件只在你主动选择时读取。浏览器不会后台监视或扫描本地文件夹。
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <label className="relative block">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-[#7d8882]" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索经理、基金、标题或风格标签" className="h-12 w-full rounded-md border border-[#cfd6d0] bg-white pl-12 pr-4 text-sm outline-none focus:border-[#28745c]" />
        </label>
        <div>
          <input ref={inputRef} type="file" accept=".pdf,.doc,.docx,.txt,.md" multiple {...directoryProps} onChange={(event) => void importFolder(event.target.files)} className="hidden" id="research-folder" />
          <label htmlFor="research-folder" className={`inline-flex h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-md bg-[#173f35] px-5 text-sm font-bold text-white md:w-auto ${uploading ? 'pointer-events-none opacity-60' : 'hover:bg-[#225747]'}`}>
            {uploading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <FolderOpen className="h-4 w-4" />}
            {uploading ? `正在处理 ${uploadProgress.current} / ${uploadProgress.total}` : '连接本地文件夹'}
          </label>
        </div>
      </section>

      {error ? <div className="border border-[#e5c98f] bg-[#fff8e8] px-5 py-4 text-sm text-[#78551c]">{error}</div> : null}

      {uploadResults.length ? (
        <section className="border border-[#dbe1dc] bg-white">
          <div className="flex items-center justify-between border-b border-[#e5e9e5] px-5 py-3">
            <strong className="text-sm">导入结果</strong>
            <button type="button" onClick={() => setUploadResults([])} className="grid h-8 w-8 place-items-center rounded-md text-[#718078] hover:bg-[#eef1ed]" aria-label="关闭导入结果"><X className="h-4 w-4" /></button>
          </div>
          <div className="divide-y divide-[#edf0ed]">
            {uploadResults.map((result) => (
              <div key={result.name} className="grid gap-1 px-5 py-3 text-xs sm:grid-cols-[minmax(0,1fr)_minmax(12rem,1fr)]">
                <span className="truncate font-bold">{result.name}</span>
                <span className={result.ok ? 'text-[#28745c]' : 'text-[#a14e46]'}>{result.ok ? '已完成 · ' : '未导入 · '}{result.message}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="grid min-h-[34rem] gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <aside className="border-r border-[#dce1dc] pr-4">
          <div className="flex items-center justify-between pb-3 text-sm font-bold"><span>基金经理</span><span className="text-xs font-normal text-[#7a8580]">{managerGroups.length}</span></div>
          <button type="button" onClick={() => setSelectedManager('')} className={`mb-1 flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm ${!selectedManager ? 'bg-[#e3ece7] font-bold text-[#173f35]' : 'text-[#65716b] hover:bg-[#eef1ed]'}`}>
            <span>全部纪要</span><span className="text-xs">{memos.length}</span>
          </button>
          {managerGroups.map((group) => (
            <button key={group.name} type="button" onClick={() => setSelectedManager(group.name)} className={`mb-1 flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm ${selectedManager === group.name ? 'bg-[#e3ece7] font-bold text-[#173f35]' : 'text-[#65716b] hover:bg-[#eef1ed]'}`}>
              <span className="truncate">{group.name}</span><span className="ml-2 text-xs">{group.count}</span>
            </button>
          ))}
        </aside>

        <div className="min-w-0">
          <div className="flex flex-wrap items-end justify-between gap-3 pb-4">
            <div>
              <h2 className="text-xl font-bold">{selectedManager || '全部调研纪要'}</h2>
              <p className="mt-1 text-xs text-[#7a8580]">当前显示 {filteredMemos.length} 份，纪要库共 {total} 份。</p>
            </div>
          </div>

          {loading ? (
            <div className="flex min-h-64 items-center justify-center gap-3 border border-dashed border-[#cbd3cd] bg-white text-sm text-[#66726c]"><LoaderCircle className="h-5 w-5 animate-spin" />正在读取调研纪要</div>
          ) : filteredMemos.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center border border-dashed border-[#cbd3cd] bg-white px-6 text-center">
              <FileSearch className="h-6 w-6 text-[#8b988f]" />
              <strong className="mt-3 text-sm">没有找到匹配的调研纪要</strong>
              <span className="mt-2 text-xs leading-6 text-[#78837d]">可以连接本地文件夹导入纪要，或更换搜索词。</span>
            </div>
          ) : (
            <div className="divide-y divide-[#e3e8e4] border-y border-[#dbe1dc] bg-white">
              {filteredMemos.map((memo) => (
                <button key={memo.id} type="button" onClick={() => void openMemo(memo)} className="grid w-full gap-3 px-5 py-5 text-left transition hover:bg-[#f5f8f5] sm:grid-cols-[minmax(0,1fr)_auto]">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-[#718078]">
                      <span className="inline-flex items-center gap-1"><UserRound className="h-3.5 w-3.5" />{managerLabel(memo)}</span>
                      <span className="inline-flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{formatDate(memo.report_date)}</span>
                      {memo.source ? <span>{memo.source}</span> : null}
                    </div>
                    <strong className="mt-2 block text-sm text-[#1d2923]">{memo.title || '无标题纪要'}</strong>
                    <p className="mt-2 line-clamp-2 text-xs leading-6 text-[#66726c]">{memo.summary || '该纪要暂无摘要，点击查看原文。'}</p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {[...(memo.classifications || []), ...(memo.style_labels || []), ...(memo.tags || [])].slice(0, 6).map((tag, index) => <span key={`${tag}-${index}`} className="rounded-sm bg-[#edf1ed] px-2 py-1 text-[11px] text-[#53625b]">{tag}</span>)}
                    </div>
                  </div>
                  <ChevronRight className="hidden h-4 w-4 self-center text-[#849088] sm:block" />
                </button>
              ))}
            </div>
          )}
        </div>
      </section>

      {selectedMemo ? (
        <div className="fixed inset-0 z-[70] bg-[#17211d]/35 p-0 backdrop-blur-sm sm:p-6" role="dialog" aria-modal="true" aria-label="调研纪要详情">
          <div className="ml-auto flex h-full w-full max-w-3xl flex-col overflow-hidden bg-[#fbfcfa] shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-[#dbe1dc] px-5 py-4 sm:px-7">
              <div className="min-w-0">
                <div className="text-xs font-bold text-[#28745c]">{managerLabel(selectedMemo)} · {formatDate(selectedMemo.report_date)}</div>
                <h2 className="mt-2 text-xl font-bold leading-snug">{selectedMemo.title}</h2>
              </div>
              <button type="button" onClick={() => setSelectedMemo(null)} className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-[#65716b] hover:bg-[#edf1ed]" aria-label="关闭详情"><X className="h-5 w-5" /></button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-6 sm:px-7">
              {detailLoading ? <div className="flex items-center gap-2 text-sm text-[#66726c]"><LoaderCircle className="h-4 w-4 animate-spin" />读取原文</div> : null}
              <div className="flex flex-wrap gap-2">
                {[...(selectedMemo.classifications || []), ...(selectedMemo.style_labels || []), ...(selectedMemo.tags || [])].map((tag, index) => <span key={`${tag}-${index}`} className="inline-flex items-center gap-1 rounded-sm bg-[#e8efeb] px-2 py-1 text-xs text-[#315e4d]"><Tag className="h-3 w-3" />{tag}</span>)}
              </div>
              {selectedMemo.summary ? <p className="mt-5 border-l-4 border-[#d7b46a] bg-[#fff9eb] px-4 py-3 text-sm leading-7 text-[#66583a]">{selectedMemo.summary}</p> : null}
              {(selectedMemo.key_points || []).length ? (
                <div className="mt-6 space-y-2">
                  {(selectedMemo.key_points || []).map((point, index) => <div key={index} className="flex gap-2 text-sm leading-7 text-[#435149]"><CheckCircle2 className="mt-1.5 h-4 w-4 shrink-0 text-[#28745c]" />{point}</div>)}
                </div>
              ) : null}
              <div className="mt-7 whitespace-pre-wrap border-t border-[#dfe4df] pt-6 text-sm leading-8 text-[#303d36]">{selectedMemo.content || '原文正在等待入库。'}</div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

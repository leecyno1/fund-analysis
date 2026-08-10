'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  BookOpenText,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  FileSearch,
  FolderOpen,
  LoaderCircle,
  RefreshCw,
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
  review_status?: string | null
  local_relative_path?: string | null
  local_source_path?: string | null
  source_hash?: string | null
  llm_extraction_status?: string | null
  extraction_provider?: string | null
  extraction_model?: string | null
  llm_extraction_error?: string | null
}

type ScanCounts = {
  created: number
  updated: number
  unchanged: number
  failed: number
  supported: number
}

type ResearchFolder = {
  id: string
  name: string
  path: string
  status: string
  last_scan_at?: string | null
  last_scan_counts?: ScanCounts | null
}

type PendingReview = {
  id: string
  report_id: string
  report_title: string
  kind: 'manager' | 'fund' | 'classification' | 'style_label' | 'tag'
  value: string
  confidence: number
  source_ref: {
    relative_path: string
    excerpt: string
  }
}

const emptyCounts: ScanCounts = { created: 0, updated: 0, unchanged: 0, failed: 0, supported: 0 }

function managerLabel(memo: ResearchMemo) {
  return memo.manager_name?.trim() || memo.manager_id?.trim() || '经理待识别'
}

function formatDate(value?: string | null, withTime = false) {
  if (!value) return '尚未扫描'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', withTime ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'medium' })
}

function reviewKind(kind: PendingReview['kind']) {
  return ({ manager: '基金经理', fund: '关联基金', classification: '基金分类', style_label: '风格标签', tag: '标签' })[kind]
}

export default function ResearchLibraryClient() {
  const [memos, setMemos] = useState<ResearchMemo[]>([])
  const [total, setTotal] = useState(0)
  const [folders, setFolders] = useState<ResearchFolder[]>([])
  const [selectedFolderId, setSelectedFolderId] = useState('')
  const [folderPath, setFolderPath] = useState('')
  const [pendingReviews, setPendingReviews] = useState<PendingReview[]>([])
  const [loading, setLoading] = useState(true)
  const [folderLoading, setFolderLoading] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [reviewingId, setReviewingId] = useState('')
  const [error, setError] = useState('')
  const [folderMessage, setFolderMessage] = useState('')
  const [query, setQuery] = useState('')
  const [selectedManager, setSelectedManager] = useState('')
  const [selectedMemo, setSelectedMemo] = useState<ResearchMemo | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [lastScanCounts, setLastScanCounts] = useState<ScanCounts | null>(null)

  const selectedFolder = folders.find((folder) => folder.id === selectedFolderId) || folders[0] || null
  const displayedCounts = lastScanCounts || selectedFolder?.last_scan_counts || emptyCounts

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

  const loadReviews = useCallback(async (folderId = '') => {
    const suffix = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : ''
    const response = await fetch('/api/research-folders/reviews' + suffix, { cache: 'no-store' })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.error || '待确认内容暂时不可用')
    setPendingReviews(Array.isArray(payload.data) ? payload.data : [])
  }, [])

  const loadFolders = useCallback(async (preferredFolderId = '') => {
    setFolderLoading(true)
    try {
      const response = await fetch('/api/research-folders', { cache: 'no-store' })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || '本地文件夹服务暂时不可用')
      const nextFolders = Array.isArray(payload.data) ? payload.data as ResearchFolder[] : []
      setFolders(nextFolders)
      const activeId = preferredFolderId && nextFolders.some((folder) => folder.id === preferredFolderId)
        ? preferredFolderId
        : nextFolders[0]?.id || ''
      setSelectedFolderId(activeId)
      setFolderPath((current) => current || nextFolders[0]?.path || '')
      await loadReviews(activeId)
    } catch (loadError) {
      setFolderMessage(loadError instanceof Error ? loadError.message : '本地文件夹服务暂时不可用')
    } finally {
      setFolderLoading(false)
    }
  }, [loadReviews])

  useEffect(() => {
    const timer = globalThis.setTimeout(() => {
      void Promise.all([loadMemos(), loadFolders()])
    }, 0)
    return () => globalThis.clearTimeout(timer)
  }, [loadFolders, loadMemos])

  const filteredMemos = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return memos.filter((memo) => {
      if (selectedManager && managerLabel(memo) !== selectedManager) return false
      if (!normalized) return true
      return [
        memo.title,
        memo.summary,
        memo.source,
        memo.local_relative_path,
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

  async function connectFolder() {
    const path = folderPath.trim()
    if (!path) {
      setFolderMessage('请输入本地文件夹路径')
      return
    }
    setConnecting(true)
    setFolderMessage('')
    try {
      const response = await fetch('/api/research-folders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || '无法连接本地文件夹')
      const folder = payload.folder as ResearchFolder
      setSelectedFolderId(folder.id)
      setFolderMessage('文件夹已连接，可以扫描更新')
      await loadFolders(folder.id)
    } catch (connectError) {
      setFolderMessage(connectError instanceof Error ? connectError.message : '无法连接本地文件夹')
    } finally {
      setConnecting(false)
    }
  }

  async function scanFolder() {
    if (!selectedFolder) return
    setScanning(true)
    setFolderMessage('')
    try {
      const response = await fetch(`/api/research-folders/${encodeURIComponent(selectedFolder.id)}/scan`, { method: 'POST' })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || '扫描失败')
      setLastScanCounts(payload.counts || emptyCounts)
      const projectedCount = Number(payload.profile_projection?.projected_count || 0)
      const deletedCount = Number(payload.profile_projection?.deleted_count || 0)
      const profileMessage = projectedCount
        ? `，已更新 ${projectedCount} 只基金画像`
        : deletedCount
          ? `，已清理 ${deletedCount} 个失效画像`
          : ''
      setFolderMessage(`${payload.counts?.failed ? '扫描完成，部分文件需要处理' : '扫描完成'}${profileMessage}`)
      await Promise.all([loadMemos(), loadFolders(selectedFolder.id)])
    } catch (scanError) {
      setFolderMessage(scanError instanceof Error ? scanError.message : '扫描失败')
    } finally {
      setScanning(false)
    }
  }

  async function decideReview(review: PendingReview, action: 'confirmed' | 'rejected') {
    setReviewingId(review.id)
    setFolderMessage('')
    try {
      const response = await fetch(
        `/api/research-folders/reviews/${encodeURIComponent(review.report_id)}/${encodeURIComponent(review.id)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action }),
        },
      )
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || '无法保存复核结果')
      setPendingReviews((items) => items.filter((item) => item.id !== review.id))
      const projectedCount = Number(payload.profile_projection?.projected_count || 0)
      const deletedCount = Number(payload.profile_projection?.deleted_count || 0)
      setFolderMessage(
        projectedCount
          ? `已保存，并更新 ${projectedCount} 只基金画像`
          : deletedCount
            ? `已保存，并清理 ${deletedCount} 个失效画像`
            : '已保存',
      )
      await loadMemos()
    } catch (reviewError) {
      setFolderMessage(reviewError instanceof Error ? reviewError.message : '无法保存复核结果')
    } finally {
      setReviewingId('')
    }
  }

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

  return (
    <div className="space-y-7">
      <header className="border-b border-[#dce1dc] pb-6">
        <div className="flex items-center gap-2 text-xs font-bold text-[#28745c]"><BookOpenText className="h-4 w-4" />调研纪要库</div>
        <h1 className="mt-2 text-3xl font-bold leading-tight text-[#18231e]">按基金经理整理纪要</h1>
      </header>

      <section aria-labelledby="folder-heading" className="border-y border-[#dbe1dc] bg-white">
        <div className="grid gap-5 px-5 py-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <div className="flex items-center justify-between gap-4">
              <h2 id="folder-heading" className="text-sm font-bold">本地文件夹路径</h2>
              <span className="text-xs text-[#748078]">上次扫描：{formatDate(selectedFolder?.last_scan_at, true)}</span>
            </div>
            <div className="mt-3 flex min-w-0 flex-col gap-2 sm:flex-row">
              <label className="sr-only" htmlFor="research-folder-path">本地文件夹路径</label>
              <input
                id="research-folder-path"
                value={folderPath}
                onChange={(event) => setFolderPath(event.target.value)}
                placeholder="例如 /Users/你的名字/Documents/基金调研纪要"
                className="h-11 min-w-0 flex-1 rounded-md border border-[#cfd6d0] bg-[#fbfcfa] px-3 text-sm outline-none focus:border-[#28745c]"
              />
              <button type="button" onClick={() => void connectFolder()} disabled={connecting} className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-md border border-[#9aaba2] px-4 text-sm font-bold text-[#254c3e] hover:bg-[#eef4f0] disabled:opacity-50">
                {connecting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <FolderOpen className="h-4 w-4" />}
                连接
              </button>
            </div>
          </div>
          <button type="button" onClick={() => void scanFolder()} disabled={!selectedFolder || scanning || folderLoading} className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-[#173f35] px-5 text-sm font-bold text-white hover:bg-[#225747] disabled:opacity-45">
            <RefreshCw className={`h-4 w-4 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? '正在扫描' : '扫描更新'}
          </button>
        </div>
        <div className="grid grid-cols-2 border-t border-[#e5e9e5] sm:grid-cols-4">
          {[
            ['新增', displayedCounts.created, 'text-[#28745c]'],
            ['已更新', displayedCounts.updated, 'text-[#27608a]'],
            ['未变化', displayedCounts.unchanged, 'text-[#65716b]'],
            ['失败', displayedCounts.failed, displayedCounts.failed ? 'text-[#a14e46]' : 'text-[#65716b]'],
          ].map(([label, value, color]) => (
            <div key={String(label)} className="border-r border-[#e5e9e5] px-4 py-3 last:border-r-0">
              <div className="text-[11px] text-[#7a8580]">{label}</div>
              <div className={`mt-1 text-xl font-bold ${color}`}>{value}</div>
            </div>
          ))}
        </div>
      </section>

      {folderMessage ? <div className="flex items-center gap-2 border border-[#e2d09d] bg-[#fff9ea] px-4 py-3 text-sm text-[#725921]"><CircleAlert className="h-4 w-4 shrink-0" />{folderMessage}</div> : null}
      {error ? <div className="border border-[#e5c98f] bg-[#fff8e8] px-5 py-4 text-sm text-[#78551c]">{error}</div> : null}

      <section aria-labelledby="review-heading" className="border-t border-[#dce1dc] pt-5">
        <div className="flex items-center justify-between gap-4 pb-3">
          <h2 id="review-heading" className="text-lg font-bold">待确认</h2>
          <span className="text-xs text-[#748078]">{pendingReviews.length} 项</span>
        </div>
        {pendingReviews.length ? (
          <div className="divide-y divide-[#e3e8e4] border-y border-[#dbe1dc] bg-white">
            {pendingReviews.map((review) => (
              <article key={`${review.report_id}-${review.id}`} className="grid gap-4 px-5 py-4 md:grid-cols-[9rem_minmax(0,1fr)_auto] md:items-center">
                <div>
                  <div className="text-[11px] text-[#78837d]">{reviewKind(review.kind)}</div>
                  <strong className="mt-1 block text-sm">{review.value}</strong>
                  <span className="mt-1 block text-[11px] text-[#78837d]">置信度 {Math.round(review.confidence * 100)}%</span>
                </div>
                <div className="min-w-0">
                  <div className="truncate text-xs font-bold text-[#435149]">{review.report_title} · {review.source_ref.relative_path}</div>
                  <blockquote className="mt-2 border-l-2 border-[#d7b46a] pl-3 text-xs leading-6 text-[#68736d]">来源原文：{review.source_ref.excerpt}</blockquote>
                </div>
                <div className="flex gap-2">
                  <button type="button" aria-label={`确认${review.value}`} onClick={() => void decideReview(review, 'confirmed')} disabled={reviewingId === review.id} className="inline-flex h-9 items-center gap-1.5 rounded-md bg-[#e4efe9] px-3 text-xs font-bold text-[#245d49] hover:bg-[#d8e8df] disabled:opacity-50"><Check className="h-4 w-4" />确认</button>
                  <button type="button" aria-label={`拒绝${review.value}`} onClick={() => void decideReview(review, 'rejected')} disabled={reviewingId === review.id} className="inline-flex h-9 items-center gap-1.5 rounded-md border border-[#d6c9c5] px-3 text-xs font-bold text-[#8b4c43] hover:bg-[#faf1ef] disabled:opacity-50"><X className="h-4 w-4" />拒绝</button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="flex h-20 items-center gap-2 border-y border-[#dbe1dc] bg-white px-5 text-sm text-[#718078]"><CheckCircle2 className="h-4 w-4 text-[#28745c]" />没有待确认内容</div>
        )}
      </section>

      <section className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <label className="relative block">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-[#7d8882]" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索经理、基金、标题或风格标签" className="h-12 w-full rounded-md border border-[#cfd6d0] bg-white pl-12 pr-4 text-sm outline-none focus:border-[#28745c]" />
        </label>
        <div className="text-xs text-[#748078]">纪要库共 {total} 份</div>
      </section>

      <section className="grid min-h-[34rem] gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <aside className="border-b border-[#dce1dc] pb-4 lg:border-b-0 lg:border-r lg:pr-4">
          <div className="flex items-center justify-between pb-3 text-sm font-bold"><span>基金经理</span><span className="text-xs font-normal text-[#7a8580]">{managerGroups.length}</span></div>
          <div className="flex gap-1 overflow-x-auto lg:block">
            <button type="button" onClick={() => setSelectedManager('')} className={`mb-1 flex shrink-0 items-center justify-between rounded-md px-3 py-2 text-left text-sm lg:w-full ${!selectedManager ? 'bg-[#e3ece7] font-bold text-[#173f35]' : 'text-[#65716b] hover:bg-[#eef1ed]'}`}><span>全部纪要</span><span className="ml-3 text-xs">{memos.length}</span></button>
            {managerGroups.map((group) => (
              <button key={group.name} type="button" onClick={() => setSelectedManager(group.name)} className={`mb-1 flex shrink-0 items-center justify-between rounded-md px-3 py-2 text-left text-sm lg:w-full ${selectedManager === group.name ? 'bg-[#e3ece7] font-bold text-[#173f35]' : 'text-[#65716b] hover:bg-[#eef1ed]'}`}><span className="max-w-32 truncate">{group.name}</span><span className="ml-2 text-xs">{group.count}</span></button>
            ))}
          </div>
        </aside>

        <div className="min-w-0">
          <div className="pb-4">
            <h2 className="text-xl font-bold">{selectedManager || '全部调研纪要'}</h2>
            <p className="mt-1 text-xs text-[#7a8580]">当前显示 {filteredMemos.length} 份</p>
          </div>
          {loading ? (
            <div className="flex min-h-64 items-center justify-center gap-3 border border-dashed border-[#cbd3cd] bg-white text-sm text-[#66726c]"><LoaderCircle className="h-5 w-5 animate-spin" />正在读取调研纪要</div>
          ) : filteredMemos.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center border border-dashed border-[#cbd3cd] bg-white px-6 text-center"><FileSearch className="h-6 w-6 text-[#8b988f]" /><strong className="mt-3 text-sm">没有找到调研纪要</strong></div>
          ) : (
            <div className="divide-y divide-[#e3e8e4] border-y border-[#dbe1dc] bg-white">
              {filteredMemos.map((memo) => (
                <button key={memo.id} type="button" onClick={() => void openMemo(memo)} className="grid w-full gap-3 px-5 py-5 text-left transition hover:bg-[#f5f8f5] sm:grid-cols-[minmax(0,1fr)_auto]">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-[#718078]">
                      <span className="inline-flex items-center gap-1"><UserRound className="h-3.5 w-3.5" />{managerLabel(memo)}</span>
                      <span className="inline-flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{formatDate(memo.report_date)}</span>
                      {memo.local_relative_path ? <span className="truncate">{memo.local_relative_path}</span> : memo.source ? <span>{memo.source}</span> : null}
                    </div>
                    <strong className="mt-2 block text-sm text-[#1d2923]">{memo.title || '无标题纪要'}</strong>
                    <p className="mt-2 line-clamp-2 text-xs leading-6 text-[#66726c]">{memo.summary || '点击查看原文。'}</p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {[...(memo.classifications || []), ...(memo.style_labels || []), ...(memo.tags || [])].slice(0, 6).map((tag, index) => <span key={`${tag}-${index}`} className="rounded-sm bg-[#edf1ed] px-2 py-1 text-[11px] text-[#53625b]">{tag}</span>)}
                      {memo.review_status === 'pending' ? <span className="rounded-sm bg-[#fff2d8] px-2 py-1 text-[11px] text-[#795b1d]">有待确认内容</span> : null}
                    </div>
                    {memo.llm_extraction_status === 'failed' ? <p className="mt-2 text-[11px] text-[#8a6a2d]">模型提取暂不可用，已使用原文规则继续处理</p> : null}
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
                {selectedMemo.local_relative_path ? <p className="mt-2 break-all text-xs text-[#768179]">{selectedMemo.local_relative_path}</p> : null}
              </div>
              <button type="button" onClick={() => setSelectedMemo(null)} className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-[#65716b] hover:bg-[#edf1ed]" aria-label="关闭详情"><X className="h-5 w-5" /></button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-6 sm:px-7">
              {detailLoading ? <div className="flex items-center gap-2 text-sm text-[#66726c]"><LoaderCircle className="h-4 w-4 animate-spin" />读取原文</div> : null}
              <div className="flex flex-wrap gap-2">
                {[...(selectedMemo.classifications || []), ...(selectedMemo.style_labels || []), ...(selectedMemo.tags || [])].map((tag, index) => <span key={`${tag}-${index}`} className="inline-flex items-center gap-1 rounded-sm bg-[#e8efeb] px-2 py-1 text-xs text-[#315e4d]"><Tag className="h-3 w-3" />{tag}</span>)}
              </div>
              {selectedMemo.summary ? <p className="mt-5 border-l-4 border-[#d7b46a] bg-[#fff9eb] px-4 py-3 text-sm leading-7 text-[#66583a]">{selectedMemo.summary}</p> : null}
              {selectedMemo.llm_extraction_status === 'failed' ? (
                <div className="mt-4 border border-[#e2d09d] bg-[#fff9ea] px-4 py-3 text-xs leading-6 text-[#725921]">
                  模型提取暂不可用，已使用原文规则继续处理。经理、基金和标签仍需人工确认。
                </div>
              ) : null}
              {(selectedMemo.key_points || []).length ? <div className="mt-6 space-y-2">{(selectedMemo.key_points || []).map((point, index) => <div key={index} className="flex gap-2 text-sm leading-7 text-[#435149]"><CheckCircle2 className="mt-1.5 h-4 w-4 shrink-0 text-[#28745c]" />{point}</div>)}</div> : null}
              <div className="mt-7 whitespace-pre-wrap border-t border-[#dfe4df] pt-6 text-sm leading-8 text-[#334139]">{selectedMemo.content || '暂无可显示的原文。'}</div>
              {selectedMemo.source_hash ? <div className="mt-8 border-t border-[#e1e5e1] pt-4 text-[11px] text-[#7a8580]">来源校验：{selectedMemo.source_hash}</div> : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

'use client'

import Link from 'next/link'
import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  BarChart3,
  Bot,
  BookOpenText,
  CheckCircle2,
  Clock3,
  FileText,
  GitCompareArrows,
  LoaderCircle,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'

type FundOption = {
  windCode: string
  name: string
  type: string
  managers?: Array<{ name?: string }>
}

type AnalysisHistory = {
  id: string
  reportType: string
  targetId: string
  content: string
  metadata?: Record<string, unknown>
  createdAt: string
}

type AnalysisResult = {
  id?: string | null
  report: string
  metadata?: Record<string, unknown>
  timeline?: AnalysisTimeline | null
}

type AnalysisRevision = {
  id: string
  revision: number
  is_current: boolean
  created_at: string
  mode: string
  mode_label: string
  provider?: string | null
  model?: string | null
  question?: string
  change_summary: string
}

type AnalysisTimeline = {
  current_revision: number
  total_revisions: number
  revisions: AnalysisRevision[]
}

type LlmHealth = {
  status: 'ready' | 'degraded' | 'unconfigured'
  configured: boolean
  provider?: string
  model?: string
  retry_after_seconds?: number
}

function formatDate(value?: string | null) {
  if (!value) return '时间待补'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function analysisModeLabel(metadata?: Record<string, unknown>) {
  return metadata?.mode === 'llm_evaluation_evidence' ? '模型综合评价' : '本地证据评价'
}

function historyFundName(item: AnalysisHistory) {
  const name = typeof item.metadata?.fund_name === 'string' ? item.metadata.fund_name.trim() : ''
  return name || item.targetId
}

function historyPeerGroup(item: AnalysisHistory) {
  return typeof item.metadata?.peer_group === 'string' ? item.metadata.peer_group.trim() : ''
}

function healthCopy(health: LlmHealth | null) {
  if (!health) return { label: '模型状态读取中', detail: '分析仍可使用本地证据评价。', tone: 'text-[#65716b]' }
  if (health.status === 'ready') return { label: 'AI 模型已配置', detail: `${health.provider || '模型服务'} · ${health.model || '默认模型'}`, tone: 'text-[#28745c]' }
  if (health.status === 'degraded') return { label: 'AI 暂时降级', detail: health.retry_after_seconds ? `约 ${health.retry_after_seconds} 秒后恢复尝试，本次自动使用本地证据。` : '本次自动使用本地证据评价。', tone: 'text-[#9a681d]' }
  return { label: 'AI 模型未配置', detail: '仍可运行本地证据评价，不会生成模拟结论。', tone: 'text-[#65716b]' }
}

function ReportBody({ content }: { content: string }) {
  const lines = content.split('\n')
  return (
    <div className="space-y-2 text-sm leading-8 text-[#303d36]">
      {lines.map((rawLine, index) => {
        const line = rawLine.trim()
        if (!line) return <div key={index} className="h-2" />
        if (line.startsWith('# ')) return <h2 key={index} className="pt-2 text-2xl font-bold leading-tight text-[#18231e]">{line.slice(2)}</h2>
        if (line.startsWith('## ')) return <h3 key={index} className="border-b border-[#dfe4df] pb-2 pt-5 text-lg font-bold text-[#18231e]">{line.slice(3)}</h3>
        if (line.startsWith('### ')) return <h4 key={index} className="pt-3 font-bold text-[#1d2923]">{line.slice(4)}</h4>
        if (line.startsWith('- ')) return <div key={index} className="flex gap-2"><span className="mt-3 h-1.5 w-1.5 shrink-0 rounded-full bg-[#28745c]" /><span>{line.slice(2)}</span></div>
        if (line.startsWith('|')) return <div key={index} className="overflow-x-auto whitespace-pre font-mono text-xs text-[#526159]">{line}</div>
        if (line === '```json' || line === '```') return null
        return <p key={index}>{line}</p>
      })}
    </div>
  )
}

export default function FundAnalysisWorkspace({ initialFund = null }: { initialFund?: FundOption | null }) {
  const [query, setQuery] = useState(initialFund ? `${initialFund.name} ${initialFund.windCode}` : '')
  const [funds, setFunds] = useState<FundOption[]>([])
  const [fundLoading, setFundLoading] = useState(false)
  const [selectedFund, setSelectedFund] = useState<FundOption | null>(initialFund)
  const [question, setQuestion] = useState('')
  const [running, setRunning] = useState(false)
  const [progressStep, setProgressStep] = useState(0)
  const [error, setError] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [history, setHistory] = useState<AnalysisHistory[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [llmHealth, setLlmHealth] = useState<LlmHealth | null>(null)

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const response = await fetch('/api/analysis?targetType=fund&reportType=fund_evaluation_analysis&limit=20', { cache: 'no-store' })
      const payload = await response.json().catch(() => ({}))
      setHistory(response.ok && Array.isArray(payload.data) ? payload.data : [])
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const loadLlmHealth = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await fetch('/api/analysis/health', { cache: 'no-store', signal })
      const payload = await response.json().catch(() => ({}))
      setLlmHealth(payload as LlmHealth)
    } catch (healthError) {
      if (healthError instanceof DOMException && healthError.name === 'AbortError') return
      setLlmHealth({ status: 'degraded', configured: false })
    }
  }, [])

  useEffect(() => {
    const timer = globalThis.setTimeout(() => void loadHistory(), 0)
    return () => globalThis.clearTimeout(timer)
  }, [loadHistory])

  useEffect(() => {
    const controller = new AbortController()
    const timer = globalThis.setTimeout(() => void loadLlmHealth(controller.signal), 0)
    return () => {
      globalThis.clearTimeout(timer)
      controller.abort()
    }
  }, [loadLlmHealth])

  useEffect(() => {
    if (query.trim().length < 2 || selectedFund) {
      const timer = globalThis.setTimeout(() => {
        setFunds([])
        setFundLoading(false)
      }, 0)
      return () => globalThis.clearTimeout(timer)
    }
    const timer = globalThis.setTimeout(async () => {
      setFundLoading(true)
      try {
        const params = new URLSearchParams({ search: query.trim(), limit: '10' })
        const response = await fetch(`/api/fund-browser?${params.toString()}`, { cache: 'no-store' })
        const payload = await response.json().catch(() => ({}))
        setFunds(response.ok && Array.isArray(payload.data) ? payload.data : [])
      } finally {
        setFundLoading(false)
      }
    }, 300)
    return () => globalThis.clearTimeout(timer)
  }, [query, selectedFund])

  const progressLabels = ['读取基金与分类', '计算同类评价', '读取风险与归因', '检索调研纪要', '形成综合评价']

  async function runAnalysis(event: FormEvent) {
    event.preventDefault()
    if (!selectedFund) {
      setError('请先选择一只基金')
      return
    }
    setRunning(true)
    setProgressStep(0)
    setError('')
    setResult(null)
    const progressTimer = globalThis.setInterval(() => setProgressStep((step) => Math.min(progressLabels.length - 1, step + 1)), 1800)
    try {
      const response = await fetch('/api/analysis/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ windCode: selectedFund.windCode, question }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(typeof payload.error === 'string' ? payload.error : '分析失败')
      setResult(payload)
      setProgressStep(progressLabels.length - 1)
      await loadHistory()
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : '分析失败')
    } finally {
      globalThis.clearInterval(progressTimer)
      setRunning(false)
      void loadLlmHealth()
    }
  }

  async function openHistoryReport(reportId: string, fallbackTargetId = '') {
    setError('')
    try {
      const response = await fetch(`/api/analysis/${encodeURIComponent(reportId)}`, { cache: 'no-store' })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || '无法读取分析历史')
      setResult({ id: payload.id, report: payload.content, metadata: payload.metadata, timeline: payload.timeline })
      const targetId = payload.targetId || fallbackTargetId
      setSelectedFund({ windCode: targetId, name: targetId, type: '' })
      setQuery(targetId)
      globalThis.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (historyError) {
      setError(historyError instanceof Error ? historyError.message : '无法读取分析历史')
    }
  }

  async function openHistory(item: AnalysisHistory) {
    await openHistoryReport(item.id, item.targetId)
  }

  const selectedManager = useMemo(() => selectedFund?.managers?.map((manager) => manager.name).filter(Boolean).join('、') || '', [selectedFund])
  const modelHealthCopy = healthCopy(llmHealth)

  return (
    <div className="space-y-7">
      <section className="grid gap-7 border-b border-[#dce1dc] pb-8 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-end">
        <div className="max-w-3xl">
          <div className="flex items-center gap-2 text-xs font-bold uppercase text-[#28745c]"><Bot className="h-4 w-4" />AI 分析</div>
          <h1 className="mt-3 text-3xl font-bold leading-tight text-[#18231e] sm:text-4xl">选一只基金，现场跑一次综合评价</h1>
          <p className="mt-3 text-sm leading-7 text-[#65716b] sm:text-base">每次只分析你选择的基金，不跑全市场。AI 先读取分类内专业评价，再结合归因和调研纪要说人话。</p>
          <Link href={selectedFund ? `/analysis/advanced?fundCode=${encodeURIComponent(selectedFund.windCode)}` : '/analysis/advanced'} className="mt-4 inline-flex items-center gap-2 text-xs font-bold text-[#28745c]">单独查看 Barra / Brinson 业绩归因<ArrowRight className="h-4 w-4" /></Link>
          <div className={`mt-3 text-xs ${modelHealthCopy.tone}`}><strong>{modelHealthCopy.label}</strong><span className="ml-2">{modelHealthCopy.detail}</span></div>
        </div>
        <div className="grid grid-cols-3 gap-px overflow-hidden border border-[#dbe1dc] bg-[#dbe1dc] text-center text-xs">
          <div className="bg-white p-3"><BarChart3 className="mx-auto h-4 w-4 text-[#28745c]" /><span className="mt-2 block">同类评价</span></div>
          <div className="bg-white p-3"><ShieldCheck className="mx-auto h-4 w-4 text-[#28745c]" /><span className="mt-2 block">归因证据</span></div>
          <div className="bg-white p-3"><BookOpenText className="mx-auto h-4 w-4 text-[#28745c]" /><span className="mt-2 block">调研纪要</span></div>
        </div>
      </section>

      <section className="grid gap-7 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-5">
          <form onSubmit={runAnalysis} className="border border-[#dbe1dc] bg-white p-5 sm:p-6">
            <label className="block text-sm font-bold">选择基金</label>
            <div className="relative mt-3">
              <Search className="pointer-events-none absolute left-4 top-3.5 h-5 w-5 text-[#7d8882]" />
              <input value={query} onChange={(event) => { setQuery(event.target.value); setSelectedFund(null) }} placeholder="输入基金名称或代码" className="h-12 w-full rounded-md border border-[#cfd6d0] bg-white pl-12 pr-4 text-sm outline-none focus:border-[#28745c]" />
              {fundLoading ? <LoaderCircle className="absolute right-4 top-4 h-4 w-4 animate-spin text-[#28745c]" /> : null}
              {funds.length ? (
                <div className="absolute inset-x-0 top-14 z-20 max-h-72 overflow-y-auto border border-[#cfd6d0] bg-white shadow-xl">
                  {funds.map((fund) => (
                    <button key={fund.windCode} type="button" onClick={() => { setSelectedFund(fund); setQuery(`${fund.name} ${fund.windCode}`); setFunds([]) }} className="flex w-full items-center justify-between gap-4 border-b border-[#edf0ed] px-4 py-3 text-left text-sm hover:bg-[#f2f6f3]">
                      <span className="min-w-0"><strong className="block truncate">{fund.name || fund.windCode}</strong><small className="mt-1 block text-[#7a8580]">{fund.windCode} · {fund.type || '类别待确认'}</small></span>
                      <ArrowRight className="h-4 w-4 shrink-0 text-[#849088]" />
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            {selectedFund ? (
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 rounded-md bg-[#edf4f0] px-4 py-3 text-xs text-[#315e4d]">
                <span className="font-bold">{selectedFund.name}</span><span>{selectedFund.windCode}</span><span>{selectedFund.type || '类别待确认'}</span>{selectedManager ? <span>{selectedManager}</span> : null}
              </div>
            ) : null}

            <label className="mt-5 block text-sm font-bold" htmlFor="analysis-question">你最关心什么 <span className="font-normal text-[#7a8580]">（可选）</span></label>
            <textarea id="analysis-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={1000} rows={3} placeholder="例如：这只基金的超额收益主要来自哪里？风格是否稳定？" className="mt-3 w-full resize-y rounded-md border border-[#cfd6d0] bg-white px-4 py-3 text-sm leading-6 outline-none focus:border-[#28745c]" />

            <button type="submit" disabled={!selectedFund || running} className="mt-4 inline-flex h-11 items-center gap-2 rounded-md bg-[#173f35] px-5 text-sm font-bold text-white hover:bg-[#225747] disabled:cursor-not-allowed disabled:opacity-50">
              {running ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}{running ? '正在分析' : '开始分析'}
            </button>
          </form>

          {error ? <div className="border border-[#e5c98f] bg-[#fff8e8] px-5 py-4 text-sm text-[#78551c]">{error}</div> : null}

          {running ? (
            <div className="border border-[#dbe1dc] bg-white p-6">
              <div className="flex items-center gap-3"><LoaderCircle className="h-5 w-5 animate-spin text-[#28745c]" /><strong className="text-sm">{progressLabels[progressStep]}</strong></div>
              <div className="mt-5 grid grid-cols-5 gap-2">
                {progressLabels.map((label, index) => <div key={label}><div className={`h-1.5 ${index <= progressStep ? 'bg-[#28745c]' : 'bg-[#dfe4df]'}`} /><span className="mt-2 hidden text-[10px] leading-4 text-[#7a8580] sm:block">{label}</span></div>)}
              </div>
            </div>
          ) : null}

          {result ? (
            <article className="border border-[#dbe1dc] bg-white">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#dfe4df] px-5 py-4 sm:px-7">
                <div className="flex items-center gap-2 text-xs font-bold text-[#28745c]"><Sparkles className="h-4 w-4" />{analysisModeLabel(result.metadata)}</div>
                {result.id ? <span className="text-xs text-[#7a8580]">已保存到分析历史</span> : null}
              </div>
              <div className="px-5 py-6 sm:px-7 sm:py-8"><ReportBody content={result.report} /></div>
              {result.timeline?.revisions?.length ? (
                <div className="border-t border-[#dfe4df] px-5 py-5 sm:px-7">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="flex items-center gap-2 text-sm font-bold"><Clock3 className="h-4 w-4 text-[#28745c]" />分析版本</h3>
                    <span className="text-xs text-[#7a8580]">当前 V{result.timeline.current_revision} / 共 {result.timeline.total_revisions} 版</span>
                  </div>
                  <div className="mt-4 divide-y divide-[#e5e9e6] border-y border-[#e5e9e6]">
                    {result.timeline.revisions.map((revision) => (
                      <button key={revision.id} type="button" onClick={() => void openHistoryReport(revision.id)} disabled={revision.is_current} className="grid w-full gap-1 py-3 text-left disabled:cursor-default sm:grid-cols-[5rem_minmax(0,1fr)_10rem] sm:items-center">
                        <strong className={revision.is_current ? 'text-[#28745c]' : 'text-[#36443d]'}>V{revision.revision}{revision.is_current ? ' · 当前' : ''}</strong>
                        <span className="text-xs leading-5 text-[#5f6c65]">{revision.change_summary}</span>
                        <span className="text-xs text-[#929b96] sm:text-right">{formatDate(revision.created_at)}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </article>
          ) : null}
        </div>

        <aside className="min-w-0">
          <div className="flex items-center justify-between border-b border-[#dbe1dc] pb-3">
            <h2 className="flex items-center gap-2 text-sm font-bold"><Clock3 className="h-4 w-4 text-[#28745c]" />分析历史</h2>
            <span className="text-xs text-[#7a8580]">{history.length}</span>
          </div>
          {historyLoading ? <div className="flex items-center gap-2 py-5 text-xs text-[#7a8580]"><LoaderCircle className="h-4 w-4 animate-spin" />读取中</div> : null}
          <div className="divide-y divide-[#e0e5e1]">
            {history.map((item) => (
              <button key={item.id} type="button" onClick={() => void openHistory(item)} className="block w-full py-4 text-left hover:text-[#28745c]">
                <div className="flex items-center justify-between gap-3"><strong className="truncate text-sm">{historyFundName(item)}</strong><FileText className="h-4 w-4 shrink-0 text-[#849088]" /></div>
                <p className="mt-1 text-[11px] text-[#929b96]">{item.targetId}{historyPeerGroup(item) ? ` · ${historyPeerGroup(item)}` : ''}</p>
                <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#6c7871]">{item.content || '基金评价分析'}</p>
                <span className="mt-2 block text-[11px] text-[#929b96]">{formatDate(item.createdAt)}</span>
              </button>
            ))}
          </div>
          {!historyLoading && !history.length ? <p className="py-5 text-xs leading-6 text-[#7a8580]">完成第一次分析后，记录会保存在这里。</p> : null}
          <Link href="/analysis/comparison" className="mt-5 flex items-center justify-between border border-[#dbe1dc] bg-white px-4 py-3 text-sm font-bold text-[#315e4d] hover:border-[#90ad9f]">
            <span className="inline-flex items-center gap-2"><GitCompareArrows className="h-4 w-4" />比较多只基金</span><ArrowRight className="h-4 w-4" />
          </Link>
        </aside>
      </section>

      <section className="grid gap-3 border-t border-[#dce1dc] pt-6 sm:grid-cols-3">
        <div className="flex gap-3 text-xs leading-6 text-[#65716b]"><CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-[#28745c]" /><span>评分只来自分类专属方法，不由 AI 即兴设计。</span></div>
        <div className="flex gap-3 text-xs leading-6 text-[#65716b]"><CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-[#28745c]" /><span>Barra 和 Brinson 类证据只解释收益与风险来源。</span></div>
        <div className="flex gap-3 text-xs leading-6 text-[#65716b]"><CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-[#28745c]" /><span>数据不足时明示缺口，不使用模拟数据补结论。</span></div>
      </section>
    </div>
  )
}

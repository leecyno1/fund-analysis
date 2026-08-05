'use client'

import Link from 'next/link'
import { useCallback, useState } from 'react'
import { ArrowRight, BarChart3, Check, CircleAlert, GitCompareArrows, Search, Sparkles } from 'lucide-react'
import type { CamelFund } from '@/lib/backend-api'
import {
  drawdownMetric,
  evidenceCoverage,
  formatAsset,
  formatPercent,
  managerName,
  professionalPeerGroup,
  professionalPeerGroupId,
  returnMetric,
  sharpeMetric,
  styleLabel,
  type SimpleFund,
} from '@/lib/simple-fund-view'

type Props = {
  initialFunds: CamelFund[]
  initialCategories: Array<{ id: string; name: string; count: number }>
  initialTotal: number
  initialSource: string
  initialError: string
}

export default function FundDiscoverClient({ initialFunds, initialCategories, initialTotal, initialSource, initialError }: Props) {
  const [funds, setFunds] = useState<SimpleFund[]>(initialFunds)
  const [searchText, setSearchText] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')
  const [peerGroupFilter, setPeerGroupFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(initialError)
  const [total, setTotal] = useState(initialTotal)
  const [compareFunds, setCompareFunds] = useState<SimpleFund[]>([])

  const runSearch = useCallback(async (nextPeerGroup = peerGroupFilter) => {
    setLoading(true)
    setError('')
    const params = new URLSearchParams({ limit: '30' })
    if (searchText.trim()) params.set('search', searchText.trim())
    if (nextPeerGroup) params.set('peerGroup', nextPeerGroup)
    try {
      const response = await fetch(`/api/fund-browser?${params.toString()}`)
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || '基金查询失败')
      setFunds(payload.data || [])
      setTotal(Number(payload.pagination?.total || 0))
      setAppliedSearch(searchText.trim())
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : '基金查询失败')
    } finally {
      setLoading(false)
    }
  }, [searchText, peerGroupFilter])

  const compareCodes = compareFunds.map((fund) => fund.windCode)
  const compareHref = `/compare?${new URLSearchParams({ codes: compareCodes.join(',') }).toString()}`
  const lockedPeerGroup = compareFunds.length ? professionalPeerGroup(compareFunds[0]) : ''

  function toggleCompare(fund: SimpleFund) {
    if (compareFunds.some((item) => item.windCode === fund.windCode)) {
      setCompareFunds((current) => current.filter((item) => item.windCode !== fund.windCode))
      return
    }
    if (compareFunds.length >= 6) return
    const selectedGroupId = professionalPeerGroupId(fund)
    if (!selectedGroupId) {
      setError('这只基金尚未完成专业分类，可以浏览，但暂不能加入同类比较。')
      return
    }
    if (compareFunds.length && professionalPeerGroupId(compareFunds[0]) !== selectedGroupId) {
      setError(`已锁定“${professionalPeerGroup(compareFunds[0])}”同类组，请只选择该类基金。`)
      return
    }
    setError('')
    setCompareFunds((current) => [...current, fund])
  }

  return (
    <div className="space-y-7">
      <section className="border-b border-[#dce1dc] pb-7">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-bold uppercase text-[#28745c]">基金浏览器</p>
            <h1 className="mt-3 text-3xl font-bold leading-tight text-[#18231e] sm:text-4xl">快速找到并看懂一只基金</h1>
            <p className="mt-3 text-sm leading-7 text-[#65716b] sm:text-base">先选专业同类组，再看收益、回撤、规模、经理与风格。只有分类一致的基金才能横向比较。</p>
          </div>
          <div className="flex items-center gap-3 text-sm text-[#65716b]">
            <span className="rounded-sm bg-[#e7eee9] px-3 py-2 font-semibold text-[#245c49]">{total.toLocaleString('zh-CN')} 只基金</span>
            <span className="hidden sm:inline">来源：{initialSource === 'database' ? '本地数据库' : initialSource}</span>
          </div>
        </div>

        <form
          className="mt-7 grid gap-3 lg:grid-cols-[minmax(0,1fr)_14rem_auto]"
          onSubmit={(event) => {
            event.preventDefault()
            void runSearch()
          }}
        >
          <label className="relative block">
            <span className="sr-only">搜索基金</span>
            <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-[#7d8882]" />
            <input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="输入基金名称或代码"
              className="h-12 w-full rounded-md border border-[#cfd6d0] bg-white pl-12 pr-4 text-sm outline-none transition focus:border-[#28745c] focus:ring-2 focus:ring-[#28745c]/10"
            />
          </label>
          <select
            value={peerGroupFilter}
            onChange={(event) => {
              const nextPeerGroup = event.target.value
              setPeerGroupFilter(nextPeerGroup)
              setCompareFunds([])
              setError('')
              void runSearch(nextPeerGroup)
            }}
            aria-label="专业同类组"
            className="h-12 rounded-md border border-[#cfd6d0] bg-white px-4 text-sm outline-none focus:border-[#28745c]"
          >
            <option value="">全部专业类别</option>
            {initialCategories.map((category) => <option key={category.id} value={category.name}>{category.name}（{category.count} 只）</option>)}
          </select>
          <button type="submit" disabled={loading} className="h-12 rounded-md bg-[#173f35] px-6 text-sm font-bold text-white transition hover:bg-[#225747] disabled:opacity-60">
            {loading ? '查询中' : '查找基金'}
          </button>
        </form>
      </section>

      {error ? (
        <div className="border border-[#e5c98f] bg-[#fff8e8] px-5 py-4 text-sm text-[#78551c]">{error}</div>
      ) : null}

      {lockedPeerGroup ? (
        <section className="flex flex-wrap items-center gap-x-4 gap-y-2 border-l-4 border-[#2b775d] bg-[#eef5f1] px-5 py-4 text-sm text-[#315e4d]">
          <strong>比较已锁定：{lockedPeerGroup}</strong>
          <span className="text-xs text-[#64736c]">已选 {compareCodes.length} / 6 只，其他类别不会加入。</span>
        </section>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-3">
        <Link href="/recommendations" className="flex items-center gap-4 border border-[#dbe1dc] bg-white p-4 transition hover:border-[#8cb3a4]">
          <span className="grid h-10 w-10 place-items-center rounded-md bg-[#e5efe9] text-[#23644f]"><Sparkles className="h-5 w-5" /></span>
          <span className="min-w-0"><strong className="block text-sm">按风格找基金</strong><small className="mt-1 block text-xs text-[#76817b]">成长、价值、均衡等标签</small></span>
          <ArrowRight className="ml-auto h-4 w-4 text-[#829089]" />
        </Link>
        <Link href="/analysis" className="flex items-center gap-4 border border-[#dbe1dc] bg-white p-4 transition hover:border-[#8cb3a4]">
          <span className="grid h-10 w-10 place-items-center rounded-md bg-[#eef0e4] text-[#707433]"><BarChart3 className="h-5 w-5" /></span>
          <span className="min-w-0"><strong className="block text-sm">运行 AI 分析</strong><small className="mt-1 block text-xs text-[#76817b]">结合量化与调研纪要</small></span>
          <ArrowRight className="ml-auto h-4 w-4 text-[#829089]" />
        </Link>
        <Link href={compareCodes.length >= 2 ? compareHref : '/compare'} className="flex items-center gap-4 border border-[#dbe1dc] bg-white p-4 transition hover:border-[#8cb3a4]">
          <span className="grid h-10 w-10 place-items-center rounded-md bg-[#f1e9e2] text-[#8a5a3c]"><GitCompareArrows className="h-5 w-5" /></span>
          <span className="min-w-0"><strong className="block text-sm">比较基金</strong><small className="mt-1 block text-xs text-[#76817b]">已选 {compareCodes.length} / 6 只</small></span>
          <ArrowRight className="ml-auto h-4 w-4 text-[#829089]" />
        </Link>
      </section>

      <section>
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4">
          <div>
            <h2 className="text-lg font-bold">{appliedSearch ? `“${appliedSearch}”的结果` : '基金列表'}</h2>
            <p className="mt-1 text-xs text-[#7b8680]">{peerGroupFilter ? `当前只显示“${peerGroupFilter}”标准同类组。` : '未分类基金可浏览，但不能加入同类比较。'}</p>
          </div>
          {compareCodes.length >= 2 ? (
            <Link href={compareHref} className="inline-flex h-10 items-center gap-2 rounded-md bg-[#173f35] px-4 text-sm font-bold text-white">
              <GitCompareArrows className="h-4 w-4" />比较 {compareCodes.length} 只基金
            </Link>
          ) : null}
        </div>

        {funds.length === 0 ? (
          <div className="border border-dashed border-[#cbd3cd] bg-white px-6 py-16 text-center text-sm text-[#748079]"><CircleAlert className="mx-auto mb-3 h-5 w-5 text-[#9a7a3a]" />没有找到可展示的基金。</div>
        ) : (
          <div className="overflow-x-auto border border-[#dbe1dc] bg-white">
            <table className="w-full min-w-[980px] border-collapse text-left text-sm">
              <thead className="bg-[#f1f4f1] text-xs text-[#66726c]">
                <tr>
                  <th className="w-12 px-4 py-3">对比</th>
                  <th className="px-4 py-3">基金</th>
                  <th className="px-4 py-3">专业同类组 / 风格</th>
                  <th className="px-4 py-3 text-right">近 1 年</th>
                  <th className="px-4 py-3 text-right">最大回撤</th>
                  <th className="px-4 py-3 text-right">Sharpe</th>
                  <th className="px-4 py-3 text-right">规模</th>
                  <th className="px-4 py-3">经理</th>
                  <th className="px-4 py-3 text-right">数据完整度</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e5e9e5]">
                {funds.map((fund) => {
                  const selected = compareCodes.includes(fund.windCode)
                  const annualReturn = returnMetric(fund)
                  return (
                    <tr key={fund.windCode} className="transition hover:bg-[#f7faf7]">
                      <td className="px-4 py-4">
                        <button
                          type="button"
                          onClick={() => toggleCompare(fund)}
                          disabled={!selected && compareCodes.length >= 6}
                          className={`grid h-7 w-7 place-items-center rounded border ${selected ? 'border-[#2c765d] bg-[#2c765d] text-white' : 'border-[#c7d0ca] text-transparent hover:border-[#2c765d]'}`}
                          aria-label={selected ? `移出对比：${fund.name}` : `加入对比：${fund.name}`}
                        >
                          <Check className="h-4 w-4" />
                        </button>
                      </td>
                      <td className="px-4 py-4">
                        <Link href={`/funds/${encodeURIComponent(fund.windCode)}`} className="font-bold text-[#1b2923] hover:text-[#28745c]">{fund.name || fund.windCode}</Link>
                        <div className="mt-1 text-xs text-[#7b8680]">{fund.windCode} · 净值 {fund.nav?.toFixed(4) || '—'}</div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="max-w-[14rem] truncate font-medium">{professionalPeerGroup(fund) || '专业分类待确认'}</div>
                        <div className="mt-1 flex flex-wrap gap-2"><span className="inline-flex rounded-sm bg-[#edf1ed] px-2 py-1 text-xs text-[#5f6b65]">{styleLabel(fund)}</span><span className="inline-flex px-1 py-1 text-xs text-[#8a948f]">{fund.type || '法律类型待补'}</span></div>
                      </td>
                      <td className={`px-4 py-4 text-right font-bold ${annualReturn != null && annualReturn < 0 ? 'text-[#a84d47]' : 'text-[#267257]'}`}>{formatPercent(annualReturn)}</td>
                      <td className="px-4 py-4 text-right text-[#8b4f48]">{formatPercent(drawdownMetric(fund))}</td>
                      <td className="px-4 py-4 text-right">{sharpeMetric(fund)?.toFixed(2) || '—'}</td>
                      <td className="px-4 py-4 text-right">{formatAsset(fund.totalAsset)}</td>
                      <td className="px-4 py-4">{managerName(fund)}</td>
                      <td className="px-4 py-4 text-right"><span className="font-bold">{Math.round(evidenceCoverage(fund))}%</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
